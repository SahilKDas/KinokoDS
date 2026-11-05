"""Save bounded ROM-derived disassembly and provenance inside ignored local/."""
import hashlib
import json
from pathlib import Path
import capstone
from rom_code import CodeImage, ROOT
from sync_parameters import ROM_HASH

REGIONS = [
    (0x02062eb0, 0x02062ec0, 'presentation predicate getter'),
    (0x020726bc, 0x020727c8, 'per-driver parameter initialization'),
    (0x0208aea8, 0x0208af38, 'source selection and record copies'),
    (0x0208ae74, 0x0208ae88, 'active character accessor'),
    (0x0208ae8c, 0x0208aea4, 'active kart accessor'),
    (0x01ffc5a0, 0x01ffc66c, 'input mapping and per-update flag reset'),
    (0x01ffba68, 0x01ffbd80, 'acceleration routine and excluded branches'),
    (0x01ffb9e0, 0x01ffba64, 'coasting and forced-stop drag'),
    (0x01ffaf18, 0x01ffb0c8, 'speed cap and excluded modifiers'),
    (0x01ffbd9c, 0x01ffbe04, 'upstream speed-fraction update (not ported)'),
    (0x02147d88, 0x02147db4, 'FX_DivAsync hardware setup'),
    (0x02147e28, 0x02147e5c, 'FX_GetDivResult rounding'),
    (0x02147f34, 0x02147f50, 'FX_Div wrapper'),
    (0x01ffc79c, 0x01ffc7f8, 'input-path caller ordering'),
    (0x01ffb33c, 0x01ffb36c, 'drag caller ordering'),
    (0x01ffb554, 0x01ffb5b8, 'speed cap caller ordering'),
]


def main():
    code = CodeImage()
    decoder = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    manifest = {'rom_sha256': ROM_HASH, 'capstone_version': capstone.__version__,
                'provenance': 'decompressed pinned ARM9 plus SDK autoload relocation; no live ITCM capture',
                'segments': [{'address': hex(base), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
                             for base, data in code.segments], 'regions': []}
    listing = []
    for start, end, name in REGIONS:
        blob = code.read(start, end - start)
        instructions = list(decoder.disasm(blob, start))
        if sum(i.size for i in instructions) != len(blob):
            raise ValueError(f'incomplete decode for {name}')
        listing.append(f'\n{name}: [{start:08x}, {end:08x})\n')
        listing.extend(f'{i.address:08x}: {i.mnemonic} {i.op_str}\n' for i in instructions)
        manifest['regions'].append({'name': name, 'start': hex(start), 'end_exclusive': hex(end),
                                    'sha256': hashlib.sha256(blob).hexdigest()})
    directory = ROOT / 'local/validation/mario-standard-mr-figure8-01'
    (directory / 'longitudinal.asm.txt').write_text(''.join(listing), encoding='utf-8')
    (directory / 'longitudinal-evidence.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Recorded {len(REGIONS)} instruction regions and {len(code.segments)} mapped segments')


if __name__ == '__main__':
    main()
