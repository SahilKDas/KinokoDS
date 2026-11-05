"""Replay a bounded ROM driver-update fixture from saved RAM, without an emulator.

This is NOT a live race trace. The optional dispatcher replay includes original
contact/course callbacks; outer scene phases and hardware frame cadence remain
frozen. C++ comparisons use states produced by original ROM instructions.
"""
import hashlib
import argparse
import json
import struct
import subprocess
from arm_offline import Arm
from rom_code import ROOT
from sync_parameters import ROM_HASH
from validate_movement import flatten


def main(dispatch=False, scenario='straight'):
    directory = ROOT / 'local/validation/mario-standard-mr-figure8-01'
    active = json.loads((directory / 'active-parameters.json').read_text())
    driver = int(active['driver_address'], 16)
    a = Arm(trace_limit=2000)
    commands, expected, labels, samples, visited = [], [], [], [], set()
    thumb_addresses = set()
    scalar_commands, scalar_expected, scalar_labels = [], [], []
    tail_inputs = None
    scalar_input = None
    movement_position = None
    s = lambda off: a.number(driver + off, sign=True)
    u = lambda off: a.number(driver + off)
    v = lambda off: tuple(s(off + 4 * i) for i in range(3))

    def observer(cpu, pc):
        nonlocal tail_inputs, scalar_input, movement_position
        visited.add(pc)
        if cpu.thumb: thumb_addresses.add(pc)
        if pc == 0x01ffba68:
            # Only the already-declared ordinary scalar domain is compared.
            if (u(0x180) == 0 and u(0x44) & 16 and not u(0x44) & 0xb
                    and not u(0x48) & 0x20 and s(0x39c) == 0):
                key = cpu.number(0x0217560a + u(0x78) * 0x5c, 2)
                scalar_input = f'V 0 0 0 2 {s(0x2a8)} {int(bool(u(0x44) & 1024))} {int(bool(key & 1))} {s(0x2a0)} {s(0xd0)} {int(bool(key & 2))}'
            else: scalar_input = None
        elif pc == 0x01ffb5a8 and scalar_input is not None:
            scalar_commands.append(scalar_input)
            scalar_expected.append(f'V {s(0x2a8)} {int(bool(u(0x44) & 1024))}')
            scalar_labels.append(len(samples))
            scalar_input = None
        elif pc == 0x01ffb638:
            sp = cpu.reg['sp']
            row = (cpu.number(sp + 4, sign=True), v(0x68), v(0x50), u(0x180), u(0x44), u(0x380),
                   v(0x374), s(0x260), s(0x274), v(0x268), v(0x2f0), v(0x1fc))
            tail_inputs = (row, v(0x80), v(0xb0), u(0x7c), s(0x38c), cpu.number(sp + 8, sign=True),
                           s(0x2b8), s(0x2bc), s(0xc8), cpu.number(0x0217ad0c, sign=True),
                           cpu.number(0x0217ad10, sign=True), s(0x4d4))
        elif pc == 0x01ffb7f0:
            movement_position = v(0x80)
            if tail_inputs is not None:
                commands.append('T ' + ' '.join(map(str, flatten(tail_inputs))))
                fields = (v(0xa4), v(0x5c), v(0xb0), s(0x2a4), v(0x80), s(0x38c), u(0x44), s(0x2b8), s(0x2bc),
                          cpu.number(0x0217ad10, sign=True), s(0x4d4))
                expected.append('T ' + ' '.join(map(str, flatten(fields))))
                labels.append({'tick': len(samples), 'pc': hex(pc), 'instruction_tail': [hex(value) for value in cpu.trace[-32:]]})
                tail_inputs = None

    a.observer = observer
    initial_flags = u(0x7c)
    input_id = u(0x78)
    if input_id >= 10: raise ValueError('invalid snapshot input unit')
    error = None
    entry = 0x0207aaec if dispatch else 0x01ffcc50
    schedules = {
        'idle': [(120, 0)],
        'straight': [(60, 1), (20, 0), (40, 1)],
        'left': [(60, 1), (40, 1 | 32), (20, 1)],
        'right': [(60, 1), (40, 1 | 16), (20, 1)],
        'brake': [(60, 1), (30, 2), (30, 1)],
        'reverse': [(20, 1), (70, 2), (70, 1)],
        'drift-left': [(90, 1), (30, 1 | 32 | 256), (30, 1 | 16), (30, 1)],
        'drift-right': [(90, 1), (30, 1 | 16 | 256), (30, 1 | 32), (30, 1)],
    }
    inputs = [keys for duration, keys in schedules[scenario] for _ in range(duration)]
    input_base = 0x02175608 + input_id * 0x5c
    previous_keys = a.number(input_base + 2, 2)
    for tick, pressed in enumerate(inputs):
        movement_position = None
        a.store(input_base, pressed & ~previous_keys, 2)
        a.store(input_base + 2, pressed, 2)
        a.store(input_base + 4, previous_keys & ~pressed, 2)
        previous_keys = pressed
        a.writes.clear()
        steps_before = a.steps
        try:
            a.run(entry, driver, budget=100000 if dispatch else 20000)
        except (ValueError, IndexError) as failure:
            error = {'tick': tick, 'message': str(failure), 'pc': hex(a.reg['pc']),
                     'instruction_tail': [hex(pc) for pc in a.trace[-32:]]}
            break
        samples.append({'tick': tick, 'pressed_keys': pressed, 'position_raw': v(0x80),
            'position_after_movement_raw': movement_position,
            'speed_raw': s(0x2a8), 'magnitude_raw': s(0x2a4), 'fraction_raw': s(0x2a0),
            'cap_raw': s(0xd0), 'displacement_raw': v(0xa4), 'flags_44': hex(u(0x44)),
            'flags_48': hex(u(0x48)), 'flags_4c': hex(u(0x4c)), 'collision_mode': u(0x180),
            'instructions': a.steps - steps_before, 'writes': len(a.writes)})
    output = subprocess.check_output([str(ROOT / 'build/kinoko_movement_runner.exe')],
        input='\n'.join(commands) + '\n', text=True).splitlines()
    if len(output) != len(expected): raise ValueError('tail comparison output count mismatch')
    for index, (want, got) in enumerate(zip(expected, output)):
        if want != got:
            fields = [f'driver+0x{offset:x}' for offset in
                (0xa4, 0xa8, 0xac, 0x5c, 0x60, 0x64, 0xb0, 0xb4, 0xb8, 0x2a4, 0x80, 0x84, 0x88, 0x38c, 0x44, 0x2b8, 0x2bc)] + ['global+0x0217ad10', 'driver+0x4d4']
            diff = next((i for i, pair in enumerate(zip(want.split()[1:], got.split()[1:])) if pair[0] != pair[1]), None)
            error = dict(labels[index], stage='movement tail', first_field=fields[diff] if diff is not None else 'output format')
            error.update({'expected_arm': want,
                     'actual_cpp': got, 'command': commands[index]}
            )
            break
    scalar_output = subprocess.check_output([str(ROOT / 'build/kinoko_offline_runner.exe'),
        str(ROOT / 'local/parameters/kartphysicalparam.bin'), str(ROOT / 'local/parameters/charphysicalparam.bin')],
        input='\n'.join(scalar_commands) + '\n', text=True).splitlines()
    if len(scalar_output) != len(scalar_expected): raise ValueError('scalar output count mismatch')
    for index, (want, got) in enumerate(zip(scalar_expected, scalar_output)):
        if want != got:
            error = {'tick': scalar_labels[index], 'stage': 'scalar acceleration/drag/limiter',
                     'expected_arm': want, 'actual_cpp': got, 'command': scalar_commands[index],
                     'first_field': 'driver+0x2a8' if want.split()[1] != got.split()[1] else 'driver+0x44 bit 0x400'}
            break
    target = ROOT / 'local/validation/frame-inspection'
    target.mkdir(parents=True, exist_ok=True)
    instruction_bytes = b''.join(struct.pack('<I', pc) + a.code.read(pc, 4) for pc in sorted(visited))
    mismatched_code = [hex(pc) for pc in sorted(visited) if 0x02000000 <= pc < 0x02400000
        and a.code.read(pc, 4) != a.ram[pc - 0x02000000:pc - 0x02000000 + 4]]
    if mismatched_code: raise ValueError(f'ROM/capture instruction mismatch: {mismatched_code[:8]}')
    frozen = ['outer scene phases', 'game timers and hardware frame cadence']
    if not dispatch: frozen += ['course/contact processing outside entry', 'outer orientation/frame phases']
    observed_modes = sorted({sample['collision_mode'] for sample in samples})
    report = {'entry': hex(entry), 'scenario': scenario, 'scheduled_updates': len(inputs),
        'driver_address': hex(driver), 'completed_updates': len(samples),
        'cpp_tail_comparisons': len(expected), 'cpp_scalar_comparisons': len(scalar_expected),
        'unique_instruction_addresses': len(visited),
        'thumb_instruction_addresses': len(thumb_addresses), 'rom_sha256': ROM_HASH,
        'main_ram_instruction_mismatches': mismatched_code,
        'state_coverage': {'collision_modes': observed_modes,
            'flags44_bit1_updates': sum(bool(int(sample['flags_44'], 16) & 2) for sample in samples),
            'flags44_bit4_clear_updates': sum(not int(sample['flags_44'], 16) & 16 for sample in samples),
            'negative_speed_updates': sum(sample['speed_raw'] < 0 for sample in samples)},
        'address_opcode_sha256': hashlib.sha256(instruction_bytes).hexdigest(),
        'ram_sha256': hashlib.sha256(a.ram).hexdigest(), 'initial_flags_7c': hex(initial_flags),
        'fixture_changes': ['write input triggeredKeys/pressedKeys/releasedKeys from key history; no driver-state patches'],
        'frozen_dependencies': frozen,
        'live_trace': False, 'full_frame_verified': False, 'error': error, 'samples': samples}
    stem = 'offline-dispatch-trace' if dispatch else 'offline-driver-trace'
    filename = stem + ('' if scenario == 'straight' else '-' + scenario) + '.json'
    (target / filename).write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: value for k, value in report.items() if k != 'samples'}, indent=2))
    if error: raise ValueError(f'bounded driver replay failed; see {filename}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dispatch', action='store_true', help='include original history/inter-driver/update/post-update dispatcher')
    parser.add_argument('--scenario', choices=('idle', 'straight', 'left', 'right', 'brake', 'reverse', 'drift-left', 'drift-right'), default='straight')
    options = parser.parse_args()
    main(options.dispatch, options.scenario)
