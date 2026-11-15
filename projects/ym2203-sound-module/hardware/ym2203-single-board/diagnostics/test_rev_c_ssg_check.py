# SPDX-License-Identifier: MIT
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel


HERE = Path(__file__).resolve().parent


def load_sound(model):
    bus = model.load()
    spec = importlib.util.spec_from_file_location("ssg_diagnostic", HERE / "rev_c_ssg_check.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"rev_c_bus_check": bus}):
        spec.loader.exec_module(module)
    module.time = model
    return module


class SSGDiagnosticTests(unittest.TestCase):
    def test_six_separate_tones_and_mute_gaps(self):
        model = BusModel(allow_tone=True)
        module = load_sound(model)
        output = io.StringIO()
        with redirect_stdout(output):
            module.run()
        self.assertEqual([w[0] for w in model.tone_windows], [0, 1, 2, 0, 1, 2])
        for channel, start, stop in model.tone_windows:
            self.assertEqual(stop - start, 2_000_000)
        for previous, following in zip(model.tone_windows, model.tone_windows[1:]):
            self.assertGreaterEqual(following[1] - previous[2], 1_000_000)
        self.assertIn("DONE: sequence sent.", output.getvalue())
        self.assertEqual(output.getvalue().count("PASS reg="), 6)
        self.assertAlmostEqual(module.TONE_HZ, 440.140845, places=5)
        model.assert_stopped()

    def test_ctrl_c_during_sound_mutes_before_reset(self):
        model = BusModel(allow_tone=True, interrupt_tone=True)
        with redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            load_sound(model).run()
        self.assertEqual(len(model.tone_windows), 1)
        self.assertEqual(model.tone_windows[0][2] - model.tone_windows[0][1], 1_000_000)
        model.assert_stopped()

    def test_failed_preflight_never_enables_audio(self):
        model = BusModel(allow_tone=True, stuck_low=0)
        with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            load_sound(model).run()
        self.assertEqual(model.tone_windows, [])
        model.assert_stopped()

    def test_setup_readback_failure_between_tones_does_not_unmute(self):
        model = BusModel(allow_tone=True, bad_second_tone=True)
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "SSG setup mismatch"):
            load_sound(model).run()
        self.assertEqual(len(model.tone_windows), 1)
        model.assert_stopped()

    def test_import_does_not_touch_gpio(self):
        model = BusModel(allow_tone=True)
        load_sound(model)
        self.assertEqual(model.pins, {})
        self.assertEqual(model.tone_windows, [])

    def test_envelope_loud_levels_noise_and_fm_writes_are_rejected(self):
        model = BusModel(allow_tone=True)
        module = load_sound(model)
        board = module.RevCSSGBus()
        try:
            board.start()
            for register, value in [(8, 11), (9, 15), (10, 16), (7, 0), (7, 0x38), (0x28, 0xF0)]:
                with self.subTest(register=register), self.assertRaises(ValueError):
                    board.write_ssg(register, value)
            for channel in [-1, 3, True]:
                with self.subTest(channel=channel), self.assertRaises(ValueError):
                    board.tone(channel)
        finally:
            board.close()
        self.assertEqual(model.tone_windows, [])
        model.assert_stopped()


if __name__ == "__main__":
    unittest.main()
