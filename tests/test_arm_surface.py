"""Optional offline execution checks using the ignored, pinned RAM capture."""
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from audit_sync import SurfaceInstructions

CAPTURE = Path(__file__).resolve().parents[1] / 'local/validation/mario-standard-mr-figure8-01/arm9-main-ram.bin'


@unittest.skipUnless(CAPTURE.exists(), 'requires local research capture')
class InstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.arm = SurfaceInstructions(CAPTURE.read_bytes())

    def test_threshold_signed_rounding_and_untouched_bytes(self):
        original = bytearray([0x59] * 152)
        values = [4096, 4097, 4095, 1, -1, -3, 0, 2048, 4096, 4096, 4096, 4096]
        struct.pack_into('<12i', original, 0x68, *values)
        actual = self.arm.run(original, struct.pack('<ii', 2048, 0))
        self.assertEqual(actual[:0x68], original[:0x68])
        self.assertEqual(struct.unpack_from('<12i', actual, 0x68),
                         (4096, 4097, 2048, 1, 0, -1, 0, 1024, 4096, 4096, 4096, 4096))

    def test_wide_product_carry_and_truncation(self):
        original = bytearray(152)
        struct.pack_into('<i', original, 0x68, -2147483648)
        actual = self.arm.run(original, struct.pack('<ii', -2147483648, 0))
        self.assertEqual(struct.unpack_from('<I', actual, 0x68)[0], 0)

    def test_wrong_instruction_bytes_rejected(self):
        ram = bytearray(CAPTURE.read_bytes())
        ram[0x72774] ^= 1
        with self.assertRaises(ValueError):
            SurfaceInstructions(ram)


if __name__ == '__main__':
    unittest.main()
