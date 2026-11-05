"""Extract only parameter tables from the pinned local ROM; never emit assets to Git.

No third-party dependencies. Names/layouts are research interpretations, not
verified runtime behavior. Unknown fields and raw records are retained.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct

ROOT = Path(__file__).resolve().parents[1]
ROM_HASH = '0ea8a91a0ae3e9db26337c25a6a8568f6737fa36c1e0761988c0fa0ecbf210ed'
CHARACTERS = ['Mario', 'Donkey Kong', 'Toad', 'Bowser', 'Peach', 'Wario',
              'Yoshi', 'Luigi', 'Dry Bones', 'Daisy', 'Waluigi', 'R.O.B.', 'Shy Guy']


def region(data, offset, size):
    if offset < 0 or size < 0 or offset + size > len(data):
        raise ValueError('binary range out of bounds')
    return data[offset:offset + size]


def u16(data, offset):
    return struct.unpack('<H', region(data, offset, 2))[0]


def u32(data, offset):
    return struct.unpack('<I', region(data, offset, 4))[0]


def filesystem(fnt, fat, image):
    """Nitro directory table; return paths and byte ranges, not extracted files."""
    count = u16(fnt, 6)
    if not count or count > 4096 or len(fat) % 8:
        raise ValueError('invalid filesystem tables')
    files = {}
    seen = set()

    def walk(directory, prefix):
        index = directory - 0xF000
        if not 0 <= index < count or directory in seen:
            raise ValueError('invalid/cyclic directory')
        seen.add(directory)
        cursor = u32(fnt, index * 8)
        file_id = u16(fnt, index * 8 + 4)
        while True:
            tag = region(fnt, cursor, 1)[0]
            cursor += 1
            if tag == 0:
                break
            length = tag & 127
            if not length:
                raise ValueError('empty filename')
            name = region(fnt, cursor, length).decode('ascii')
            cursor += length
            if name in ('.', '..') or '/' in name or '\\' in name:
                raise ValueError('unsafe filename')
            path = prefix + name
            if tag & 128:
                child = u16(fnt, cursor)
                cursor += 2
                walk(child, path + '/')
            else:
                start, end = struct.unpack('<II', region(fat, file_id * 8, 8))
                region(image, start, end - start)
                if path in files:
                    raise ValueError('duplicate path')
                files[path] = (start, end)
                file_id += 1
    walk(0xF000, '')
    return files


def decompress(data):
    if data[:1] != b'\x10':
        return data
    size = int.from_bytes(region(data, 1, 3), 'little')
    if size > 16_000_000:
        raise ValueError('archive exceeds decompression budget')
    out = bytearray()
    pos = 4
    while len(out) < size:
        flags = region(data, pos, 1)[0]
        pos += 1
        for bit in range(7, -1, -1):
            if len(out) == size:
                break
            if flags & (1 << bit):
                a, b = region(data, pos, 2)
                pos += 2
                length, distance = (a >> 4) + 3, ((a & 15) << 8 | b) + 1
                if distance > len(out) or len(out) + length > size:
                    raise ValueError('invalid LZ10 backreference')
                for _ in range(length):
                    out.append(out[-distance])
            else:
                out.extend(region(data, pos, 1))
                pos += 1
    return bytes(out)


def narc(data):
    if data[:4] != b'NARC' or u32(data, 8) != len(data):
        raise ValueError('invalid NARC')
    blocks = {}
    cursor = u16(data, 12)
    for _ in range(u16(data, 14)):
        signature = region(data, cursor, 4)
        size = u32(data, cursor + 4)
        if size < 8 or signature in blocks:
            raise ValueError('invalid NARC block')
        blocks[signature] = region(data, cursor + 8, size - 8)
        cursor += size
    if cursor != len(data):
        raise ValueError('NARC trailing data')
    allocations = blocks[b'BTAF']
    count = u16(allocations, 0)
    if len(allocations) != 4 + count * 8:
        raise ValueError('NARC file count mismatch')
    return blocks[b'BTNF'], allocations[4:], blocks[b'GMIF']


def decode_kart(raw):
    if len(raw) != 0x98:
        raise ValueError('kart record must be 0x98 bytes')
    fields = {}
    for offset, name in [(0, 'collision_sphere_size'), (4, 'collision_sphere_z_offset'),
                         (8, 'unknown_08'), (16, 'max_speed'), (20, 'base_acceleration'),
                         (24, 'unknown_18'), (28, 'unknown_1c'),
                         (32, 'drift_base_acceleration'), (36, 'unknown_24'),
                         (40, 'unknown_28'), (44, 'deceleration'),
                         (52, 'drift_turning_compensation')]:
        fields[name + '_raw'] = struct.unpack_from('<i', raw, offset)[0]
    for offset, name in [(12, 'weight'), (14, 'drift_boost_time'), (48, 'handling'), (50, 'drift')]:
        fields[name + '_raw'] = struct.unpack_from('<h', raw, offset)[0]
    fields['collision_velocity_multipliers_raw'] = list(struct.unpack_from('<12i', raw, 0x38))
    fields['collision_speed_multipliers_raw'] = list(struct.unpack_from('<12i', raw, 0x68))
    return fields


def sync():
    rom = ROOT / 'local/roms/Mario Kart DS.nds'
    image = rom.read_bytes()
    digest = hashlib.sha256(image).hexdigest()
    if digest != ROM_HASH:
        raise ValueError('ROM identity differs from pinned AMCE revision 0')
    fnt = region(image, u32(image, 0x40), u32(image, 0x44))
    fat = region(image, u32(image, 0x48), u32(image, 0x4C))
    files = filesystem(fnt, fat, image)
    candidates = [p for p in files if p.lower().endswith('/kartmodelmaina.carc')]
    if len(candidates) != 1:
        raise ValueError(f'expected one active KartModelMainA.carc: {candidates}')
    archive_path = candidates[0]
    start, end = files[archive_path]
    names, allocations, archive_image = narc(decompress(image[start:end]))
    entries = filesystem(names, allocations, archive_image)
    output = ROOT / 'local/parameters'
    tables = {}
    for filename, stride in [('kartphysicalparam.bin', 0x98), ('charphysicalparam.bin', 8)]:
        matches = [p for p in entries if p.split('/')[-1] == filename]
        if len(matches) != 1:
            raise ValueError(f'expected one {filename}')
        path = matches[0]
        begin, finish = entries[path]
        payload = archive_image[begin:finish]
        if not payload or len(payload) % stride:
            raise ValueError(f'invalid table size: {filename}')
        records = []
        for index in range(len(payload) // stride):
            raw = payload[index * stride:(index + 1) * stride]
            record = {'id': index, 'offset': index * stride,
                      'sha256': hashlib.sha256(raw).hexdigest(), 'raw_hex': raw.hex(),
                      'status': 'extracted; runtime behavior unverified'}
            if stride == 8:
                record['name'] = CHARACTERS[index] if index < len(CHARACTERS) else None
                record['name_status'] = 'upstream enum order; AMCE runtime mapping unverified'
                record['fields'] = dict(zip(['unknown_00_raw', 'weight_raw'], struct.unpack('<ii', raw)))
            else:
                record['name'] = None
                record['fields'] = decode_kart(raw)
            records.append(record)
        tables[filename] = {'archive': archive_path, 'entry': path, 'stride': stride,
                            'sha256': hashlib.sha256(payload).hexdigest(), 'records': records,
                            'payload': payload}
    # Parse and validate completely before writing; output only small selected tables.
    projected = sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
    encoded = {}
    for filename, table in tables.items():
        encoded[filename + '.json'] = json.dumps({k: v for k, v in table.items() if k != 'payload'}, indent=2) + '\n'
    estimate = sum(len(t['payload']) for t in tables.values()) + sum(len(v.encode()) for v in encoded.values())
    if projected + estimate >= 199_000_000:
        raise ValueError('insufficient workspace headroom')
    output.mkdir(exist_ok=True)
    for filename, table in tables.items():
        (output / filename).write_bytes(table['payload'])
        (output / (filename + '.json')).write_text(encoded[filename + '.json'], encoding='utf-8')
        print(f"{filename}: {len(table['records'])} records, {len(table['payload'])} bytes")
    manifest = {'rom_sha256': digest, 'schema': 1,
                'layout_source': 'HaroohiePals/MKDS-decomp-headers/race/drivers/physicalParams.h',
                'layout_commit': '2d089194e146650406f6c257914ec397d35c8de7',
                'runtime_verified': False}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    sync()
