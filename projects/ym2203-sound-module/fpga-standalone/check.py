#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check the first F1 RTL slice against framing rules and the existing C parser.

No physical I2C/USB, complete session engine, board programming or timing signoff.
Uses only the Python standard library, a C/C++ compiler, Verilator and Yosys.
"""
import argparse
import binascii
import ctypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import shutil
import struct
import subprocess

HERE = Path(__file__).resolve().parent


def packet(opcode, sequence, payload=b''):
    raw = struct.pack('<2sBBIH2x', b'Y2', 2, opcode, sequence, len(payload)) + payload
    return raw + struct.pack('<I', binascii.crc32(raw) & 0xffffffff)


def envelope_result(raw):
    if (not 16 <= len(raw) <= 208 or raw[:3] != b'Y2\x02' or raw[10:12] != b'\0\0'
            or int.from_bytes(raw[8:10], 'little') > 192
            or len(raw) != 16 + int.from_bytes(raw[8:10], 'little')):
        return 2
    return 0 if binascii.crc32(raw[:-4]) & 0xffffffff == int.from_bytes(raw[-4:], 'little') else 1


def vectors():
    rng = random.Random(2203)
    cases = []
    for length in range(193):
        data = packet(rng.randrange(256), rng.getrandbits(32), rng.randbytes(length))
        # Unknown commands and semantically invalid payloads must reach the
        # downstream engine unchanged when their envelope is valid.
        cases.append((data, 0, length % 2))
        corrupt = bytearray(data)
        corrupt[-1] ^= 1
        cases.append((bytes(corrupt), 1, length % 2))
    base = packet(0, 0)
    cases.append((base, 0, 0))
    for size in range(16):
        cases.append((base[:size], 2, 0))
    for index, value in [(0, 0), (1, 0), (2, 3), (8, 1), (9, 1), (10, 1), (11, 1)]:
        bad = bytearray(base)
        bad[index] = value
        cases.append((bytes(bad), 2, 0))
    cases.extend([(base + b'\0', 2, 1), (packet(3, 0, bytes(193)), 2, 0),
                  (bytes(600), 2, 1), (b'', 7, 2), (base[:7], 7, 2), (base, 7, 2)])
    for _ in range(160):
        raw = rng.randbytes(rng.randrange(250))
        cases.append((raw, envelope_result(raw), 0))
    return cases


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, logfile):
    with logfile.open('w') as out:
        subprocess.run([str(v) for v in command], stdout=out, stderr=subprocess.STDOUT,
                       check=True, timeout=300)
    return logfile.read_text()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, default=HERE.parent)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use a new, empty output directory')
    output.mkdir(parents=True, exist_ok=True)
    tools = {}
    for name, version_args in [('verilator', ['--version']), ('yosys', ['-V']), ('cc', ['--version'])]:
        executable = Path(shutil.which(name) or name)
        tools[name] = {'version': subprocess.check_output([str(executable), *version_args], text=True).splitlines()[0],
                       'sha256': sha(executable.resolve())}
    bridge = output / 'oracle.c'
    bridge.write_text('#include "stream.h"\nunsigned oracle(const unsigned char *p,unsigned n){'
                      'revc_stream s;revc_stream_init(&s);'
                      'revc_stream_command(&s,p,n,0,0,0);return s.result;}\n')
    src = project / 'firmware-c/src'
    library = output / 'oracle.so'
    run(['cc', '-std=c11', '-Wall', '-Wextra', '-Werror', '-shared', '-fPIC', '-I' + str(src),
         bridge, src / 'stream.c', src / 'wym1.c', '-o', library], output / 'oracle-build.log')
    oracle = ctypes.CDLL(str(library)).oracle
    oracle.argtypes = [ctypes.c_void_p, ctypes.c_uint]
    oracle.restype = ctypes.c_uint
    cases = vectors()
    compared = 0
    for raw, expected, mode in cases:
        if mode != 2 and (expected or raw == packet(0, 0)):
            actual = oracle(raw, len(raw))
            if actual != expected:
                raise AssertionError(('C envelope oracle mismatch', len(raw), actual, expected))
            compared += 1
    stimuli = output / 'vectors.bin'
    with stimuli.open('wb') as out:
        out.write(struct.pack('<I', len(cases)))
        for raw, expected, mode in cases:
            out.write(struct.pack('<III', len(raw), expected, mode) + raw)
    rtl, cpp = HERE / 'rtl/revc_v2_frame.v', HERE / 'tests/frame_test.cpp'
    build = output / 'build'
    run(['verilator', '--cc', '--exe', '--build', '-j', '4', '-Wall',
         '--top-module', 'revc_v2_frame', '--Mdir', build,
         '-CFLAGS', '-std=c++17', '-o', 'frame-test', rtl, cpp], output / 'rtl-build.log')
    result = run([build / 'frame-test', stimuli], output / 'rtl-test.log').strip()
    print(result)
    ys = output / 'synth.ys'
    ys.write_text('read_verilog ' + json.dumps(str(rtl)) + '\n'
                  'synth_ecp5 -top revc_v2_frame -json ' + json.dumps(str(output / 'frame.json')) + '\n'
                  'check -assert\ntee -o ' + json.dumps(str(output / 'stat.json')) + ' stat -json\n')
    run(['yosys', '-ql', output / 'synth.log', ys], output / 'synth-console.log')
    stats = json.loads((output / 'stat.json').read_text())
    summary = {
        'schema_version': 1, 'date_utc': datetime.now(timezone.utc).isoformat(),
        'scope': 'F1 v2 frame validator only; not a board or complete protocol implementation',
        'tools': tools, 'rtl_vectors': len(cases), 'c_parser_comparisons': compared,
        'result': result, 'synthesis': stats['design'],
        'source_sha256': {str(p.relative_to(HERE)): sha(p) for p in [rtl, cpp, Path(__file__).resolve()]},
        'c_oracle_sha256': {p.name: sha(p) for p in [src / 'stream.c', src / 'stream.h', src / 'wym1.c', src / 'wym1.h']},
        'place_route': 'not run', 'timing': 'not measured', 'physical_pinout': 'not assigned',
        'limits': ['No physical I2C or USB receiver, session state/sequence/lease engine, MIDI, clock setup or audio.',
                   'Ready/valid backpressure requires upstream buffering; physical overflow must fail safe.',
                   'Mapped cells describe this slice only; no full-system resource or timing conclusion.']}
    (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print('PASS C parser comparisons:', compared)
    print('PASS Yosys ECP5 mapping/check; no placement, timing or hardware acceptance')


if __name__ == '__main__':
    main()
