"""Synthetic binary tests; no ROM or extracted Nintendo data required."""
import importlib.util
from pathlib import Path
import struct
import unittest

spec = importlib.util.spec_from_file_location('sync_parameters', Path(__file__).resolve().parents[1] / 'tools/sync_parameters.py')
sync = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync)


class BinaryTests(unittest.TestCase):
    def test_lz_literals_and_overlapping_copy(self):
        self.assertEqual(sync.decompress(bytes.fromhex('10060000104142430002')), b'ABCABC')
        self.assertEqual(sync.decompress(bytes.fromhex('1006000040412000')), b'AAAAAA')

    def test_invalid_lz(self):
        for data in [bytes.fromhex('10030000800000'), bytes.fromhex('1003000000')]:
            with self.assertRaises(ValueError):
                sync.decompress(data)

    def test_filesystem(self):
        fnt = struct.pack('<IHH', 8, 0, 1) + b'\x01a\x00'
        fat = struct.pack('<II', 1, 3)
        self.assertEqual(sync.filesystem(fnt, fat, b'1234'), {'a': (1, 3)})
        with self.assertRaises(ValueError):
            sync.filesystem(fnt, struct.pack('<II', 1, 7), b'1234')

    def test_narc(self):
        fnt = struct.pack('<IHH', 8, 0, 1) + b'\x01a\x00'
        fat = struct.pack('<HHII', 1, 0, 0, 3)
        blocks = b''.join(tag + struct.pack('<I', len(body) + 8) + body
                          for tag, body in [(b'BTAF', fat), (b'BTNF', fnt), (b'GMIF', b'abc')])
        data = b'NARC' + struct.pack('<HHIHH', 0xfeff, 0x100, len(blocks) + 16, 16, 3) + blocks
        names, allocations, image = sync.narc(data)
        self.assertEqual(sync.filesystem(names, allocations, image), {'a': (0, 3)})
        with self.assertRaises(ValueError):
            sync.narc(data[:-1])

    def test_kart_width_and_signedness(self):
        raw = bytearray(0x98)
        struct.pack_into('<h', raw, 12, -2)
        struct.pack_into('<i', raw, 52, -65537)
        decoded = sync.decode_kart(raw)
        self.assertEqual(decoded['weight_raw'], -2)
        self.assertEqual(decoded['drift_turning_compensation_raw'], -65537)
        with self.assertRaises(ValueError):
            sync.decode_kart(raw[:-1])


if __name__ == '__main__':
    unittest.main()
