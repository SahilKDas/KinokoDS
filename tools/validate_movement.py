"""Compare recovered movement fragments with pinned ARM instructions offline.

No generated input is a live race trace. Direction production, magnitude
normalization, collision correction and frame cadence remain outside this test.
"""
import hashlib
import json
import random
import struct
import subprocess
from arm_offline import Arm, DRIVER, STACK, KART, signed
from rom_code import ROOT


class MovementReference:
    def __init__(self):
        self.arm = Arm()

    def start(self):
        a = self.arm
        a.reset()
        # Nonzero sentinels ensure unrelated fields are preserved.
        a.put(DRIVER, bytes((i * 17 + 3) & 255 for i in range(0x5a8)))
        return a

    def vector(self, offset, values):
        for i, value in enumerate(values): self.arm.store(DRIVER + offset + i * 4, value)

    def result_vector(self, offset):
        return tuple(self.arm.number(DRIVER + offset + i * 4, sign=True) for i in range(3))

    def unchanged(self, before, allowed, external=()):
        a = self.arm
        for offset in range(len(before)):
            if not any(start <= offset < end for start, end in allowed):
                if a.read(DRIVER + offset, 1)[0] != before[offset]:
                    raise ValueError(f'unexpected changed driver byte +0x{offset:x}')
        for pc, address, length, _ in a.writes:
            for byte in range(address, address + length):
                if DRIVER <= byte < DRIVER + 0x5a8:
                    if not any(start <= byte - DRIVER < end for start, end in allowed):
                        raise ValueError(f'unexpected driver write {pc:08x} -> {byte:08x}')
                elif not STACK - 256 <= byte < STACK + 256 and not 0x04000280 <= byte < 0x040002c0 and not any(start <= byte < end for start, end in external):
                    raise ValueError(f'unexpected external write {pc:08x} -> {byte:08x}')

    def cap(self, current, target):
        a = self.start()
        a.store(DRIVER + 0xd0, current); a.store(DRIVER + 0xcc, target)
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffbe04)
        self.unchanged(before, [(0xd0, 0xd4)])
        return [a.number(DRIVER + 0xd0, sign=True)]

    def target(self, values):
        base, dc, d4, d8, override, flags7c, flags48, flags4c = values
        a = self.start()
        a.store(DRIVER + 0x2cc, KART); a.store(KART + 16, base)
        for off, value in ((0xdc, dc), (0xd4, d4), (0xd8, d8), (0x4c4, override),
                           (0x7c, flags7c), (0x48, flags48), (0x4c, flags4c)):
            a.store(DRIVER + off, value)
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffbe70)
        self.unchanged(before, [(0xcc, 0xd0), (0xdc, 0xe0)])
        return [a.number(DRIVER + 0xcc, sign=True), a.number(DRIVER + 0xdc, sign=True)]

    def penalty(self, scalar, mode, flags, field, coefficient):
        a = self.start()
        a.store(DRIVER + 0x180, mode); a.store(DRIVER + 0x44, flags)
        a.store(DRIVER + 0x2d4, field); a.store(0x021654d8, coefficient)
        a.store(STACK + 128, scalar); a.reg['r1'] = DRIVER
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffb930, STACK + 128)
        self.unchanged(before, [])
        return [a.number(STACK + 128, sign=True)]

    def fraction(self, magnitude, cap):
        a = self.start()
        a.store(DRIVER + 0x2a4, magnitude); a.store(DRIVER + 0xd0, cap)
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffbd9c, stop_at=0x01ffbdb0)
        # The intervening direction helper is excluded, not replaced by guessed
        # behavior. It does not belong to the division/readback fragment.
        a.run(0x01ffbddc)
        self.unchanged(before, [(0x2a0, 0x2a8)])
        return [a.number(DRIVER + 0x2a0, sign=True), a.number(DRIVER + 0x2a4, sign=True)]

    def fraction_direction(self, magnitude, cap, flags, basis, normal, source):
        a = self.start()
        for off, value in ((0x2a4, magnitude), (0xd0, cap), (0x44, flags)): a.store(DRIVER + off, value)
        for off, vec in ((0x120, basis), (0x244, normal), (0x138, source)): self.vector(off, vec)
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffbd9c)
        self.unchanged(before, [(0x2a0, 0x2a8), (0x278, 0x284)])
        return [a.number(DRIVER + 0x2a0, sign=True), a.number(DRIVER + 0x2a4, sign=True)] + list(self.result_vector(0x278))

    def blend(self, direction, target, flags44, flags4c, factor):
        a = self.start()
        self.vector(0x68, direction); self.vector(0x50, target)
        for off, value in ((0x44, flags44), (0x4c, flags4c), (0x240, factor)): a.store(DRIVER + off, value)
        a.reg['r5'] = DRIVER
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffb5b8, stop_at=0x01ffb638)
        self.unchanged(before, [(0x68, 0x74)])
        return list(self.result_vector(0x68))

    def seed_displacement(self, row):
        a = self.start()
        scalar, d68, d50, mode, flags, count, v374, v260, v274, v268, v2f0, v1fc = row
        for off, value in ((0x180, mode), (0x44, flags), (0x380, count), (0x260, v260), (0x274, v274)):
            a.store(DRIVER + off, value)
        for off, vector in ((0x68, d68), (0x50, d50), (0x374, v374), (0x268, v268), (0x2f0, v2f0), (0x1fc, v1fc)):
            self.vector(off, vector)
        a.store(STACK + 4, scalar)
        a.reg['r5'] = DRIVER
        return a

    def displacement(self, row):
        a = self.seed_displacement(row)
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffb638, stop_at=0x01ffb754)
        self.unchanged(before, [(0xa4, 0xb0), (0x5c, 0x68)])
        return list(self.result_vector(0xa4) + self.result_vector(0x5c))

    def tail(self, values):
        row, position, direction, flags, field, scale, acc_a, acc_b, c8, global_scale, global_value, field4d4 = values
        a = self.seed_displacement(row)
        self.vector(0x80, position); self.vector(0xb0, direction)
        for off, value in ((0x7c, flags), (0x38c, field), (0x2b8, acc_a), (0x2bc, acc_b), (0xc8, c8)):
            a.store(DRIVER + off, value)
        a.store(STACK + 8, scale)
        a.store(0x0217ad0c, global_scale); a.store(0x0217ad10, global_value); a.store(DRIVER + 0x4d4, field4d4)
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffb638, stop_at=0x01ffb7f0)
        self.unchanged(before, [(0xa4, 0xbc), (0x5c, 0x68), (0x80, 0x8c),
                               (0x38c, 0x390), (0x2a4, 0x2a8), (0x44, 0x48), (0x2b8, 0x2c0), (0x4d4, 0x4d8)],
                       external=[(0x0217ad10, 0x0217ad14)])
        return (list(self.result_vector(0xa4) + self.result_vector(0x5c) + self.result_vector(0xb0))
            + [a.number(DRIVER + 0x2a4, sign=True)] + list(self.result_vector(0x80))
            + [a.number(DRIVER + 0x38c, sign=True), a.number(DRIVER + 0x44),
               a.number(DRIVER + 0x2b8, sign=True), a.number(DRIVER + 0x2bc, sign=True),
               a.number(0x0217ad10, sign=True), a.number(DRIVER + 0x4d4, sign=True)])

    def position(self, pos, delta, flags, field):
        a = self.start()
        self.vector(0x80, pos); self.vector(0xa4, delta)
        a.store(DRIVER + 0x7c, flags); a.store(DRIVER + 0x38c, field)
        a.reg['r5'] = DRIVER
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffb7cc, stop_at=0x01ffb7f0)
        self.unchanged(before, [(0x80, 0x8c), (0x38c, 0x390)])
        return list(self.result_vector(0x80)) + [a.number(DRIVER + 0x38c, sign=True)]

    def normalize(self, delta, direction, scale):
        a = self.start()
        self.vector(0xa4, delta); self.vector(0xb0, direction)
        a.reg['r1'] = scale & 0xffffffff
        before = a.read(DRIVER, 0x5a8)
        a.run(0x01ffae14)
        self.unchanged(before, [(0xa4, 0xbc), (0x2a4, 0x2a8)])
        return list(self.result_vector(0xa4) + self.result_vector(0xb0)) + [a.number(DRIVER + 0x2a4, sign=True)]


def flatten(values):
    for value in values:
        if isinstance(value, (tuple, list)): yield from flatten(value)
        else: yield value


def main():
    ref = MovementReference()
    commands, expected, cases = [], [], []
    counts = dict.fromkeys('CFDPNTBRGH', 0)

    def add(command, values, result, label=None):
        commands.append(command + ' ' + ' '.join(map(str, flatten(values))))
        expected.append(command + ' ' + ' '.join(map(str, result)))
        cases.append({'stage': command, 'input': values, 'label': label,
                      'instruction_tail': [hex(pc) for pc in ref.arm.trace],
                      'driver_writes': [w for w in ref.arm.writes if DRIVER <= w[1] < DRIVER + 0x5a8]})
        counts[command] += 1

    bounds = (-2147483648, -2147483647, -53249, -4097, -4096, -1, 0, 1, 4095, 4096,
              4097, 24575, 24576, 24577, 30719, 30720, 30721, 53248, 53249, 2147483647)
    for current in bounds:
        for target in bounds: add('C', (current, target), ref.cap(current, target))
    for magnitude in bounds:
        for cap in bounds: add('F', (magnitude, cap), ref.fraction(magnitude, cap))

    rng = random.Random(0x4d4b4453)
    random_word = lambda: signed(rng.getrandbits(32))
    vector = lambda: tuple(random_word() for _ in range(3))
    for flags in (0, 8, 16, 128, 144, 0xffffffff):
        for _ in range(100):
            args = (rng.choice(bounds), rng.choice(bounds), flags, vector(), vector(), vector())
            add('G', args, ref.fraction_direction(*args), 'complete-fraction-direction')
            args = (vector(), vector(), flags, rng.choice((0, 0x10000000, 0xffffffff)), rng.choice(bounds))
            add('H', args, ref.blend(*args), 'direction-blend-boundary')
    for flags7c in (0, 0x2000, 0x400000, 0x402000):
        for flags48 in (0, 0x20, 0x21, 0x400020, 0x20000020, 0x10000000, 0x10000021, 0xffffffff):
            for flags4c in (0, 0x40, 0x10000000, 0xffffffff):
                for base in (0, 21502, 26115, 30720, -1, 2147483647):
                    args = (base, 2867, 4095, 4097, 12345, flags7c, flags48, flags4c)
                    add('B', args, ref.target(args), 'cap-target-flag-matrix')
    for _ in range(200):
        args = tuple(random_word() for _ in range(5)) + tuple(rng.getrandbits(32) for _ in range(3))
        add('B', args, ref.target(args), 'cap-target-seeded')
    for scalar in (-2147483648, -1, 0, 12287, 12288, 12289, 30720, 2147483647):
        for mode in (0, 1, 6):
            for flags in (0, 8, 16, 24, 0xffffffff):
                for field in (-2147483648, -4096, -1, 0, 1, 4096, 2147483647):
                    args = (scalar, mode, flags, field, 0x1ec)
                    add('R', args, ref.penalty(*args), 'direction-penalty-boundary')
    for length in (0, 1, 2, 3, 4, 5, 4095, 4096, 4097, 53247, 53248, 53249, 2147483647, -2147483648):
        for scale in (-4097, -4096, -1, 0, 1, 4095, 4096, 4097, 2147483647, -2147483648):
            for delta in ((length, 0, 0), (length, length, length), (length, -1, 2)):
                args = (delta, (1234, -5678, 91011), scale)
                add('N', args, ref.normalize(*args), 'normalization-boundary')
    for _ in range(500):
        args = (vector(), vector(), random_word())
        add('N', args, ref.normalize(*args), 'normalization-seeded')
    for index in range(500):
        row = (rng.choice(bounds), vector(), vector(), rng.choice((0, 6, 7)),
               rng.choice((0, 0x10, 0xffffffff)), rng.choice((0, 5, 6, 0xffffffff)),
               vector(), random_word(), random_word(), vector(), vector(), vector())
        add('D', row, ref.displacement(row), f'seeded-boundary-{index}')
        args = (row, vector(), vector(), rng.choice((0, 1, 0x20, 0x21, 0xffffffff)),
                random_word(), rng.choice((0, 4096, -4096, 4097)), random_word(), random_word(), random_word(),
                random_word(), random_word(), random_word())
        add('T', args, ref.tail(args), f'connected-tail-{index}')
        args = (vector(), vector(), rng.choice((0, 0x20, 0xffffffff)), random_word())
        add('P', args, ref.position(*args))
    # Directed falling clamp and signed multiplication boundaries.
    for y in (-24577, -24576, -24575):
        for mode in (0, 6):
            for flags in (0, 16):
                for count in (5, 6):
                    row = (4096, (0, y, 0), (0, 4096, 0), mode, flags, count,
                           (0, 0, 0), 0, 0, (0, 0, 0), (0, 0, 0), (0, 0, 0))
                    add('D', row, ref.displacement(row), 'falling-clamp-boundary')

    # Actual captured driver fields are included without treating one snapshot
    # as a time series. Heap addresses come from the saved capture metadata.
    directory = ROOT / 'local/validation/mario-standard-mr-figure8-01'
    active = json.loads((directory / 'active-parameters.json').read_text())
    snapshot = (directory / 'arm9-main-ram.bin').read_bytes()
    driver = int(active['driver_address'], 16) - 0x02000000
    si = lambda off: struct.unpack_from('<i', snapshot, driver + off)[0]
    ui = lambda off: struct.unpack_from('<I', snapshot, driver + off)[0]
    sv = lambda off: struct.unpack_from('<3i', snapshot, driver + off)
    add('C', (si(0xd0), si(0xcc)), ref.cap(si(0xd0), si(0xcc)), 'captured-driver-fields')
    add('F', (si(0x2a4), si(0xd0)), ref.fraction(si(0x2a4), si(0xd0)), 'captured-driver-fields')
    add('P', (sv(0x80), sv(0xa4), ui(0x7c), si(0x38c)),
        ref.position(sv(0x80), sv(0xa4), ui(0x7c), si(0x38c)), 'captured-driver-fields')
    args = (sv(0xa4), sv(0xb0), si(0x3f8))
    add('N', args, ref.normalize(*args), 'captured-driver-fields')
    row = (si(0x2a8), sv(0x68), sv(0x50), ui(0x180), ui(0x44), ui(0x380),
           sv(0x374), si(0x260), si(0x274), sv(0x268), sv(0x2f0), sv(0x1fc))
    args = (row, sv(0x80), sv(0xb0), ui(0x7c), si(0x38c), si(0x3f8), si(0x2b8), si(0x2bc), si(0xc8),
            struct.unpack_from('<i', snapshot, 0x17ad0c)[0], struct.unpack_from('<i', snapshot, 0x17ad10)[0], si(0x4d4))
    add('T', args, ref.tail(args), 'captured-fields')
    # 256 chained position writes check accumulated integer/overflow behavior.
    pos, delta = sv(0x80), (237, -1, -4097)
    for step in range(256):
        args = (pos, delta, 0, 4096)
        result = ref.position(*args)
        add('P', args, result, f'repeated-position-{step}')
        pos = tuple(result[:3])

    output = subprocess.check_output([str(ROOT / 'build/kinoko_movement_runner.exe')],
        input='\n'.join(commands) + '\n', text=True).splitlines()
    target = ROOT / 'local/validation/frame-inspection'
    target.mkdir(parents=True, exist_ok=True)
    if len(output) != len(expected): raise ValueError('movement output count mismatch')
    field_names = {'C': ['driver+0xd0'], 'F': ['driver+0x2a0', 'driver+0x2a4'],
        'D': [f'driver+0x{off:x}' for off in (0xa4, 0xa8, 0xac, 0x5c, 0x60, 0x64)],
        'P': [f'driver+0x{off:x}' for off in (0x80, 0x84, 0x88, 0x38c)],
        'N': [f'driver+0x{off:x}' for off in (0xa4, 0xa8, 0xac, 0xb0, 0xb4, 0xb8, 0x2a4)]}
    field_names['T'] = [f'driver+0x{off:x}' for off in
        (0xa4, 0xa8, 0xac, 0x5c, 0x60, 0x64, 0xb0, 0xb4, 0xb8, 0x2a4, 0x80, 0x84, 0x88, 0x38c, 0x44, 0x2b8, 0x2bc)] + ['global+0x0217ad10', 'driver+0x4d4']
    field_names['B'] = ['driver+0xcc', 'driver+0xdc']
    field_names['R'] = ['local movement scalar']
    field_names['G'] = [f'driver+0x{off:x}' for off in (0x2a0, 0x2a4, 0x278, 0x27c, 0x280)]
    field_names['H'] = [f'driver+0x{off:x}' for off in (0x68, 0x6c, 0x70)]
    for index, (want, actual) in enumerate(zip(expected, output)):
        if want != actual:
            diff = next((i for i, pair in enumerate(zip(want.split()[1:], actual.split()[1:])) if pair[0] != pair[1]), None)
            failure = dict(cases[index], index=index, command=commands[index], expected_arm=want, actual_cpp=actual,
                first_field=field_names[cases[index]['stage']][diff] if diff is not None else 'output format')
            (target / 'movement-failure.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8')
            raise ValueError(f'first movement mismatch: {failure}')
    report = {'cases': counts, 'total': len(commands), 'repeated_position_steps': 256,
        'ram_sha256': hashlib.sha256(snapshot).hexdigest(),
        'scope': 'cap production/transition, fraction/direction, blend/penalty, displacement assembly, normalization/magnitude, connected tail/position',
        'live_trace_captured': False, 'full_frame_verified': False,
        'unaccounted_driver_writes': 0}
    (target / 'movement-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (target / 'movement-failure.json').unlink(missing_ok=True)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
