# SPDX-License-Identifier: MIT
"""Host tests of sample data and safety sequencing, not analogue verification."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import struct
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel


HERE = Path(__file__).resolve().parent


class DACModel(BusModel):
    def __init__(self, fault=None, fail_pin=None):
        super().__init__(fail_pin=fail_pin)
        self.fault = fault
        self.transfers = []
        self.audio = None
        self.events = []
        model = self

        class FakeI2S:
            TX, STEREO = 0, 1

            def __init__(self, ident, **kwargs):
                model.events.append("init")
                assert all(model.level(gpio) == 0 for gpio in (9, 19, 22, 26))
                if model.fault == "init":
                    raise OSError("I2S resource unavailable")
                self.ident, self.kwargs = ident, kwargs
                self.closed = False
                model.audio = self

            def write(self, data):
                assert not self.closed
                nonzero = any(data)
                if model.level(19) and model.level(26) and nonzero:
                    if model.fault == "interrupt":
                        raise KeyboardInterrupt
                    if model.fault == "write":
                        raise OSError("I2S write failure")
                    if model.fault == "short":
                        return len(data) - 4
                model.transfers.append(
                    (bytes(data), model.level(19), model.level(26), model.us)
                )
                model.us += len(data) * 1_000_000 // (48_000 * 4)
                return len(data)

            def deinit(self):
                # Audio must be muted and reset before DMA/PIO clocks stop.
                assert all(model.level(gpio) == 0 for gpio in (9, 19, 22, 26))
                self.closed = True
                model.events.append("deinit")
                if model.fault == "deinit":
                    raise OSError("I2S deinit failure")

        self.I2S = FakeI2S

    def changed(self, gpio, old, value):
        # This test never releases YM reset or performs a bus transaction.
        self.steps.append((self.us, gpio, old, value))
        assert self.level(9) == 0, "YM reset was released"
        assert all(self.level(g) == 1 for g in (13, 14, 15))
        assert all(p.mode == self.Pin.IN for g, p in self.pins.items() if g < 8)
        if gpio in (19, 26) and value and not old:
            assert self.level(22) == 1, "Unmute before ARM"
        if old != value:
            self.events.append((gpio, value))

    def load_dac(self, missing_i2s=False):
        bus = self.load()
        machine = types.SimpleNamespace(Pin=self.Pin)
        if not missing_i2s:
            machine.I2S = self.I2S
        spec = importlib.util.spec_from_file_location("dac_diagnostic", HERE / "rev_c_dac_check.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"machine": machine, "rev_c_bus_check": bus}):
            spec.loader.exec_module(module)
        return module, machine

    def run_dac(self, missing_i2s=False):
        module, machine = self.load_dac(missing_i2s)
        with patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()):
            module.run()
        return module

    def assert_stopped(self):
        super().assert_stopped()
        assert all(self.level(g) == 0 for g in (10, 11, 12))
        assert all(self.pins[g].mode == self.Pin.IN for g in (16, 17, 18, 28) if g in self.pins)
        assert not self.writes
        if self.audio is not None:
            assert self.audio.closed


class DACDiagnosticTests(unittest.TestCase):
    def test_three_tones_and_independent_dac_line_mutes(self):
        model = DACModel()
        module = model.run_dac()
        sounding = []
        for data, line, dac, unused_us in model.transfers:
            if line and dac and any(data):
                sounding.append(data)
        # Three two-second sample sequences, including 10 ms fade in/out.
        self.assertEqual(len(sounding) * module.FRAMES, 3 * 2 * module.RATE)
        self.assertTrue(any(any(d) and line and not dac for d, line, dac, t in model.transfers))
        self.assertTrue(any(any(d) and not line and dac for d, line, dac, t in model.transfers))
        self.assertEqual(sum(any(d) and line and not dac for d, line, dac, t in model.transfers), 100)
        self.assertEqual(sum(any(d) and not line and dac for d, line, dac, t in model.transfers), 100)
        self.assertEqual(model.events.count((19, 1)), 2)
        self.assertEqual(model.events.count((26, 1)), 2)
        # Explicit zero audio after each fade-out, before any mute change.
        ending = module._buffers()[3]
        for i, transfer in enumerate(model.transfers):
            if transfer[0] == ending:
                following = model.transfers[i + 1:i + 11]
                self.assertEqual(len(following), 10)
                self.assertTrue(all(not any(d) and line and dac for d, line, dac, t in following))
        model.assert_stopped()

    def test_waveform_frequency_level_channel_order_and_fades(self):
        module, unused = DACModel().load_dac()
        silence, steady, fade_in, fade_out = module._buffers()
        self.assertFalse(any(silence))
        samples = list(struct.iter_unpack("<hh", steady))
        left = [s[0] for s in samples]
        self.assertTrue(all(r == 0 for l, r in samples))
        self.assertEqual(max(left), 4096)
        self.assertEqual(min(left), -4096)
        self.assertEqual(sum(left), 0)
        # At 48 kHz a 1 kHz cycle is 48 frames, ten cycles in each chunk.
        for cycle in range(1, 10):
            self.assertEqual(left[:48], left[cycle * 48:(cycle + 1) * 48])
        for ramp in (fade_in, fade_out):
            for index, (l, r) in enumerate(struct.iter_unpack("<hh", ramp)):
                self.assertEqual(r, 0)
                self.assertLessEqual(abs(l), abs(left[index]))
        self.assertEqual(struct.unpack_from("<h", fade_in)[0], 0)
        self.assertEqual(struct.unpack_from("<h", fade_out, len(fade_out) - 4)[0], 0)

    def test_approved_i2s_map_and_pll_compatible_clock_rate(self):
        model = DACModel()
        module = model.run_dac()
        args = model.audio.kwargs
        self.assertEqual((args["sd"].gpio, args["sck"].gpio, args["ws"].gpio), (10, 11, 12))
        self.assertEqual(model.audio.ident, 0)
        self.assertEqual((args["bits"], args["rate"]), (16, 48000))
        self.assertEqual(args["format"], model.I2S.STEREO)
        self.assertGreater(module.FLUSH_MS, (module.IBUF + 512) / (module.RATE * 4) * 1000)
        self.assertNotIn(27, model.pins)
        self.assertNotIn(20, model.pins)
        self.assertNotIn(21, model.pins)
        model.assert_stopped()

    def test_interrupt_write_error_and_short_write_all_stop(self):
        for fault, exception in [("interrupt", KeyboardInterrupt), ("write", OSError), ("short", RuntimeError)]:
            with self.subTest(fault=fault):
                model = DACModel(fault=fault)
                with self.assertRaises(exception):
                    model.run_dac()
                model.assert_stopped()

    def test_no_i2s_or_failed_i2s_setup_never_unmutes(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                model = DACModel(fault="init")
                with self.assertRaises((OSError, RuntimeError)):
                    model.run_dac(missing_i2s=missing)
                self.assertNotIn((19, 1), model.events)
                self.assertNotIn((26, 1), model.events)
                self.assertNotIn((22, 1), model.events)
                model.assert_stopped()

    def test_partial_gpio_initialization_disarms(self):
        model = DACModel(fail_pin=16)
        with self.assertRaises(OSError):
            model.run_dac()
        model.assert_stopped()

    def test_deinit_failure_still_mutes_and_clears_i2s_pins(self):
        model = DACModel(fault="deinit")
        with self.assertRaisesRegex(OSError, "deinit failure"):
            model.run_dac()
        model.assert_stopped()

    def test_import_has_no_gpio_or_audio_side_effects(self):
        model = DACModel()
        model.load_dac()
        self.assertEqual(model.pins, {})
        self.assertEqual(model.events, [])


if __name__ == "__main__":
    unittest.main()
