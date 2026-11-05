"""Resolve the baseline's active driver from a captured AMCE RAM image.

Offsets are research hypotheses corroborated by pointer/identity checks, not
portable symbols. No emulator memory is modified. Results stay in local/.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
from sync_parameters import decode_kart

ROOT = Path(__file__).resolve().parents[1]
BASE = 0x02000000


def hits(data, pattern):
    start = 0
    while (pos := data.find(pattern, start)) >= 0:
        yield pos
        start = pos + 1


def analyze(ram, karts, characters):
    if len(ram) != 0x400000 or len(karts) != 50 * 0x98 or len(characters) != 13 * 8:
        raise ValueError('expected AMCE main RAM and original table sizes')

    def read(address, size):
        pos = address - BASE
        if pos < 0 or pos + size > len(ram):
            raise ValueError('pointer outside main RAM')
        return ram[pos:pos + size]

    def u32(address):
        return struct.unpack('<I', read(address, 4))[0]

    candidates = []
    for table_pos in hits(ram, karts):
        table_address = BASE + table_pos
        for pointer_pos in hits(ram, struct.pack('<I', table_address)):
            # physp: driver kart ptr, driver char ptr, field8, kart table, char table.
            context = BASE + pointer_pos - 12
            try:
                kp, cp, unknown, kt, ct = struct.unpack('<5I', read(context, 20))
                if read(ct, len(characters)) != characters:
                    continue
                active_kart, active_char = read(kp, 0x98), read(cp, 8)
                for driver_pointer_pos in hits(ram, struct.pack('<II', kp, cp)):
                    driver = BASE + driver_pointer_pos - 0x2cc
                    if driver == context - 0x2cc:
                        continue
                    char_kart = u32(driver + 0x590)
                    character_id, kart_id = struct.unpack('<II', read(char_kart, 8))
                    if character_id != 0 or kart_id != 0 or read(driver + 0x74, 2) != b'\0\0':
                        continue
                    source_kart, effective_kart = decode_kart(karts[:0x98]), decode_kart(active_kart)
                    differences = {key: {'source': value, 'active': effective_kart[key]}
                                   for key, value in source_kart.items() if effective_kart[key] != value}
                    char_factor, char_weight = struct.unpack('<ii', active_char)
                    src = source_kart['collision_speed_multipliers_raw']
                    actual = effective_kart['collision_speed_multipliers_raw']
                    affected = [i for i in range(12) if src[i] != actual[i]]
                    rounded = [(value * char_factor + 0x800) >> 12 for value in src]
                    predicted = [((value * char_factor + 0x800) >> 12) if value < 4096 else value for value in src]
                    candidates.append({
                        'driver_address': hex(driver), 'char_kart_address': hex(char_kart),
                        'character_id': character_id, 'kart_id': kart_id,
                        'kart_table_address': hex(kt), 'character_table_address': hex(ct),
                        'active_kart_address': hex(kp), 'active_character_address': hex(cp),
                        'physp_address': hex(context), 'physp_unknown_08_raw': unknown,
                        'character_record_exact': active_char == characters[:8],
                        'character_factor_raw': char_factor, 'character_weight_raw': char_weight,
                        'active_kart_sha256': hashlib.sha256(active_kart).hexdigest(),
                        'kart_field_differences': differences,
                        'changed_surface_slots': affected,
                        'changed_slots_fit_rounded_fx_mul': all(actual[i] == rounded[i] for i in affected),
                        'complete_surface_array_matches_instruction_rule': actual == predicted,
                        'position_raw': list(struct.unpack('<iii', read(driver + 0x80, 12))),
                        'speed_raw': struct.unpack('<i', read(driver + 0x2a8, 4))[0],
                    })
            except ValueError:
                continue
    if len(candidates) != 1:
        raise ValueError(f'expected one corroborated Mario/kart 0 driver; found {len(candidates)}')
    return candidates[0]


def main(label):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in label):
        raise ValueError('invalid label')
    directory = ROOT / 'local/validation' / label
    ram = (directory / 'arm9-main-ram.bin').read_bytes()
    capture = json.loads((directory / 'report.json').read_text())
    if hashlib.sha256(ram).hexdigest() != capture['ram_sha256']:
        raise ValueError('capture digest mismatch')
    result = analyze(ram, (ROOT / 'local/parameters/kartphysicalparam.bin').read_bytes(),
                     (ROOT / 'local/parameters/charphysicalparam.bin').read_bytes())
    result['capture'] = label
    result['status'] = 'active identity and parameter snapshot corroborated; physics unverified'
    result['layout_commit'] = '2d089194e146650406f6c257914ec397d35c8de7'
    address = int(result['active_kart_address'], 16) - BASE
    (directory / 'active-kart.bin').write_bytes(ram[address:address + 0x98])
    (directory / 'active-parameters.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    main(parser.parse_args().label)
