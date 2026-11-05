"""Offline byte audit of ROM -> catalogs -> C++ -> captured initialization loop.

The small ARM executor below supports only the inspected surface loop. It is
not a general emulator or a substitute for a game trajectory oracle.
"""
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import capstone
from capstone.arm import ARM_OP_IMM, ARM_OP_REG, ARM_SFT_LSL, ARM_SFT_LSR, ARM_SFT_ASR
import sync_parameters as source

ROOT = Path(__file__).resolve().parents[1]
MASK = 0xffffffff


def signed(value):
    return value if value < 0x80000000 else value - 0x100000000


class SurfaceInstructions:
    def __init__(self, ram):
        self.start, self.end = 0x02072774, 0x020727C0
        decoder = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        decoder.detail = True
        code = ram[self.start - 0x02000000:self.end - 0x02000000]
        self.instructions = {i.address: i for i in decoder.disasm(code, self.start)}
        if len(self.instructions) * 4 != len(code):
            raise ValueError('incomplete ARM loop decode')
        self.sha256 = hashlib.sha256(code).hexdigest()
        if self.sha256 != 'a22e38f958dc46500f8846cea3220b8859984321da99ecaf367902f9abc2a6d0':
            raise ValueError('surface loop differs from inspected AMCE instructions')

    def run(self, kart, character):
        memory = bytearray(kart)
        registers = {'r0': 0x1000, 'ip': 0x2000}
        carry, comparison, pc = 0, 0, self.start

        def read_operand(instruction, op):
            if op.type == ARM_OP_IMM:
                value = op.imm & MASK
            elif op.type == ARM_OP_REG:
                value = registers.get(instruction.reg_name(op.reg), 0)
            else:
                raise ValueError('unsupported ARM operand')
            if op.shift.type == ARM_SFT_LSL:
                value = (value << op.shift.value) & MASK
            elif op.shift.type == ARM_SFT_LSR:
                value >>= op.shift.value
            elif op.shift.type == ARM_SFT_ASR:
                value = (signed(value) >> op.shift.value) & MASK
            elif op.shift.type:
                raise ValueError('unsupported shift')
            return value

        for _ in range(1000):
            if pc == self.end:
                return bytes(memory)
            instruction = self.instructions[pc]
            op, args = instruction.mnemonic, instruction.operands
            pc += 4
            if op in ('bge', 'blt'):
                if (comparison >= 0 if op == 'bge' else comparison < 0):
                    pc = args[0].imm
                continue
            if op == 'cmp':
                comparison = signed(read_operand(instruction, args[0])) - signed(read_operand(instruction, args[1]))
                continue
            destination = instruction.reg_name(args[0].reg)
            if op in ('ldr', 'str'):
                address = registers[instruction.reg_name(args[1].mem.base)] + args[1].mem.disp
                if op == 'ldr':
                    if address == 0x2000:
                        value = struct.unpack_from('<I', character)[0]
                    elif 0x1000 <= address <= 0x1000 + 148:
                        value = struct.unpack_from('<I', memory, address - 0x1000)[0]
                    else:
                        raise ValueError('unsupported ARM memory read')
                else:
                    if not 0x1068 <= address <= 0x1094:
                        raise ValueError('unexpected ARM write')
                    struct.pack_into('<I', memory, address - 0x1000, registers[destination])
                    continue
            elif op == 'smull':
                product = signed(read_operand(instruction, args[2])) * signed(read_operand(instruction, args[3]))
                registers[destination] = product & MASK
                registers[instruction.reg_name(args[1].reg)] = (product >> 32) & MASK
                continue
            else:
                values = [read_operand(instruction, a) for a in args[1:]]
                if op == 'mov': value = values[0]
                elif op in ('add', 'adds', 'adc'):
                    value = values[0] + values[1] + (carry if op == 'adc' else 0)
                    if op == 'adds': carry = int(value > MASK)
                # Capstone represents these aliases as a MOV-like shifted operand.
                elif op in ('lsl', 'lsr', 'asr'): value = values[0]
                elif op == 'orr': value = values[0] | values[1]
                else: raise ValueError(f'unsupported instruction: {op}')
            registers[destination] = value & MASK
        raise ValueError('ARM loop failed to terminate')


def original_tables():
    rom = (ROOT / 'local/roms/Mario Kart DS.nds').read_bytes()
    if hashlib.sha256(rom).hexdigest() != source.ROM_HASH:
        raise ValueError('ROM hash mismatch')
    files = source.filesystem(source.region(rom, source.u32(rom, 0x40), source.u32(rom, 0x44)),
                              source.region(rom, source.u32(rom, 0x48), source.u32(rom, 0x4c)), rom)
    start, end = files['data/KartModelMainA.carc']
    names, fat, data = source.narc(source.decompress(rom[start:end]))
    entries = source.filesystem(names, fat, data)
    result = {}
    for name in ('kartphysicalparam.bin', 'charphysicalparam.bin'):
        a, b = entries[name]
        result[name] = data[a:b]
    return result


def audit():
    tables = original_tables()
    for name, payload in tables.items():
        binary = (ROOT / 'local/parameters' / name).read_bytes()
        catalog = json.loads((ROOT / 'local/parameters' / (name + '.json')).read_text())
        if binary != payload or hashlib.sha256(payload).hexdigest() != catalog['sha256']:
            raise ValueError(f'{name}: ROM/table/catalog mismatch')
        if len(catalog['records']) * catalog['stride'] != len(payload):
            raise ValueError('catalog record count mismatch')
        for index, record in enumerate(catalog['records']):
            raw = payload[index * catalog['stride']:(index + 1) * catalog['stride']]
            expected = source.decode_kart(raw) if catalog['stride'] == 152 else dict(zip(['unknown_00_raw', 'weight_raw'], struct.unpack('<ii', raw)))
            if (record['id'] != index or record['offset'] != index * catalog['stride'] or
                record['raw_hex'] != raw.hex() or record['sha256'] != hashlib.sha256(raw).hexdigest() or record['fields'] != expected):
                raise ValueError(f'{name}: record {index} catalog mismatch')
    directory = ROOT / 'local/validation/mario-standard-mr-figure8-01'
    ram = (directory / 'arm9-main-ram.bin').read_bytes()
    if hashlib.sha256(ram).hexdigest() != json.loads((directory / 'report.json').read_text())['ram_sha256']:
        raise ValueError('RAM capture hash mismatch')
    arm = SurfaceInstructions(ram)
    kart_table, char_table = tables['kartphysicalparam.bin'], tables['charphysicalparam.bin']
    # All output is bounded (<1 MB); no generated game data enters version control.
    output = subprocess.check_output([str(ROOT / 'build/kinoko_sync_dump.exe'),
                                     str(ROOT / 'local/parameters/kartphysicalparam.bin'),
                                     str(ROOT / 'local/parameters/charphysicalparam.bin')], text=True)
    lines = output.splitlines()
    if len(lines) != 63 + 1950:
        raise ValueError('unexpected C++ audit case count')
    for index, line in enumerate(lines[:63]):
        kind, number, encoded = line.split(',')
        table, stride, expected_index = (kart_table, 152, index) if index < 50 else (char_table, 8, index - 50)
        if kind != ('kart' if index < 50 else 'char') or int(number) != expected_index or bytes.fromhex(encoded) != table[expected_index * stride:(expected_index + 1) * stride]:
            raise ValueError(f'C++ record roundtrip mismatch: {index}')
    seen = set()
    cache = {}
    for line in lines[63:]:
        kind, mode, character, kart, selected_kart, selected_char, encoded_kart, encoded_char = line.split(',')
        mode, character, kart, selected_kart, selected_char = map(int, (mode, character, kart, selected_kart, selected_char))
        case = (mode, character, kart)
        expected = (kart, character) if mode == 0 else ((37 + character, character) if mode == 1 else (0, 0))
        if kind != 'case' or mode not in range(3) or character not in range(13) or kart not in range(50) or case in seen or (selected_kart, selected_char) != expected:
            raise ValueError(f'C++ selection mismatch: {case}')
        seen.add(case)
        ki, ci = expected
        original = kart_table[ki * 152:(ki + 1) * 152]
        char = char_table[ci * 8:(ci + 1) * 8]
        if expected not in cache:
            cache[expected] = arm.run(original, char)
        if bytes.fromhex(encoded_kart) != cache[expected] or bytes.fromhex(encoded_char) != char:
            raise ValueError(f'C++/captured ARM mismatch: {case}')
    actual = json.loads((directory / 'active-parameters.json').read_text())
    address = int(actual['active_kart_address'], 16) - 0x2000000
    if cache[(0, 0)] != ram[address:address + 152]:
        raise ValueError('active Mario/kart 0 mismatch')
    report = {'rom_sha256': source.ROM_HASH, 'record_roundtrips': 63, 'selection_cases': len(seen),
              'distinct_surface_pairs_executed': len(cache), 'surface_loop_sha256': arm.sha256,
              'mario_kart0_active_record_match': True,
              'scope': 'ROM/catalog byte fidelity, selection, surface loop only; not full initialization or driving physics'}
    (ROOT / 'local/parameters/sync-audit.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    audit()
