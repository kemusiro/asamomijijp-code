# SPDX-License-Identifier: MIT
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

HERE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('render', HERE / 'render.py')
render = importlib.util.module_from_spec(spec)
spec.loader.exec_module(render)
BINARY = Path(os.environ.get('JT03_BINARY', HERE.parent / '.cache/jt03/build/jt03-render'))


def score(path, events, period=700, clock=4000000):
    path.write_bytes(struct.pack('<4sIII', b'WYM1', len(events), period, clock)
                     + b''.join(struct.pack('<IBB', *e) for e in events))


def fundamental(x, rate):
    x = x - x.mean()
    spec = abs(np.fft.rfft(x * np.hanning(len(x))))
    return int(np.argmax(spec)) * rate / len(x)


class Validation(unittest.TestCase):
    def test_invalid_inputs(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'x.bin'
            for events, clock in [([(0, 0, 1)], 8000000), ([(2, 0, 1), (1, 0, 2)], 4000000),
                                  ([(701, 0, 0)], 4000000), ([(0, 0x2d, 0)], 4000000)]:
                score(p, events, clock=clock)
                with self.assertRaises(ValueError):
                    render.read_score(p)
            p.write_bytes(b'WYM1')
            with self.assertRaises(ValueError):
                render.read_score(p)

    def test_trace_detects_reorder_and_early_write(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'trace'
            events = [(1, 0, 10), (1, 0, 20)]
            for writes in [[(4000, 0, 20), (4010, 0, 10)], [(3999, 0, 10), (4000, 0, 20)]]:
                p.write_bytes(b''.join(struct.pack('<QBB', *e) for e in writes))
                with self.assertRaises(ValueError):
                    render.verify_trace(p, events, 700)


@unittest.skipUnless(BINARY.exists(), 'Build the simulator or set JT03_BINARY for RTL integration tests')
class RTL(unittest.TestCase):
    def run_score(self, events):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        p = root / 'input.bin'
        score(p, events)
        report = render.render(p, root / 'out', BINARY)
        rate, audio = wavfile.read(root / 'out/stems-float.wav')
        self.assertEqual(audio.shape, (33600, 2))
        self.assertEqual(report['simulation']['fm_sample_period_min_cycles'], 72)
        self.assertEqual(report['simulation']['fm_sample_period_max_cycles'], 72)
        return rate, audio, report

    def test_ssg_pitch_busy_order_and_mute(self):
        # Same-time period-low writes deliberately repeat: never sort/deduplicate them.
        rate, audio, report = self.run_score([(0, 0, 1), (0, 0, 142), (0, 1, 0),
                                             (0, 7, 0x3e), (0, 8, 15), (500, 8, 0)])
        measured = fundamental(audio[4800:19200, 1], rate)
        self.assertLess(abs(measured - 4000000 / (64 * 142)), 4)
        self.assertEqual(float(abs(audio[:, 0]).max()), 0)
        self.assertLess(float(abs(audio[28800:, 1]).max()), 1e-5)
        self.assertGreater(report['simulation']['busy_wait_cycles'], 0)
        self.assertEqual(report['trace']['verified_writes'], 6)

    def test_fm_pitch_and_keyoff(self):
        # Algorithm 7, only operator 1 audible: FNUM=1038, BLOCK=4 => 439.96 Hz.
        events = []
        for slot in (0, 4, 8, 12):
            for reg, value in [(0x30, 1), (0x40, 32 if slot == 0 else 127),
                               (0x50, 31), (0x60, 0), (0x70, 0), (0x80, 15), (0x90, 0)]:
                events.append((0, reg + slot, value))
        events += [(0, 0xb0, 7), (0, 0xa4, 0x24), (0, 0xa0, 0x0e),
                   (10, 0x28, 0xf0), (500, 0x28, 0)]
        rate, audio, report = self.run_score(events)
        measured = fundamental(audio[4800:19200, 0], rate)
        expected = 1038 * 4000000 * 16 / (144 * 1048576)
        self.assertLess(abs(measured - expected), 4)
        self.assertEqual(float(abs(audio[:, 1]).max()), 0)
        self.assertLess(float(abs(audio[28800:, 0]).max()), 1e-4)
        self.assertGreater(report['simulation']['fm_peak_native'], 100)

    def test_event_exactly_at_period_is_executed_without_extra_audio(self):
        _, _, report = self.run_score([(0, 8, 0), (700, 8, 0)])
        self.assertEqual(report['trace']['verified_writes'], 2)
        self.assertEqual(report['output_frames_48000hz'], 33600)

    def test_cpp_independently_rejects_bad_clock(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d)
            score(p / 'bad.bin', [(0, 0, 1)], clock=8000000)
            rc = subprocess.run([str(BINARY), str(p / 'bad.bin'), str(p / 'trace'),
                                 str(p / 'stats'), '0'], capture_output=True)
            self.assertNotEqual(rc.returncode, 0)
            self.assertEqual(rc.stdout, b'')


if __name__ == '__main__':
    unittest.main()
