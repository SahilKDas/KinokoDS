"""Recover pinned ARM9 and autoload code in memory. No emulator or downloads."""
from pathlib import Path
import hashlib
import struct
from sync_parameters import ROM_HASH

ROOT = Path(__file__).resolve().parents[1]


def backward_lz(data):
    if len(data) < 8:
        raise ValueError('short BLZ image')
    packed, extra = struct.unpack_from('<II', data, len(data) - 8)
    header, compressed = packed >> 24, packed & 0xffffff
    if not 8 <= header <= compressed <= len(data) or len(data) + extra > 4_000_000:
        raise ValueError('invalid BLZ dimensions')
    stop, src = len(data) - compressed, len(data) - header
    out = bytearray(data) + bytearray(extra)
    dst = len(out)
    while src > stop and dst > stop:
        src -= 1
        flags = out[src]
        for bit in range(7, -1, -1):
            if src <= stop or dst <= stop:
                break
            if flags & (1 << bit):
                if src - 2 < stop:
                    raise ValueError('truncated BLZ token')
                src -= 1
                first = out[src]
                src -= 1
                second = out[src]
                length, distance = (first >> 4) + 3, ((first & 15) << 8 | second) + 3
                if dst - length < stop:
                    raise ValueError('BLZ output overrun')
                for _ in range(length):
                    dst -= 1
                    if dst + distance >= len(out):
                        raise ValueError('invalid BLZ backreference')
                    out[dst] = out[dst + distance]
            else:
                src -= 1
                dst -= 1
                out[dst] = out[src]
    if dst != stop or src != stop:
        raise ValueError('incomplete BLZ decode')
    return bytes(out)


class CodeImage:
    def __init__(self):
        rom = (ROOT / 'local/roms/Mario Kart DS.nds').read_bytes()
        if hashlib.sha256(rom).hexdigest() != ROM_HASH:
            raise ValueError('unrecognized ROM')
        offset, _, base, size = struct.unpack_from('<4I', rom, 0x20)
        self.main = backward_lz(rom[offset:offset + size])
        magic = bytes.fromhex('2106c0dedec00621')
        params = self.main.index(magic) - 28
        start, end, data = struct.unpack_from('<III', self.main, params)
        self.segments = [(base, self.main)]
        cursor = data - base
        for off in range(start - base, end - base, 12):
            target, length, _ = struct.unpack_from('<III', self.main, off)
            self.segments.insert(0, (target, self.main[cursor:cursor + length]))
            cursor += length
        ram = (ROOT / 'local/validation/mario-standard-mr-figure8-01/arm9-main-ram.bin').read_bytes()
        if self.main[0x726bc:0x727c8] != ram[0x726bc:0x727c8]:
            raise ValueError('ROM/RAM initialization mismatch')

    def read(self, address, size):
        for base, data in self.segments:
            if base <= address and address + size <= base + len(data):
                return data[address - base:address - base + size]
        raise ValueError(f'code address not mapped: {address:08x}')
