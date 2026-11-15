# SPDX-License-Identifier: MIT
"""Per-channel FM configuration, aggregate headroom and six-voice commands."""
from contextlib import redirect_stdout
import importlib.util
import io
import math
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_rev_c_fm_live import TestStream, packed
from test_rev_c_fm_ssg_check import MixerModel, load as load_mixer


HERE = Path(__file__).resolve().parent


class PolyModel(MixerModel):
    def __init__(self):
        self.fm_keys = [False] * 3
        self.poly_transfers = []
        super().__init__()
        original = self.I2S.write
        model = self
        def write(audio, data):
            if len(data) == 2160:
                periods = tuple(model.registers[2*i] | model.registers[2*i+1] << 8 for i in range(3))
                model.poly_transfers.append((tuple(model.fm_keys), model.level(19), model.level(26),
                                             tuple(model.registers[8:11]), periods))
            return original(audio, data)
        self.I2S.write = write

    def changed(self, gpio, old, value):
        count = len(self.writes)
        super().changed(gpio, old, value)
        if not self.level(22) or not self.level(9):
            self.fm_keys[:] = [False] * 3
        elif len(self.writes) != count and self.writes[-1][0] == 0x28:
            key = self.writes[-1][1]
            assert key & 3 < 3
            assert key & 0xF0 in (0, 0x10)
            self.fm_keys[key & 3] = bool(key & 0x10)


class PolyStream(TestStream):
    def __init__(self, model, missing=None, loud=False):
        super().__init__(model)
        self.phases = [0.0] * 3
        self.missing, self.loud = missing, loud

    def take(self):
        assert self.running
        self.model.us += 11250
        regs = self.model.registers
        frequencies, levels = [], []
        for channel in range(3):
            fnum = ((regs[0xA4 + channel] & 7) << 8) | regs[0xA0 + channel]
            block = (regs[0xA4 + channel] >> 3) & 7
            frequencies.append(4000000 / 72 * fnum * 2**block / 2**21)
            level = 127 if regs[0x40 + channel] == 48 else 70 if self.loud else 32
            levels.append(level if self.model.fm_keys[channel] and self.missing != channel else 0)
        words = []
        for unused in range(625):
            value = 0
            for channel in range(3):
                value += round(levels[channel] * math.sin(self.phases[channel]))
                self.phases[channel] = (self.phases[channel] + 2 * math.pi * frequencies[channel] / (4000000/72)) % (2*math.pi)
            words.append(0x400 | (512 + value))
        return packed(words)


def load(model):
    mixer, live, machine = load_mixer(model)
    spec = importlib.util.spec_from_file_location("six_voice_diagnostic", HERE / "rev_c_six_voice_check.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"rev_c_fm_live": live, "rev_c_fm_ssg_check": mixer}):
        spec.loader.exec_module(module)
    return module, live, machine


class SixVoiceTests(unittest.TestCase):
    def test_three_individual_fm_channels_chord_six_voices_and_mutes(self):
        model = PolyModel()
        module, live, machine = load(model)
        output = io.StringIO()
        original = module.SixVoiceBus.configure_three
        def configure(bus):
            self.assertFalse(model.stream.running)
            self.assertEqual(model.level(19), 0)
            self.assertEqual(model.level(26), 0)
            original(bus)
        with patch.object(live, "Stream", lambda: PolyStream(model)), patch.object(module.SixVoiceBus, "configure_three", configure), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output):
            module.run()
        states = {(keys, line, dac, levels) for keys, line, dac, levels, periods in model.poly_transfers}
        for keys in ((True,False,False), (False,True,False), (False,False,True), (True,True,True)):
            self.assertIn((keys, 1, 1, (0,0,0)), states)
        self.assertIn(((True,True,True), 1, 1, (7,7,7)), states)
        self.assertIn(((True,True,True), 1, 0, (7,7,7)), states)
        self.assertIn(((True,True,True), 0, 1, (7,7,7)), states)
        self.assertIn(((False,False,False), 1, 1, (0,0,0)), states)
        final = dict(model.writes)
        for channel in range(3):
            self.assertEqual(final[0x40+channel], 64)
            for slot in (4,8,12):
                self.assertEqual(final[0x40+slot+channel], 127)
        self.assertTrue(any(periods == (478,379,319) and levels == (7,7,7)
                            for keys, line, dac, levels, periods in model.poly_transfers))
        self.assertIn("SIX VOICE: all ten sections sent.", output.getvalue())
        self.assertIn("SAFE:", output.getvalue())
        model.assert_stopped()
        self.assertFalse(any(model.fm_keys))
        self.assertTrue(model.stream.closed and model.audio.closed)

    def test_missing_second_fm_channel_is_detected(self):
        model = PolyModel()
        module, live, machine = load(model)
        with patch.object(live, "Stream", lambda: PolyStream(model, missing=1)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "channel 2"):
            module.run()
        model.assert_stopped()
        self.assertTrue(model.stream.closed and model.audio.closed)

    def test_excessive_three_channel_sum_fails_before_six_voice_section(self):
        model = PolyModel()
        module, live, machine = load(model)
        with patch.object(live, "Stream", lambda: PolyStream(model, loud=True)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "level exceeded"):
            module.run()
        self.assertFalse(any(levels == (7,7,7) for keys, line, dac, levels, periods in model.poly_transfers))
        model.assert_stopped()

    def test_poly_policy_rejects_loud_levels_extra_slots_and_register_holes(self):
        model = PolyModel()
        module, live, machine = load(model)
        bus = module.SixVoiceBus()
        try:
            bus.start()
            for register, value in ((0x40,48), (0x41,0), (0x42,48), (0x44,64),
                                    (0x28,0xF0), (0x28,0x13), (0x43,64), (0xA8,0),
                                    (0x27,0), (True,0), (0x40,64.0)):
                with self.subTest(register=register, value=value), self.assertRaises(ValueError):
                    bus._write_three(register,value)
            for channels in ((3,), (True,), (-1,), (0,4)):
                with self.subTest(channels=channels), self.assertRaises(ValueError):
                    bus.fm_mask(channels)
        finally:
            bus.close()
        self.assertFalse(model.writes)
        model.assert_stopped()

    def test_import_has_no_pin_side_effects(self):
        model = PolyModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
