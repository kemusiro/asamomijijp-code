#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate WYM1, run JT03, resample separate FM/SSG outputs, verify every write."""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import time
import zlib

HERE = Path(__file__).resolve().parent
RESAMPLE = 'aresample=48000:resampler=swr:filter_size=128:cutoff=0.95:exact_rational=1'


def read_score(path):
    data = path.read_bytes()
    if len(data) < 16:
        raise ValueError('WYM1 header truncated')
    magic, count, period, clock = struct.unpack_from('<4sIII', data)
    if magic != b'WYM1' or not 1 <= count <= 131071 or not period or clock != 4000000:
        raise ValueError('Unsupported WYM1 header (single 4 MHz YM2203 only)')
    if len(data) != 16 + 6 * count:
        raise ValueError('WYM1 length/count mismatch')
    events = list(struct.iter_unpack('<IBB', data[16:]))
    previous = 0
    for ms, reg, value in events:
        if not previous <= ms <= period:
            raise ValueError('WYM1 timestamps must be ordered and within period')
        if 0x2d <= reg <= 0x2f:
            raise ValueError('Prescaler changes have not been validated')
        previous = ms
    return events, {'events': count, 'period_ms': period, 'clock_hz': clock,
                    'bytes': len(data), 'crc32': f'{zlib.crc32(data):08x}',
                    'sha256': hashlib.sha256(data).hexdigest()}


def verify_trace(path, events, duration_ms, full=True):
    data = path.read_bytes()
    if len(data) % 10:
        raise ValueError('Truncated bus trace')
    writes = list(struct.iter_unpack('<QBB', data))
    expected = events if full else [e for e in events if e[0] < duration_ms]
    if len(writes) != len(expected):
        raise ValueError(f'Trace count mismatch: {len(writes)} != {len(expected)}')
    last = -1
    for (cycle, reg, value), (ms, er, ev) in zip(writes, expected):
        if (reg, value) != (er, ev) or cycle < ms * 4000 or cycle <= last:
            raise ValueError('Bus trace changed, reordered or executed an event early')
        last = cycle
    return {'verified_writes': len(writes), 'same_time_order_preserved': True,
            'no_early_writes': True, 'sha256': hashlib.sha256(data).hexdigest()}


def render(source, output, binary, limit_ms=0):
    if sys.byteorder != 'little':
        raise ValueError('The PCM pipe currently requires a little-endian host')
    events, info = read_score(source)
    output.mkdir(parents=True, exist_ok=True)
    if (output / 'manifest.json').exists() or (output / 'stems-float.wav').exists():
        raise FileExistsError('Use a new output directory to preserve previous results')
    start = time.monotonic()
    with (output / 'simulation.log').open('w') as log:
        sim = subprocess.Popen([str(binary.resolve()), str(source.resolve()),
                                str((output / 'bus-trace.bin').resolve()),
                                str((output / 'simulation.json').resolve()), str(limit_ms)],
                               stdout=subprocess.PIPE, stderr=log)
        try:
            ff = subprocess.Popen(['ffmpeg', '-v', 'error', '-nostdin', '-f', 'f32le',
                                   '-ar', '1000000', '-ac', '2', '-i', 'pipe:0',
                                   '-af', RESAMPLE, '-c:a', 'pcm_f32le',
                                   str((output / 'stems-float.wav').resolve())],
                                  stdin=sim.stdout, stderr=log)
            sim.stdout.close()
            sim_rc, ff_rc = sim.wait(), ff.wait()
            if sim_rc or ff_rc:
                raise RuntimeError(f'Simulation/resampling failed: {sim_rc}/{ff_rc}; see simulation.log')
        finally:
            if sim.poll() is None:
                sim.terminate()
                sim.wait()
    stats = json.loads((output / 'simulation.json').read_text())
    duration = min(limit_ms, info['period_ms']) if limit_ms else info['period_ms']
    full = not limit_ms
    trace = verify_trace(output / 'bus-trace.bin', events, duration, full)
    if stats['executed_events'] != trace['verified_writes'] or stats['frames'] != duration * 1000:
        raise ValueError('Simulation count/frame mismatch')
    if stats['fm_sample_period_min_cycles'] != 72 or stats['fm_sample_period_max_cycles'] != 72:
        raise ValueError('Unexpected FM sample clock')
    probe = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams',
                                               '-of', 'json', str(output / 'stems-float.wav')]))['streams'][0]
    frames = int(probe['duration_ts'])
    if int(probe['sample_rate']) != 48000 or probe['channels'] != 2 or frames != duration * 48:
        raise ValueError('Resampled WAV length/rate/channel mismatch')
    build_info = binary.parent / 'build-info.json'
    manifest = {'schema_version': 1, 'source': info, 'simulation': stats,
                'trace': trace, 'full_score': full, 'output_frames_48000hz': frames,
                'wall_seconds': time.monotonic() - start,
                'build': json.loads(build_info.read_text()) if build_info.exists() else None,
                'resampler': RESAMPLE,
                'ffmpeg': subprocess.check_output(['ffmpeg', '-version'], text=True).splitlines()[0],
                'stems': {'channel_0': 'FM signed16 / 32768',
                          'channel_1': '(SSG A+B+C) / 255; DC retained; NOT stereo listening audio'},
                'stems_sha256': hashlib.sha256((output / 'stems-float.wav').read_bytes()).hexdigest()}
    (output / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(f"PASS: {trace['verified_writes']} ordered writes; {frames} frames at 48 kHz", flush=True)
    return manifest


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('source', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--binary', type=Path, default=HERE.parent / '.cache/jt03/build/jt03-render')
    p.add_argument('--limit-ms', type=int, default=0)
    a = p.parse_args()
    if a.limit_ms < 0:
        p.error('--limit-ms must be nonnegative')
    render(a.source, a.output, a.binary, a.limit_ms)
