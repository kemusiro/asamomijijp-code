# SPDX-License-Identifier: MIT
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np
from scipy.io import wavfile

spec = importlib.util.spec_from_file_location('audio', Path(__file__).resolve().parents[1] / 'audio.py')
audio = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audio)


class Listening(unittest.TestCase):
    def test_common_gain_preserves_stem_sum_and_stereo(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            t = np.arange(36 * 48000) / 48000
            fm = .1 * np.sin(2 * np.pi * 440 * t)
            psg = .3 + .05 * np.sign(np.sin(2 * np.pi * 220 * t))
            raw = np.column_stack([fm, psg]).astype('float32')
            wavfile.write(root / 'stems-float.wav', 48000, raw)
            before = audio.digest(root / 'stems-float.wav')
            _, report = audio.listening(root)
            self.assertFalse(report['independent_stem_normalization'])
            self.assertEqual(before, audio.digest(root / 'stems-float.wav'))
            _, mix = wavfile.read(root / 'ysii-jt03-full.wav')
            _, fm_out = wavfile.read(root / 'ysii-jt03-fm.wav')
            _, ssg_out = wavfile.read(root / 'ysii-jt03-ssg.wav')
            self.assertTrue(np.array_equal(mix[:, 0], mix[:, 1]))
            error = mix[:, 0].astype(int) - fm_out.astype(int) - ssg_out.astype(int)
            self.assertLessEqual(abs(error).max(), 1)
            self.assertLess(abs(mix.astype(int)).max(), 32767)
            self.assertEqual(report['files']['ysii-jt03-25-35s.wav']['frames'], 480000)

    def test_arbitrary_recording_cannot_be_labelled_legacy_alpha4(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'wrong.wav'
            p.write_bytes(b'not the archived recording')
            with self.assertRaisesRegex(ValueError, 'SHA mismatch'):
                audio.legacy_comparison(Path(d), None, p)


if __name__ == '__main__':
    unittest.main()
