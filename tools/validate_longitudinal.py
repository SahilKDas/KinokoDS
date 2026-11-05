"""Differential validation of recovered AMCE scalar routines, entirely offline."""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
from arm_offline import Arm, DRIVER, KART, CHARACTER, PHYSP, CONFIG, STATUS, signed
from rom_code import ROOT
from audit_sync import original_tables


class Reference:
    def __init__(self):
        self.arm = Arm()
        tables = original_tables()
        self.karts = tables['kartphysicalparam.bin']
        self.characters = tables['charphysicalparam.bin']

    def prepare(self, character, kart, scene, engine):
        a = self.arm
        a.setup(bytes(152), bytes(8))
        a.store(PHYSP + 12, 0x0238adc8)
        a.store(PHYSP + 16, 0x02386568)
        a.store(CONFIG + 8, 2 if scene == 1 else 1)
        a.store(CONFIG + 16, engine)
        a.store(STATUS + 0x38, int(scene == 2))
        a.reg.update({'r1': kart, 'r2': character})
        a.run(0x0208aea8, 0)
        ki = (a.copies[0][0] - 0x0238adc8) // 152
        ci = (a.copies[1][0] - 0x02386568) // 8
        a.run(0x020726bc)
        expected_driver = bytearray(0x5a8)
        struct.pack_into('<II', expected_driver, 0x2cc, KART, CHARACTER)
        struct.pack_into('<I', expected_driver, 0x3f4, a.number(DRIVER + 0x3f4))
        if a.read(DRIVER, 0x5a8) != expected_driver:
            raise ValueError('unaccounted initialization driver write')
        return ki, ci, a.number(DRIVER + 0x3f4, sign=True), a.read(KART, 152), a.read(CHARACTER, 8)

    def step(self, prepared, speed, coast, throttle, fraction, cap, brake=False):
        a = self.arm
        a.setup(prepared[3], prepared[4])
        a.store(DRIVER + 0x44, 16 | (1024 if coast else 0))
        a.store(DRIVER + 0x2a8, speed)
        a.store(DRIVER + 0x2a0, fraction)
        a.store(DRIVER + 0xd0, cap)
        a.store(DRIVER + 0x38c, 4096)
        a.store(DRIVER + 0x394, 4096)
        a.store(0x0217560a, int(throttle) | (2 if brake else 0), 2)
        before = bytearray(a.read(DRIVER, 0x5a8))
        # Actual input mapping, ordinary speed update, drag, then cap stage.
        a.run(0x01ffc5a0)
        a.run(0x01ffba68)
        a.run(0x01ffb9e0)
        returned = a.run(0x01ffaf18)
        for off in (0x44, 0x48, 0x2a8):
            before[off:off + 4] = a.read(DRIVER + off, 4)
        if bytes(before) != a.read(DRIVER, 0x5a8):
            raise ValueError('unaccounted longitudinal driver write')
        value = a.number(DRIVER + 0x2a8, sign=True)
        if signed(returned) != value:
            raise ValueError('cap result differs from stored speed on ordinary path')
        return value, bool(a.number(DRIVER + 0x44) & 1024)


def main():
    ref = Reference()
    commands, expected, labels = [], [], []
    prepared = {}

    def add_prepare(ch, kart, scene, engine):
        key = ch, kart, scene, engine
        result = ref.prepare(*key)
        prepared[key] = result
        commands.append(f'P {ch} {kart} {scene} {engine}')
        ki, ci, field, k, c = result
        expected.append(f'P {ki} {ci} {field} {k.hex()} {c.hex()}')
        labels.append({'stage': 'initialization', 'character': ch, 'kart': kart, 'scene': scene, 'engine': engine})

    print('Checking all ordinary initialization pairs and mode branches...', flush=True)
    for engine in (0, 1, 2):
        for ch in range(13):
            for kart in range(50): add_prepare(ch, kart, 0, engine)
            add_prepare(ch, 0, 1, engine)
            add_prepare(ch, 49, 2, engine)
    for scene in range(3): add_prepare(0, 0, scene, 99)
    initialization_count = len(commands)

    def add_step(ch, kart, engine, speed, coast, throttle, fraction, cap, sequence=None):
        key = ch, kart, 0, engine
        result = ref.step(prepared[key], speed, coast, throttle, fraction, cap)
        commands.append(f'L {ch} {kart} 0 {engine} {speed} {int(coast)} {int(throttle)} {fraction} {cap}')
        expected.append(f'L {result[0]} {int(result[1])}')
        labels.append({'stage': 'longitudinal', 'character': ch, 'kart': kart, 'engine': engine,
                       'speed': speed, 'coast': coast, 'throttle': throttle, 'fraction': fraction,
                       'cap': cap, 'sequence': sequence})
        return result

    print('Checking threshold/cap/input boundaries...', flush=True)
    for engine in (0, 1, 2):
        cap = struct.unpack_from('<i', prepared[(0, 0, 0, engine)][3], 16)[0]
        for fraction in (0, 2047, 2048, 2049, 2866, 2867, 2868, 4095, 4096):
            for speed in (0, 1, 409, 410, 411, cap - 1, cap, cap + 1, 2147483647):
                for coast in (False, True):
                    for throttle in (False, True): add_step(0, 0, engine, speed, coast, throttle, fraction, cap)
    for ch in range(13):
        for kart in range(50):
            cap = struct.unpack_from('<i', prepared[(ch, kart, 0, 2)][3], 16)[0]
            add_step(ch, kart, 2, 0, False, True, 0, cap)
            add_step(ch, kart, 2, cap, True, True, 4096, cap)

    print('Checking repeated scalar sequences (not full game frames)...', flush=True)
    for engine in (0, 1, 2):
        cap = struct.unpack_from('<i', prepared[(0, 0, 0, engine)][3], 16)[0]
        speed, coast = 0, False
        for tick in range(850):
            throttle = tick < 250 or tick >= 600
            # Explicit idealized external fraction schedule. This is NOT a claim
            # that driver deltaPosMag equals scalar speed in a full game frame.
            fraction = min(4096, ((speed * 4294967296 // cap) + 0x80000) >> 20)
            speed, coast = add_step(0, 0, engine, speed, coast, throttle, fraction, cap, tick)

    print('Comparing C++ outputs and all relevant record/state writes...', flush=True)
    process = subprocess.run([str(ROOT / 'build/kinoko_offline_runner.exe'),
        str(ROOT / 'local/parameters/kartphysicalparam.bin'), str(ROOT / 'local/parameters/charphysicalparam.bin')],
        input='\n'.join(commands) + '\n', text=True, capture_output=True, check=True)
    actual = process.stdout.splitlines()
    directory = ROOT / 'local/validation/mario-standard-mr-figure8-01'
    if len(actual) != len(expected): raise ValueError('C++ case count differs')
    for index, (want, got) in enumerate(zip(expected, actual)):
        if want != got:
            case = labels[index]
            if case['stage'] == 'initialization':
                ref.prepare(case['character'], case['kart'], case['scene'], case['engine'])
                field = 'selection/derived field/record bytes'
                wp, gp = want.split(), got.split()
                if len(gp) == 6 and gp[0] == 'P':
                    for token, name in ((1, 'kart index'), (2, 'character index'), (3, 'driver+0x3f4'), (4, 'kart record'), (5, 'character record')):
                        if wp[token] != gp[token]:
                            field = name
                            if token >= 4:
                                offset = next(i for i, pair in enumerate(zip(bytes.fromhex(wp[token]), bytes.fromhex(gp[token]))) if pair[0] != pair[1])
                                field += f' byte +0x{offset:x}'
                            break
            else:
                ref.step(prepared[(case['character'], case['kart'], 0, case['engine'])], case['speed'], case['coast'], case['throttle'], case['fraction'], case['cap'])
                if got.startswith('L '):
                    field = 'speed_raw' if want.split()[1] != got.split()[1] else 'coasting'
                else: field = 'unsupported-input guard'
            failure = {'index': index, 'case': labels[index], 'command': commands[index],
                       'field': field, 'expected_arm': want, 'actual_cpp': got,
                       'instruction_tail': [hex(pc) for pc in ref.arm.trace],
                       'driver_writes': [write for write in ref.arm.writes if DRIVER <= write[1] < DRIVER + 0x5a8]}
            (directory / 'offline-failure.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8')
            raise ValueError(f'first divergent case: {failure}')
    baseline = prepared[(0, 0, 0, 2)]
    snapshot = (directory / 'arm9-main-ram.bin').read_bytes()
    active = json.loads((directory / 'active-parameters.json').read_text())
    for key, blob in [('active_kart_address', baseline[3]), ('active_character_address', baseline[4])]:
        address = int(active[key], 16) - 0x02000000
        if snapshot[address:address + len(blob)] != blob: raise ValueError('active snapshot mismatch')
    if baseline[2] != struct.unpack_from('<i', snapshot, int(active['driver_address'], 16) - 0x02000000 + 0x3f4)[0]:
        raise ValueError('active initialization derived field mismatch')
    # Fail closed on conditions outside the recovered path.
    invalid = ['L 0 0 0 2 -1 0 1 0 30720', 'L 0 0 0 2 0 0 1 4097 30720', 'L 0 0 0 2 0 0 1 0 0']
    rejected = subprocess.check_output([str(ROOT / 'build/kinoko_offline_runner.exe'),
        str(ROOT / 'local/parameters/kartphysicalparam.bin'), str(ROOT / 'local/parameters/charphysicalparam.bin')],
        input='\n'.join(invalid) + '\n', text=True).splitlines()
    if len(rejected) != len(invalid) or not all(row.startswith('E ') for row in rejected):
        raise ValueError('unsupported input accepted')
    report = {'initialization_cases': initialization_count,
              'longitudinal_cases': len(commands) - initialization_count,
              'repeated_sequence_steps': 2550, 'unsupported_cases_rejected': len(invalid),
              'active_snapshot_initialization_match': True, 'ram_sha256': hashlib.sha256(snapshot).hexdigest(),
              'rom_sha256': hashlib.sha256((ROOT / 'local/roms/Mario Kart DS.nds').read_bytes()).hexdigest(),
              'scope': 'ordinary grounded scalar stages with explicit upstream fraction/cap; not full-frame fidelity'}
    (directory / 'offline-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    # Discard only this tool's stale failed-run diagnostic after complete success.
    (directory / 'offline-failure.json').unlink(missing_ok=True)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
