"""Capture ARM9 main RAM through melonDS's localhost GDB stub.

Read-only memory commands; briefly halts the emulated CPU, then detaches.
This is a state snapshot, NOT a frame-aligned physics trace.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time

ROOT = Path(__file__).resolve().parents[1]


class Remote:
    def __init__(self, port=3333):
        self.socket = socket.create_connection(('127.0.0.1', port), 5)
        self.socket.settimeout(10)
        self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.pending = bytearray()
        # melonDS expects an initial ACK before accepting RSP commands.
        self.socket.sendall(b'+')
        if self.byte() != b'+':
            raise ConnectionError('missing initial melonDS ACK')

    def byte(self):
        if not self.pending:
            self.pending.extend(self.socket.recv(16384))
            if not self.pending:
                raise ConnectionError('debugger disconnected')
        value = bytes(self.pending[:1])
        del self.pending[:1]
        return value

    def response(self):
        while self.byte() != b'$':
            pass
        raw = bytearray()
        while True:
            b = self.byte()
            if b == b'#':
                break
            raw.extend(b)
        checksum = self.byte() + self.byte()
        if int(checksum, 16) != sum(raw) % 256:
            self.socket.sendall(b'-')
            raise ValueError('RSP checksum mismatch')
        self.socket.sendall(b'+')
        # GDB RSP escaping and run-length encoding.
        out = bytearray()
        i = 0
        while i < len(raw):
            if raw[i] == 0x7d:
                i += 1
                out.append(raw[i] ^ 0x20)
            elif raw[i] == 0x2a:
                i += 1
                out.extend([out[-1]] * (raw[i] - 29))
            else:
                out.append(raw[i])
            i += 1
        return out.decode('ascii')

    def command(self, text):
        data = text.encode('ascii')
        self.socket.sendall(b'$' + data + b'#' + f'{sum(data) % 256:02x}'.encode())
        return self.response()

    def halt(self):
        reply = self.command('?')
        if not reply.startswith(('S', 'T')):
            raise ValueError(f'expected stop reply: {reply}')
        return reply

    def read(self, address, size):
        result = bytearray()
        for offset in range(0, size, 512):
            length = min(512, size - offset)
            reply = self.command(f'm{address + offset:x},{length:x}')
            if reply.startswith('E'):
                raise ValueError(f'memory read failed: {reply}')
            block = bytes.fromhex(reply)
            if len(block) != length:
                raise ValueError('short memory response')
            result.extend(block)
        return bytes(result)

    def close(self):
        try:
            self.command('D')
        finally:
            self.socket.close()


def capture(label):
    if not label or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in label):
        raise ValueError('use lowercase letters, digits, - and _ for label')
    output = ROOT / 'local/validation' / label
    if output.exists():
        raise ValueError('capture label already exists; choose another')
    used = sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file())
    if used + 4_194_304 + 100_000 >= 199_000_000:
        raise ValueError('insufficient workspace budget')
    remote = Remote()
    try:
        stop = remote.halt()
        ram = remote.read(0x02000000, 0x400000)
    finally:
        remote.close()
    output.mkdir(parents=True)
    (output / 'arm9-main-ram.bin').write_bytes(ram)
    matches = {}
    for filename, stride in [('kartphysicalparam.bin', 0x98), ('charphysicalparam.bin', 8)]:
        table = (ROOT / 'local/parameters' / filename).read_bytes()
        table_hits = []
        start = 0
        while (hit := ram.find(table, start)) >= 0:
            table_hits.append(f'0x{0x02000000 + hit:08x}')
            start = hit + 1
        records = []
        for index in range(len(table) // stride):
            pattern = table[index * stride:(index + 1) * stride]
            hits = []
            start = 0
            while (hit := ram.find(pattern, start)) >= 0:
                hits.append(f'0x{0x02000000 + hit:08x}')
                start = hit + 1
            records.append({'id': index, 'exact_byte_matches': hits})
        matches[filename] = {'whole_table_matches': table_hits, 'records': records}
    report = {'label': label, 'captured_at_unix': time.time(), 'base_address': '0x02000000',
              'length': len(ram), 'ram_sha256': hashlib.sha256(ram).hexdigest(),
              'stop_reply': stop, 'matches': matches,
              'limitation': 'Byte matches do not establish active driver selection or physics fidelity.'}
    (output / 'report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({name: {'whole_table': value['whole_table_matches'],
                            'id_0': value['records'][0]['exact_byte_matches']}
                      for name, value in matches.items()}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('label')
    capture(parser.parse_args().label)
