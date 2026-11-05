"""Local-only regression tests for BLZ, relocation, ARM execution and SDK math."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rom_code import CodeImage, backward_lz, ROOT
from arm_offline import Arm, signed, trunc_div
from validate_longitudinal import Reference


class DecodeTests(unittest.TestCase):
    def test_bad_blz(self):
        for data in (b'', bytes(8), b'12345678'):
            with self.assertRaises(ValueError): backward_lz(data)


@unittest.skipUnless((ROOT / 'local/roms/Mario Kart DS.nds').exists(), 'requires pinned local ROM/capture')
class OfflineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = Reference()

    def test_autoload_and_snapshot_code(self):
        code = self.ref.arm.code
        self.assertEqual(len(code.main), 0x1773b8)
        self.assertEqual(len(next(data for base, data in code.segments if base == 0x01ff8000)), 0x7fa0)
        self.assertEqual(code.read(0x020726bc, 0x10c), self.ref.arm.ram[0x726bc:0x727c8])

    def test_sdk_signed_division_and_stack(self):
        a = self.ref.arm
        for numerator, denominator in ((1, 3), (-1, 3), (1, -3), (-1, -3), (139, 819),
                                       (-2147483648, -1), (2147483647, 1), (1, 0), (-1, 0)):
            a.reset()
            a.reg['r1'] = denominator & 0xffffffff
            stack = a.reg['sp']
            actual = a.run(0x02147f34, numerator & 0xffffffff)
            wide = numerator * 4294967296
            quotient = trunc_div(wide, denominator) if denominator else (1 if wide < 0 else -1)
            if quotient == (1 << 63): quotient = -(1 << 63)
            expected = (((quotient & ((1 << 64) - 1)) + 0x80000) >> 20) & 0xffffffff
            self.assertEqual(actual, expected)
            self.assertEqual(a.reg['sp'], stack)

    def test_threshold_endpoint_is_quantized(self):
        p = self.ref.prepare(0, 0, 0, 2)
        self.assertEqual(self.ref.step(p, 0, False, True, 2047, 30720)[0], 237)
        self.assertEqual(self.ref.step(p, 0, False, True, 2867, 30720)[0], 99)
        self.assertEqual(self.ref.step(p, 0, False, True, 2868, 30720)[0], 98)

    def test_mode_initialization_branches(self):
        import struct
        for engine, speed, drift in ((0, 21502, 180), (1, 26115, 200), (2, 30720, 220)):
            p = self.ref.prepare(0, 0, 0, engine)
            self.assertEqual(struct.unpack_from('<i', p[3], 16)[0], speed)
            self.assertEqual(struct.unpack_from('<h', p[3], 50)[0], drift)
        self.assertEqual(self.ref.prepare(12, 49, 2, 0)[:2], (0, 0))


if __name__ == '__main__':
    unittest.main()
