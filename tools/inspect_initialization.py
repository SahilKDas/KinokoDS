"""Disassemble bounded initialization routines from the existing local capture.

Uses the already-installed capstone package. Does not download tools or contact
melonDS. All instruction listings are ignored local research artifacts.
"""
import hashlib
import json
from pathlib import Path
import capstone

ROOT = Path(__file__).resolve().parents[1]
DIRECTORY = ROOT / 'local/validation/mario-standard-mr-figure8-01'
BASE = 0x02000000


def main():
    ram = (DIRECTORY / 'arm9-main-ram.bin').read_bytes()
    report = json.loads((DIRECTORY / 'report.json').read_text())
    if hashlib.sha256(ram).hexdigest() != report['ram_sha256']:
        raise ValueError('capture digest mismatch')
    decoder = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    regions = [(0x020726BC, 0x020727C8, 'driver parameter setup'),
               (0x0208AE74, 0x0208AE88, 'character parameter accessor'),
               (0x0208AE8C, 0x0208AEA4, 'kart parameter accessor'),
               (0x0208AEA8, 0x0208AF38, 'parameter record copy')]
    manifest = {'ram_sha256': report['ram_sha256'], 'capstone_version': capstone.__version__, 'regions': []}
    listings = []
    for start, end, label in regions:
        code = ram[start - BASE:end - BASE]
        listing = list(decoder.disasm(code, start))
        if sum(instruction.size for instruction in listing) != len(code):
            raise ValueError('incomplete instruction decode')
        listings.append(f'\n{label} [{start:08x}, {end:08x})\n')
        for instruction in listing:
            listings.append(f'{instruction.address:08x}: {instruction.mnemonic} {instruction.op_str}\n')
        manifest['regions'].append({'label': label, 'start': hex(start), 'end_exclusive': hex(end),
                                    'sha256': hashlib.sha256(code).hexdigest()})
    (DIRECTORY / 'initialization.asm.txt').write_text(''.join(listings), encoding='utf-8')
    (DIRECTORY / 'initialization-evidence.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Inspected {len(regions)} bounded code regions offline')


if __name__ == '__main__':
    main()
