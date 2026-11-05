"""Record bounded frame-path evidence; does not claim live frame validation."""
import hashlib
import json
import capstone
from rom_code import CodeImage, ROOT
from sync_parameters import ROM_HASH

REGIONS = [
    (0x020652ec, 0x020653bc, 'alternate driver caller ordering; enclosing context unresolved'),
    (0x01ffbd9c, 0x01ffbe04, 'fraction from measured movement and cap'),
    (0x01ffb638, 0x01ffb768, 'displacement construction and recovered helpers'),
    (0x01ffb7cc, 0x01ffb7f0, 'conditional position addition'),
    (0x02148504, 0x02148538, 'complete vector addition helper'),
    (0x01ffae14, 0x01ffaf18, 'complete displacement scale, normalization, magnitude and clamp'),
    (0x02039860, 0x0203998c, 'complete magnitude/normalization helper'),
    (0x01ffbe04, 0x01ffbe6c, 'cap transition'),
    (0x02147fd8, 0x02148038, 'complete vector scale-add helper'),
    (0x020637e0, 0x02063830, 'ordinary driver caller'),
    (0x01ff9c40, 0x01ff9c98, 'complete flag-gated accumulator helper'),
    (0x01ffb638, 0x01ffb7f0, 'complete connected movement tail'),
    (0x01ffbe70, 0x01ffbfd0, 'complete cap target production'),
    (0x01ffb930, 0x01ffb9c8, 'complete direction penalty'),
    (0x020397a8, 0x02039828, 'complete cross-product helper'),
    (0x02063b10, 0x02063b30, 'complete orientation-vector accessor'),
    (0x01ffb5b8, 0x01ffb638, 'complete direction blend fragment'),
    (0x021484d0, 0x02148504, 'complete vector subtraction helper'),
    (0x01ffcc50, 0x01ffccd0, 'driver update body replayed from captured fields'),
    (0x01ffb130, 0x01ffb8f8, 'full movement body; not fully ported'),
    (0x020738f4, 0x020738f8, 'mode-0 movement dispatch target is a no-op'),
    (0x0207aaec, 0x0207abd8, 'history, inter-driver, update and post-update dispatcher'),
    (0x020646c0, 0x020646f0, 'captured driver update callback'),
    (0x020641d4, 0x020641f0, 'captured driver post-update callback'),
    (0x02039828, 0x02039860, 'complete truncating dot-product helper'),
    (0x0207a74c, 0x0207a778, 'complete projected-movement global writer'),
]
DATA_REGIONS = [
    (0x0203998c, 0x020399a8, 'normalization MMIO address literals'),
    (0x01ffbe6c, 0x01ffbe70, 'cap transition coefficient'),
    (0x01ff9c98, 0x01ff9c9c, 'accumulator reset mask'),
    (0x01ffbfd0, 0x01ffbfe4, 'cap production masks and coefficients'),
    (0x01ffb9c8, 0x01ffb9cc, 'direction penalty coefficient pointer'),
    (0x021654d8, 0x021654dc, 'direction penalty coefficient'),
    (0x01ffb8f8, 0x01ffb930, 'movement body literal pool'),
    (0x021655c4, 0x021655e0, 'seven inspected movement dispatch targets; table length not inferred'),
    (0x0207a778, 0x0207a780, 'projected-movement global pointers'),
]
THUMB_REGIONS = [
    (0x02147218, 0x0214722e, 'Thumb rotation-matrix helper 1'),
    (0x02147230, 0x0214724e, 'Thumb rotation-matrix helper 2'),
    (0x02147250, 0x0214726a, 'Thumb rotation-matrix helper 3'),
    (0x0214726c, 0x02147286, 'Thumb rotation-matrix helper 4'),
]


def main():
    code = CodeImage()
    decoder = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
    manifest = {'rom_sha256': ROM_HASH, 'capstone_version': capstone.__version__,
                'segments': [{'start': hex(base), 'bytes': len(blob), 'sha256': hashlib.sha256(blob).hexdigest()}
                             for base, blob in code.segments],
                'status': 'static inspection only; no live trace captured', 'regions': []}
    listing = []
    for start, end, name in REGIONS + THUMB_REGIONS:
        blob = code.read(start, end - start)
        mode = 'thumb' if (start, end, name) in THUMB_REGIONS else 'arm'
        decoder.mode = capstone.CS_MODE_THUMB if mode == 'thumb' else capstone.CS_MODE_ARM
        instructions = list(decoder.disasm(blob, start))
        if sum(i.size for i in instructions) != len(blob):
            raise ValueError(f'incomplete decode: {name}')
        listing.append(f'\n{name}: [{start:08x}, {end:08x})\n')
        listing.extend(f'{i.address:08x}: {i.mnemonic} {i.op_str}\n' for i in instructions)
        manifest['regions'].append({'name': name, 'mode': mode, 'start': hex(start),
            'end_exclusive': hex(end), 'sha256': hashlib.sha256(blob).hexdigest()})
    for start, end, name in DATA_REGIONS:
        blob = code.read(start, end - start)
        listing.append(f'\n{name}: [{start:08x}, {end:08x}) DATA {blob.hex()}\n')
        manifest['regions'].append({'name': name, 'kind': 'data', 'start': hex(start),
            'end_exclusive': hex(end), 'sha256': hashlib.sha256(blob).hexdigest()})
    directory = ROOT / 'local/validation/frame-inspection'
    directory.mkdir(parents=True, exist_ok=True)
    (directory / 'frame.asm.txt').write_text(''.join(listing), encoding='utf-8')
    (directory / 'evidence.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(f'Recorded {len(REGIONS) + len(THUMB_REGIONS)} code and {len(DATA_REGIONS)} data ranges; full-frame verification remains pending')


if __name__ == '__main__':
    main()
