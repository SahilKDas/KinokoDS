"""Exact ordinary A/B/reverse scalar comparisons; no whole-frame claim."""
import json
import subprocess
from rom_code import ROOT
from validate_longitudinal import Reference


def main():
    reference = Reference()
    commands, expected, cases = [], [], []
    prepared = {engine: reference.prepare(0, 0, 0, engine) for engine in (0, 1, 2)}

    def add(engine, speed, coast, a, b, fraction, cap, sequence=None):
        result = reference.step(prepared[engine], speed, coast, a, fraction, cap, brake=b)
        commands.append(f'V 0 0 0 {engine} {speed} {int(coast)} {int(a)} {fraction} {cap} {int(b)}')
        expected.append(f'V {result[0]} {int(result[1])}')
        cases.append({'engine': engine, 'speed': speed, 'coast': coast, 'a': a, 'b': b,
                      'fraction': fraction, 'cap': cap, 'sequence': sequence})
        return result

    speeds = (-2147483648, -2147483647, -30721, -30720, -12289, -12288, -12287,
              -411, -410, -409, -1, 0, 1, 409, 410, 411, 12287, 12288, 12289,
              30719, 30720, 30721, 2147483647)
    for engine in (0, 1, 2):
        for speed in speeds:
            for fraction in (0, 2047, 2048, 2867, 2868, 4096):
                for a, b in ((False, False), (True, False), (False, True)):
                    for coast in (False, True):
                        add(engine, speed, coast, a, b, fraction, 30720)
        for cap in (1, 410, 4096, 12287, 12288, 12289, 21502, 26115, 30720):
            for speed in (-cap - 1, -cap, -cap + 1, 0, cap - 1, cap, cap + 1):
                add(engine, speed, False, False, True, 0, cap)

    repeated = 0
    for engine in (0, 1, 2):
        speed, coast = 0, False
        for index in range(340):
            a, b = (False, True) if index < 120 else (True, False) if index < 270 else (False, False)
            # Synthetic scalar sequence, not measured movement or game timing.
            fraction = min(4096, abs(speed) * 4096 // 30720)
            speed, coast = add(engine, speed, coast, a, b, fraction, 30720, index)
            repeated += 1
    output = subprocess.check_output([str(ROOT / 'build/kinoko_offline_runner.exe'),
        str(ROOT / 'local/parameters/kartphysicalparam.bin'), str(ROOT / 'local/parameters/charphysicalparam.bin')],
        input='\n'.join(commands) + '\n', text=True).splitlines()
    target = ROOT / 'local/validation/frame-inspection'
    target.mkdir(parents=True, exist_ok=True)
    if len(output) != len(expected): raise ValueError('drive comparison output count mismatch')
    for index, (want, actual) in enumerate(zip(expected, output)):
        if want != actual:
            case = cases[index]
            reference.step(prepared[case['engine']], case['speed'], case['coast'], case['a'], case['fraction'], case['cap'], brake=case['b'])
            field = 'speed_raw' if want.split()[1] != actual.split()[1] else 'coasting'
            failure = dict(case, index=index, command=commands[index], first_field=field,
                expected_arm=want, actual_cpp=actual, instruction_tail=[hex(pc) for pc in reference.arm.trace],
                writes=reference.arm.writes)
            (target / 'drive-failure.json').write_text(json.dumps(failure, indent=2) + '\n', encoding='utf-8')
            raise ValueError(f'grounded drive mismatch: {failure}')
    invalid = 'V 0 0 0 2 0 0 1 0 30720 1\n'
    rejected = subprocess.check_output([str(ROOT / 'build/kinoko_offline_runner.exe'),
        str(ROOT / 'local/parameters/kartphysicalparam.bin'), str(ROOT / 'local/parameters/charphysicalparam.bin')], input=invalid, text=True)
    if not rejected.startswith('E '): raise ValueError('unrecovered A+B accepted')
    report = {'cases': len(commands), 'repeated_scalar_steps': repeated, 'a_plus_b_rejected': True,
        'scope': 'ordinary grounded scalar A, B and reverse; synthetic boundaries/sequences, not full frames'}
    (target / 'drive-validation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    (target / 'drive-failure.json').unlink(missing_ok=True)
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
