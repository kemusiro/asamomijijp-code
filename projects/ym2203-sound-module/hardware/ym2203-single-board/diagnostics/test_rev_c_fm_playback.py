# SPDX-License-Identifier: MIT
"""FM word decoding, waveform conversion, and muted capture-before-playback."""
from contextlib import redirect_stdout
import importlib.util
import io
import math
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel
from test_rev_c_dac_check import DACModel
from test_rev_c_fm_capture import trace


HERE = Path(__file__).resolve().parent
SOURCE_RATE = 16_000_000 / 288


def word(frame):
    return 0x400 | (512 + round(127 * math.sin(2 * math.pi * 440 * frame / SOURCE_RATE)))


def records():
    data = [word(i) for i in range(454)]
    on = {"data": data, "sh_hz": SOURCE_RATE, "bit_counts": {24: 454}}
    off = {"data": [0x600] * 454, "sh_hz": SOURCE_RATE, "bit_counts": {24: 454}}
    return off, on, off


def load(model):
    bus = model.load()
    machine = types.SimpleNamespace(Pin=model.Pin, I2S=model.I2S)
    modules = {"machine": machine, "rev_c_bus_check": bus}
    for name in ("rev_c_fm_capture", "rev_c_dac_check", "rev_c_fm_playback"):
        spec = importlib.util.spec_from_file_location(name, HERE / (name + ".py"))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        module.time = model
        modules[name] = module
    return modules["rev_c_fm_playback"], machine


class PlaybackModel(DACModel):
    def __init__(self, fault=None):
        self.playback_phase = False
        super().__init__(fault=fault)
        self.allow_fm = True
        self.registers = [0] * 256
        original_i2s = self.I2S
        model = self

        def i2s(*args, **kwargs):
            # Chip must be reset and both gates off before I2S takes resources.
            assert model.capture_closed
            model.playback_phase = True
            return original_i2s(*args, **kwargs)

        i2s.TX, i2s.STEREO = original_i2s.TX, original_i2s.STEREO
        self.I2S = i2s
        self.capture_closed = False

    def changed(self, gpio, old, value):
        if self.playback_phase:
            DACModel.changed(self, gpio, old, value)
        else:
            BusModel.changed(self, gpio, old, value)

    def assert_stopped(self):
        BusModel.assert_stopped(self)
        self.assert_audio_stopped()

    def assert_audio_stopped(self):
        assert all(self.level(g) == 0 for g in (10, 11, 12))
        if self.audio is not None:
            assert self.audio.closed


def fake_capture(model, bad=False):
    class FakeCapture:
        def open(self):
            pass

        def read(self):
            assert model.level(19) == model.level(26) == 0
            on = model.registers[0x28] == 0x10
            return trace(frame_value=(lambda f: 0) if bad else word if on else lambda f: 0x600)

        def close(self):
            # No DMA remains active when audio is enabled or after a failure.
            BusModel.assert_stopped(model)
            model.capture_closed = True
    return FakeCapture


class FMPlaybackTests(unittest.TestCase):
    def test_user_capture_words_decode_to_zero_and_small_positive_signal(self):
        module, unused = load(PlaybackModel())
        self.assertEqual(module.decode(0x600), 0)
        self.assertEqual([module.decode(w) for w in (0x67F, 0x67E, 0x65C)], [127, 126, 92])
        for exponent in range(1, 8):
            self.assertEqual(module.decode((exponent << 10) | 512), 0)
            self.assertEqual(module.decode(exponent << 10), -512 * 2 ** (exponent - 1))
            self.assertEqual(module.decode((exponent << 10) | 1023), 511 * 2 ** (exponent - 1))
        for value in (-1, 0, 1023, 8192, True, 0x600 + 0.0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                module.decode(value)

    def test_captured_period_resampling_level_limit_order_and_fades(self):
        module, unused = load(PlaybackModel())
        buffers, info = module.make_buffers(*records())
        silence, steady, fade_in, fade_out = buffers
        self.assertAlmostEqual(info["source_hz"], 440, delta=0.5)
        self.assertAlmostEqual(info["playback_hz"], 440, delta=1)
        self.assertAlmostEqual(info["tone_ms"], 2000, delta=10)
        self.assertFalse(any(silence))
        samples = list(struct.iter_unpack("<hh", steady))
        self.assertTrue(all(r == 0 for l, r in samples))
        self.assertLessEqual(max(abs(l) for l, r in samples), 4096)
        self.assertGreater(max(l for l, r in samples), 4000)
        self.assertLess(min(l for l, r in samples), -4000)
        period = len(samples) // 4
        self.assertEqual(samples[:period], samples[period:period * 2])
        for ramp in (fade_in, fade_out):
            for i, (l, r) in enumerate(struct.iter_unpack("<hh", ramp)):
                self.assertEqual(r, 0)
                self.assertLessEqual(abs(l), abs(samples[i][0]))
        self.assertEqual(struct.unpack_from("<h", fade_in)[0], 0)
        self.assertEqual(struct.unpack_from("<h", fade_out, len(fade_out) - 4)[0], 0)

    def test_invalid_format_silence_pitch_or_keyoff_never_produces_buffers(self):
        module, unused = load(PlaybackModel())
        for fault in ("format", "rate", "quiet", "zero", "pitch", "exponent"):
            off1, on, off2 = records()
            if fault == "format":
                on["bit_counts"] = {23: 454}
            elif fault == "rate":
                on["sh_hz"] = 40000
            elif fault == "quiet":
                off1["data"][0] = 0x67F
            elif fault == "zero":
                on["data"] = [0x600] * 454
            elif fault == "pitch":
                on["data"] = [0x400 | (512 + round(127 * math.sin(2 * math.pi * 880 * i / SOURCE_RATE))) for i in range(454)]
            else:
                on["data"][0] = 0
            with self.subTest(fault=fault), self.assertRaises((ValueError, RuntimeError)):
                module.make_buffers(off1, on, off2)

    def test_capture_then_three_replays_with_chip_held_in_reset(self):
        model = PlaybackModel()
        module, machine = load(model)
        with patch.object(module, "Capture", fake_capture(model)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()):
            module.run()
        self.assertTrue(model.capture_closed)
        self.assertEqual(sum(g == 19 and old == 0 and value == 1 for t, g, old, value in model.steps), 3)
        self.assertTrue(model.transfers)
        for data, line, dac, t in model.transfers:
            if any(data):
                self.assertTrue(line and dac)
                self.assertLessEqual(max(abs(l) for l, r in struct.iter_unpack("<hh", data)), 4096)
        model.assert_stopped()

    def test_invalid_captured_word_never_initializes_i2s_or_unmutes(self):
        model = PlaybackModel()
        module, machine = load(model)
        with patch.object(module, "Capture", fake_capture(model, bad=True)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
            module.run()
        self.assertIsNone(model.audio)
        self.assertFalse(any(g == 19 and value for t, g, old, value in model.steps))
        model.assert_stopped()

    def test_playback_interrupt_write_or_init_failure_stops_everything(self):
        for fault, error in (("interrupt", KeyboardInterrupt), ("short", RuntimeError), ("init", OSError)):
            model = PlaybackModel(fault=fault)
            module, machine = load(model)
            with self.subTest(fault=fault), patch.object(module, "Capture", fake_capture(model)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaises(error):
                module.run()
            self.assertTrue(model.capture_closed)
            model.assert_stopped()

    def test_import_does_not_touch_gpio(self):
        model = PlaybackModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
