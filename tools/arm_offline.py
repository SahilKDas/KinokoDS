"""Bounded ARM/Thumb interpreter for inspected parameter/physics reference paths.

Executes pinned ROM instructions, not a second copy of the C++ equations.
Only DS division/square-root MMIO and the identified byte-copy helper are modeled externally.
No desktop, socket, process-memory or live emulator access.
"""
import struct
import math
import hashlib
import json
from pathlib import Path
import capstone
from capstone import arm as A
from rom_code import CodeImage, ROOT

MASK = 0xffffffff
DRIVER, KART, CHARACTER, PHYSP = 0x03000000, 0x03001000, 0x03002000, 0x03003000
STACK, CONFIG, STATUS = 0x03010000, 0x03005000, 0x03006000
RETURN = 0xdead0000


def signed(value, width=32):
    return value - (1 << width) if value & (1 << (width - 1)) else value


def trunc_div(a, b):
    return (abs(a) // abs(b)) * (-1 if (a < 0) != (b < 0) else 1)


class Arm:
    def __init__(self, code=None, trace_limit=100):
        self.code = code or CodeImage()
        if not 1 <= trace_limit <= 20000: raise ValueError('trace limit must be bounded')
        self.trace_limit = trace_limit
        self.ram = (ROOT / 'local/validation/mario-standard-mr-figure8-01/arm9-main-ram.bin').read_bytes()
        report = json.loads((ROOT / 'local/validation/mario-standard-mr-figure8-01/report.json').read_text())
        if hashlib.sha256(self.ram).hexdigest() != report['ram_sha256']:
            raise ValueError('captured RAM digest mismatch')
        self.decoder = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_ARM)
        self.decoder.detail = True
        self.thumb_decoder = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
        self.thumb_decoder.detail = True
        self.cache = {}
        self.reset()

    def reset(self):
        self.memory = {}
        self.reg = {f'r{i}': 0 for i in range(13)}
        self.reg.update({'sp': STACK, 'lr': RETURN, 'pc': 0})
        self.n = self.z = self.c = self.v = False
        self.writes, self.trace, self.copies = [], [], []
        self.steps = 0
        self.thumb = False
        self.observer = None

    @staticmethod
    def name(name):
        return {'ip': 'r12', 'fp': 'r11', 'sl': 'r10', 'sb': 'r9'}.get(name, name)

    def read(self, address, size):
        result = bytearray()
        for a in range(address, address + size):
            if a in self.memory: result.append(self.memory[a])
            elif 0x04000280 <= a < 0x040002c0: result.append(0)
            elif 0x02000000 <= a < 0x02400000: result.append(self.ram[a - 0x02000000])
            elif 0x03000000 <= a < 0x03020000: result.append(0)
            else: result.extend(self.code.read(a, 1))
        return bytes(result)

    def number(self, address, size=4, sign=False):
        return int.from_bytes(self.read(address, size), 'little', signed=sign)

    def put(self, address, data, record=False):
        for i, value in enumerate(data): self.memory[address + i] = value
        if record: self.writes.append((self.reg['pc'], address, len(data), data.hex()))

    def store(self, address, value, size=4, record=False):
        self.put(address, (value & ((1 << (size * 8)) - 1)).to_bytes(size, 'little'), record)
        if record and (address == 0x04000280 or 0x04000290 <= address < 0x040002a0):
            self.divide_device()
        if record and (address == 0x040002b0 or 0x040002b8 <= address < 0x040002c0):
            width = 8 if self.number(0x040002b0, 2) & 1 else 4
            self.store(0x040002b4, math.isqrt(self.number(0x040002b8, width)))

    def divide_device(self):
        mode = self.number(0x04000280, 2) & 3
        if mode not in (1, 2): raise ValueError('only inspected DIVCNT modes 1/2 are supported')
        numerator = self.number(0x04000290, 8, True)
        denominator = self.number(0x04000298, 8 if mode == 2 else 4, True)
        if denominator == 0: quotient, remainder = (1 if numerator < 0 else -1), numerator
        elif numerator == -(1 << 63) and denominator == -1: quotient, remainder = numerator, 0
        else:
            quotient = trunc_div(numerator, denominator)
            remainder = numerator - quotient * denominator
        self.store(0x040002a0, quotient, 8)
        self.store(0x040002a8, remainder, 8)

    def getreg(self, instruction, register):
        name = self.name(instruction.reg_name(register))
        if name not in self.reg and name != 'pc':
            raise ValueError(f'unsupported register {name} at {instruction.address:08x}: {instruction.mnemonic} {instruction.op_str}')
        return self.reg['pc'] + (4 if self.thumb else 8) if name == 'pc' else self.reg[name]

    def setreg(self, instruction, register, value):
        self.reg[self.name(instruction.reg_name(register))] = value & MASK

    def operand(self, instruction, op):
        if op.type == A.ARM_OP_IMM: value = op.imm & MASK
        elif op.type == A.ARM_OP_REG: value = self.getreg(instruction, op.reg)
        else: raise ValueError('unsupported value operand')
        shift = op.shift
        if shift.type in (A.ARM_SFT_LSL, A.ARM_SFT_LSR, A.ARM_SFT_ASR):
            value = self.shift(value, shift.value, shift.type)
        elif shift.type in (A.ARM_SFT_LSL_REG, A.ARM_SFT_LSR_REG, A.ARM_SFT_ASR_REG):
            kind = {A.ARM_SFT_LSL_REG: A.ARM_SFT_LSL, A.ARM_SFT_LSR_REG: A.ARM_SFT_LSR, A.ARM_SFT_ASR_REG: A.ARM_SFT_ASR}[shift.type]
            value = self.shift(value, self.getreg(instruction, shift.value) & 255, kind)
        elif shift.type: raise ValueError('unsupported ARM shift')
        return value

    def shift(self, value, amount, kind):
        if amount == 0: return value
        if kind == A.ARM_SFT_LSL:
            self.shifter_carry = bool((value >> (32 - amount)) & 1) if amount <= 32 else False
            return (value << amount) & MASK if amount < 32 else 0
        if kind == A.ARM_SFT_LSR:
            self.shifter_carry = bool((value >> (amount - 1)) & 1) if amount <= 32 else False
            return value >> amount if amount < 32 else 0
        if kind == A.ARM_SFT_ASR:
            self.shifter_carry = bool((value >> (min(amount, 32) - 1)) & 1)
            return (signed(value) >> min(amount, 32)) & MASK
        raise ValueError('unsupported barrel shift')

    def condition(self, cc):
        return {A.ARM_CC_INVALID: True, A.ARM_CC_AL: True,
                A.ARM_CC_EQ: self.z, A.ARM_CC_NE: not self.z,
                A.ARM_CC_HS: self.c, A.ARM_CC_LO: not self.c,
                A.ARM_CC_MI: self.n, A.ARM_CC_PL: not self.n,
                A.ARM_CC_VS: self.v, A.ARM_CC_VC: not self.v,
                A.ARM_CC_HI: self.c and not self.z, A.ARM_CC_LS: not self.c or self.z,
                A.ARM_CC_GE: self.n == self.v, A.ARM_CC_LT: self.n != self.v,
                A.ARM_CC_GT: not self.z and self.n == self.v,
                A.ARM_CC_LE: self.z or self.n != self.v}[cc]

    def flags(self, value, a=None, b=None, subtract=False):
        self.n, self.z = bool(value & 0x80000000), (value & MASK) == 0
        if a is not None:
            if subtract:
                self.c = a >= b
                self.v = bool(((a ^ b) & (a ^ value)) & 0x80000000)
            else:
                self.c = a + b > MASK
                self.v = bool((~(a ^ b) & (a ^ value)) & 0x80000000)

    def run(self, entry, r0=DRIVER, budget=20000, stop_at=None):
        self.thumb = bool(entry & 1)
        self.reg.update({'pc': entry & ~1, 'r0': r0, 'lr': RETURN})
        for _ in range(budget):
            pc = self.reg['pc']
            if pc == RETURN or pc == stop_at: return self.reg['r0']
            if self.observer is not None: self.observer(self, pc)
            # Known byte-copy contract; parameter selection itself is executed.
            if pc == 0x0214d1fc:
                size = self.reg['r2']
                if size not in (8, 152): raise ValueError('unexpected parameter copy size')
                self.copies.append((self.reg['r0'], self.reg['r1'], size))
                self.put(self.reg['r1'], self.read(self.reg['r0'], size), True)
                self.reg['pc'] = self.reg['lr']
                continue
            key = (pc, self.thumb)
            if key not in self.cache:
                decoder = self.thumb_decoder if self.thumb else self.decoder
                decoded = list(decoder.disasm(self.code.read(pc, 4), pc, count=1))
                if len(decoded) != 1: raise ValueError(f'cannot decode {pc:08x}')
                self.cache[key] = decoded[0]
            ins = self.cache[key]
            self.steps += 1
            if not self.condition(ins.cc):
                self.reg['pc'] = pc + ins.size
                continue
            self.trace.append(pc)
            if len(self.trace) > self.trace_limit: self.trace.pop(0)
            args, kind = ins.operands, ins.id
            self.shifter_carry = self.c
            next_pc = pc + ins.size
            if kind in (A.ARM_INS_B, A.ARM_INS_BL, A.ARM_INS_BX, A.ARM_INS_BLX):
                target = self.operand(ins, args[0])
                if kind in (A.ARM_INS_BL, A.ARM_INS_BLX): self.reg['lr'] = next_pc | int(self.thumb)
                if kind == A.ARM_INS_BLX and args[0].type == A.ARM_OP_IMM:
                    self.thumb = not self.thumb
                elif kind in (A.ARM_INS_BX, A.ARM_INS_BLX): self.thumb = bool(target & 1)
                next_pc = target & ~1
            elif kind in (A.ARM_INS_PUSH, A.ARM_INS_POP, A.ARM_INS_STMDB, A.ARM_INS_LDM, A.ARM_INS_STM):
                push = kind in (A.ARM_INS_PUSH, A.ARM_INS_STMDB)
                storing = push or kind == A.ARM_INS_STM
                if kind in (A.ARM_INS_PUSH, A.ARM_INS_POP):
                    base_name, registers = 'sp', args
                else:
                    base_name = self.name(ins.reg_name(args[0].reg))
                    registers = args[1:]
                address = self.reg[base_name] - 4 * len(registers) if push else self.reg[base_name]
                for index, register in enumerate(registers):
                    if storing: self.store(address + index * 4, self.getreg(ins, register.reg), record=True)
                    else: self.setreg(ins, register.reg, self.number(address + index * 4))
                if not storing and any(self.name(ins.reg_name(reg.reg)) == 'pc' for reg in registers):
                    target = self.reg['pc']; self.thumb = bool(target & 1); next_pc = target & ~1
                if kind in (A.ARM_INS_PUSH, A.ARM_INS_POP) or ins.writeback:
                    self.reg[base_name] = address if push else address + 4 * len(registers)
            elif kind in (A.ARM_INS_LDR, A.ARM_INS_LDRH, A.ARM_INS_LDRSH, A.ARM_INS_LDRB, A.ARM_INS_LDRSB, A.ARM_INS_STR, A.ARM_INS_STRH, A.ARM_INS_STRB):
                mem = args[1].mem
                base = self.getreg(ins, mem.base)
                encoding = int.from_bytes(ins.bytes, 'little')
                if self.thumb and self.name(ins.reg_name(mem.base)) == 'pc': base &= ~3
                preindexed = self.thumb or bool(encoding & (1 << 24))
                offset = mem.disp
                if mem.index:
                    index = self.getreg(ins, mem.index)
                    if args[1].shift.type == A.ARM_SFT_LSL: index <<= args[1].shift.value
                    elif args[1].shift.type: raise ValueError('unsupported memory shift')
                    offset += index if self.thumb or encoding & (1 << 23) else -index
                if not preindexed:
                    if len(args) != 3: raise ValueError('unsupported postindexed operand')
                    offset = args[2].imm if args[2].type == A.ARM_OP_IMM else self.operand(ins, args[2]) * (1 if encoding & (1 << 23) else -1)
                address = (base + offset if preindexed else base) & MASK
                size = 1 if kind in (A.ARM_INS_LDRB, A.ARM_INS_LDRSB, A.ARM_INS_STRB) else 2 if kind in (A.ARM_INS_LDRH, A.ARM_INS_LDRSH, A.ARM_INS_STRH) else 4
                if address % size:
                    raise ValueError(f'unsupported unaligned access at {pc:08x} -> {address:08x}, size {size}')
                if kind in (A.ARM_INS_STR, A.ARM_INS_STRH, A.ARM_INS_STRB):
                    self.store(address, self.getreg(ins, args[0].reg), size, True)
                else:
                    self.setreg(ins, args[0].reg, self.number(address, size, kind in (A.ARM_INS_LDRSH, A.ARM_INS_LDRSB)))
                    if self.name(ins.reg_name(args[0].reg)) == 'pc':
                        target = self.reg['pc']; self.thumb = bool(target & 1); next_pc = target & ~1
                if ins.writeback:
                    if args[0].reg == mem.base: raise ValueError('unpredictable load/store base overlap')
                    self.setreg(ins, mem.base, base + offset)
            elif kind in (A.ARM_INS_SMULL, A.ARM_INS_UMULL, A.ARM_INS_SMLAL):
                a, b = self.operand(ins, args[2]), self.operand(ins, args[3])
                product = signed(a) * signed(b) if kind != A.ARM_INS_UMULL else a * b
                if kind == A.ARM_INS_SMLAL:
                    product += self.getreg(ins, args[0].reg) | (self.getreg(ins, args[1].reg) << 32)
                self.setreg(ins, args[0].reg, product)
                self.setreg(ins, args[1].reg, product >> 32)
            elif kind == A.ARM_INS_MLA:
                value = self.operand(ins, args[1]) * self.operand(ins, args[2]) + self.operand(ins, args[3])
                self.setreg(ins, args[0].reg, value)
            elif kind == A.ARM_INS_SMULBB:
                a, b = self.operand(ins, args[1]), self.operand(ins, args[2])
                self.setreg(ins, args[0].reg, signed(a & 0xffff, 16) * signed(b & 0xffff, 16))
            elif kind == A.ARM_INS_CMP:
                a, b = self.operand(ins, args[0]), self.operand(ins, args[1])
                self.flags((a - b) & MASK, a, b, True)
            else:
                values = [self.operand(ins, op) for op in args[1:]]
                a, b = values[0], values[1] if len(values) > 1 else 0
                if self.thumb and len(values) == 1 and kind in (A.ARM_INS_ADD, A.ARM_INS_SUB, A.ARM_INS_AND, A.ARM_INS_BIC, A.ARM_INS_ORR, A.ARM_INS_MUL):
                    a, b = self.getreg(ins, args[0].reg), a
                if kind in (A.ARM_INS_LSL, A.ARM_INS_LSR, A.ARM_INS_ASR) and len(values) == 2:
                    shift_kind = {A.ARM_INS_LSL: A.ARM_SFT_LSL, A.ARM_INS_LSR: A.ARM_SFT_LSR, A.ARM_INS_ASR: A.ARM_SFT_ASR}[kind]
                    value = self.shift(a, b & 255, shift_kind)
                elif kind in (A.ARM_INS_MOV, A.ARM_INS_LSL, A.ARM_INS_LSR, A.ARM_INS_ASR): value = a
                elif kind == A.ARM_INS_MVN: value = ~a
                elif kind == A.ARM_INS_ADD: value = a + b
                elif kind == A.ARM_INS_ADC: value = a + b + int(self.c)
                elif kind == A.ARM_INS_SUB: value = a - b
                elif kind == A.ARM_INS_SBC: value = a - b - int(not self.c)
                elif kind == A.ARM_INS_RSB: value = b - a
                elif kind == A.ARM_INS_AND: value = a & b
                elif kind == A.ARM_INS_BIC: value = a & ~b
                elif kind == A.ARM_INS_ORR: value = a | b
                elif kind == A.ARM_INS_MUL: value = a * b
                else: raise ValueError(f'unsupported instruction {pc:08x}: {ins.mnemonic} {ins.op_str}')
                self.setreg(ins, args[0].reg, value)
                if ins.update_flags:
                    if kind == A.ARM_INS_ADD: self.flags(value & MASK, a, b)
                    elif kind == A.ARM_INS_SUB: self.flags(value & MASK, a, b, True)
                    elif kind == A.ARM_INS_RSB: self.flags(value & MASK, b, a, True)
                    elif kind in (A.ARM_INS_ADC, A.ARM_INS_SBC):
                        signed_value = signed(a) + signed(b) + int(self.c) if kind == A.ARM_INS_ADC else signed(a) - signed(b) - int(not self.c)
                        self.flags(value & MASK)
                        self.c = value > MASK if kind == A.ARM_INS_ADC else value >= 0
                        self.v = not -(1 << 31) <= signed_value < (1 << 31)
                    else:
                        self.flags(value & MASK)
                        self.c = self.shifter_carry
            self.reg['pc'] = next_pc
        raise ValueError(f'instruction budget exceeded at {self.reg["pc"]:08x}')

    def setup(self, kart, character):
        self.reset()
        self.put(KART, kart)
        self.put(CHARACTER, character)
        self.store(DRIVER + 0x2cc, KART)
        self.store(DRIVER + 0x2d0, CHARACTER)
        self.store(0x0217b018, PHYSP)
        self.store(PHYSP, KART)
        self.store(PHYSP + 4, CHARACTER)
        self.store(0x021759a0, CONFIG)
        self.store(0x0217aa34, STATUS)
