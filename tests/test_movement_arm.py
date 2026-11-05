"""Known-result checks for the expanded offline ARM/math-device boundary."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from rom_code import ROOT
from validate_movement import MovementReference


@unittest.skipUnless((ROOT / 'local/roms/Mario Kart DS.nds').exists(), 'requires pinned local ROM/capture')
class MovementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = MovementReference()

    def test_normalization_threshold_preserves_previous_direction(self):
        for value in (0, 1, 2, 3):
            self.assertEqual(self.ref.normalize((value, 0, 0), (11, 22, 33), 4096),
                             [value, 0, 0, 11, 22, 33, 0])
        self.assertEqual(self.ref.normalize((4, 0, 0), (11, 22, 33), 4096),
                         [4, 0, 0, 4096, 0, 0, 4])

    def test_magnitude_clamp_and_negative_direction(self):
        self.assertEqual(self.ref.normalize((53249, 0, 0), (0, 0, 0), 4096),
                         [53248, 0, 0, 4096, 0, 0, 53248])
        self.assertEqual(self.ref.normalize((-4096, 0, 0), (0, 0, 0), 4096),
                         [-4096, 0, 0, -4096, 0, 0, 4096])

    def test_grounded_cross_product_and_airborne_copy(self):
        args = (4096, 8192, 16, (4096, 0, 0), (0, 4096, 0), (7, 8, 9))
        self.assertEqual(self.ref.fraction_direction(*args), [2048, 4096, 0, 0, 4096])
        self.assertEqual(self.ref.fraction_direction(4096, 8192, 0, *args[3:]), [2048, 4096, 7, 8, 9])

    def test_cap_override_priority(self):
        self.assertEqual(self.ref.target((30720, 2000, 3000, 4000, 12345, 0x2000, 0, 0)), [30720, 4096])
        self.assertEqual(self.ref.target((30720, 2000, 3000, 4000, 12345, 0x2000, 0x10000000, 0)), [12345, 4096])

    def test_math_devices_use_integer_64_bit_results(self):
        a = self.ref.arm
        a.reset()
        a.store(0x04000280, 2, 2, True)
        a.store(0x04000290, -(1 << 55), 8, True)
        a.store(0x04000298, 1 << 33, 8, True)
        self.assertEqual(a.number(0x040002a0, 8, True), -(1 << 22))
        a.store(0x040002b0, 1, 2, True)
        a.store(0x040002b8, (1 << 64) - 1, 8, True)
        self.assertEqual(a.number(0x040002b4), 0xffffffff)

    def test_course_list_load_updates_its_base_register(self):
        a = self.ref.arm
        a.reset()
        a.store(0x03008002, 123, 2)
        a.reg['r1'] = 0x03008000
        # Actual course-triangle iterator instruction: ldrh r0,[r1,#2]!
        a.run(0x01ffed94, stop_at=0x01ffed98)
        self.assertEqual(a.reg['r0'], 123)
        self.assertEqual(a.reg['r1'], 0x03008002)

    def test_register_shift_uses_low_byte_and_large_shift_rules(self):
        a = self.ref.arm
        for amount, expected in ((0, 3), (1, 7), (32, 1), (33, 1), (256, 3)):
            a.reset(); a.reg['r8'] = 1; a.reg['r7'] = 3
            # Actual octree-index instruction: orr r0,r8,r7,lsl r0
            a.run(0x01ffe108, amount, stop_at=0x01ffe10c)
            self.assertEqual(a.reg['r0'], expected)

    def test_arm_to_thumb_matrix_helper_and_return(self):
        a = self.ref.arm
        a.reset()
        destination = 0x03008000
        a.reg['r1'] = 0; a.reg['r2'] = 4096
        # Original ARM BLX to a Thumb SDK rotation-matrix constructor.
        a.run(0x02070508, destination, stop_at=0x0207050c)
        self.assertFalse(a.thumb)
        self.assertEqual([a.number(destination + 4 * i, sign=True) for i in range(12)],
                         [4096, 0, 0, 0, 4096, 0, 0, 0, 4096, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
