"""Synthetic pointer graph checks, independent of ROM data and emulator."""
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import validate_baseline as baseline


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.ram = bytearray(0x400000)
        self.karts = bytes((i * 7 + i // 256) % 256 for i in range(7600))
        self.characters = struct.pack('<ii', 3891, 2048) + bytes(range(8, 104))
        self.put(0x02010000, self.karts)
        self.put(0x02014000, self.characters)
        self.put(0x02003000, self.karts[:152])
        self.put(0x02004000, self.characters[:8])
        self.put(0x02002000, struct.pack('<5I', 0x02003000, 0x02004000, 30720, 0x02010000, 0x02014000))
        self.put(0x02001000 + 0x2cc, struct.pack('<II', 0x02003000, 0x02004000))
        self.put(0x02001000 + 0x590, struct.pack('<I', 0x02005000))
        self.put(0x02005000, struct.pack('<II', 0, 0))

    def put(self, address, value):
        self.ram[address - baseline.BASE:address - baseline.BASE + len(value)] = value

    def test_pointer_chain_and_identity(self):
        result = baseline.analyze(self.ram, self.karts, self.characters)
        self.assertEqual(result['driver_address'], '0x2001000')
        self.assertTrue(result['character_record_exact'])
        self.assertEqual(result['kart_field_differences'], {})

    def test_wrong_selected_id_rejected(self):
        self.put(0x02005004, struct.pack('<I', 1))
        with self.assertRaises(ValueError):
            baseline.analyze(self.ram, self.karts, self.characters)

    def test_driver_id_is_at_74_not_78(self):
        self.put(0x02001000 + 0x78, struct.pack('<I', 123))
        self.assertEqual(baseline.analyze(self.ram, self.karts, self.characters)['driver_address'], '0x2001000')
        self.put(0x02001000 + 0x74, struct.pack('<H', 1))
        with self.assertRaises(ValueError):
            baseline.analyze(self.ram, self.karts, self.characters)

    def test_invalid_pointer_rejected(self):
        self.put(0x02001000 + 0x590, struct.pack('<I', 0xffffffff))
        with self.assertRaises(ValueError):
            baseline.analyze(self.ram, self.karts, self.characters)

    def test_ambiguous_driver_rejected(self):
        self.put(0x02006000 + 0x2cc, struct.pack('<II', 0x02003000, 0x02004000))
        self.put(0x02006000 + 0x590, struct.pack('<I', 0x02005000))
        with self.assertRaises(ValueError):
            baseline.analyze(self.ram, self.karts, self.characters)


if __name__ == '__main__':
    unittest.main()
