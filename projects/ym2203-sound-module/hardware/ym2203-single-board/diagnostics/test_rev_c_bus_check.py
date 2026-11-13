# SPDX-License-Identifier: MIT
"""Host-side protocol checks; these do not substitute for electrical tests."""
from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch


HERE = Path(__file__).resolve().parent


class BusModel:
    def __init__(self, stuck_low=None, forced_status=None, interrupt_at=None, fail_pin=None,
                 allow_tone=False, interrupt_tone=False, bad_second_tone=False, allow_fm=False,
                 allow_dac=False, allow_line=False, allow_ssg_mix=False):
        self.pins = {}
        self.us = 0
        self.registers = [0] * (256 if allow_fm else 16)
        self.address = 0
        self.writes = []
        self.steps = []
        self.stuck_low = stuck_low
        self.forced_status = forced_status
        self.interrupt_at = interrupt_at
        self.fail_pin = fail_pin
        self.allow_tone = allow_tone
        self.allow_fm = allow_fm
        self.allow_dac = allow_dac
        self.allow_line = allow_line
        self.allow_ssg_mix = allow_ssg_mix
        self.interrupt_tone = interrupt_tone
        self.bad_second_tone = bad_second_tone
        self.tone_windows = []
        self.reads = 0
        self.last_rd_rise = -100
        self.last_rd_fall = -100
        self.last_cs_rise = -100
        self.last_cs_fall = -100
        self.last_data_input = -100
        model = self

        class FakePin:
            IN, OUT = 0, 1

            def __new__(cls, gpio, *args, **kwargs):
                if gpio == model.fail_pin:
                    model.fail_pin = None
                    raise OSError("Injected construction failure")
                if gpio not in model.pins:
                    obj = object.__new__(cls)
                    obj.gpio, obj.mode, obj.level = gpio, cls.IN, 0
                    if gpio in (13, 14, 15):
                        obj.level = 1
                    model.pins[gpio] = obj
                return model.pins[gpio]

            def __init__(self, gpio, mode=None, pull=None, *, value=None):
                if mode is not None:
                    self.init(mode, pull, value=value)

            def init(self, mode, pull=None, *, value=None):
                assert pull is None
                old = self.level
                self.mode = mode
                if value is not None:
                    self.level = value
                if self.gpio < 8:
                    if mode == self.IN:
                        model.last_data_input = model.us
                    else:
                        assert model.level(15) == 1, "Pico drives against U2 read buffer"
                        assert model.us - model.last_rd_rise >= 10
                model.changed(self.gpio, old, self.level)

            def value(self, value=None):
                if value is not None:
                    old, self.level = self.level, value
                    model.changed(self.gpio, old, value)
                    return
                assert self.mode == self.IN, "Reading an OUT Pin has undefined semantics"
                assert self.gpio < 8
                model.reads += 1
                if model.reads == model.interrupt_at:
                    raise KeyboardInterrupt
                assert model.level(22) == model.level(9) == 1
                assert model.level(13) == model.level(15) == 0
                assert model.level(14) == 1
                assert model.us - model.last_cs_fall >= 10
                value = model.read_data()
                return (value >> self.gpio) & 1

        self.Pin = FakePin

    def level(self, gpio):
        if gpio in self.pins:
            return self.pins[gpio].level
        return 1 if gpio in (13, 14, 15) else 0

    def changed(self, gpio, old, value):
        self.steps.append((self.us, gpio, old, value))
        # DAC stays muted in both diagnostics; analogue audio requires opt-in.
        if not self.allow_dac:
            assert self.level(26) == 0
        if not self.allow_tone and not self.allow_line:
            assert self.level(19) == 0
        if self.allow_tone and gpio == 19 and old != value:
            if value:
                assert self.level(22) == self.level(9) == 1
                channels = [i for i, level in enumerate(self.registers[8:11]) if level]
                assert len(channels) == 1
                channel = channels[0]
                assert self.registers[8 + channel] == 10
                assert self.registers[7] == 0x3F ^ (1 << channel)
                assert self.registers[2 * channel] == 142
                assert self.registers[2 * channel + 1] == 0
                self.tone_windows.append([channel, self.us, None])
            else:
                self.tone_windows[-1][2] = self.us
        if self.level(22) and not self.level(15):
            assert all(self.pins[i].mode == self.Pin.IN for i in range(8))
        if not self.level(22) or not self.level(9):
            self.registers = [0] * len(self.registers)
            self.address = 0
        if old == value:
            return
        if gpio == 15:
            assert self.level(13) == self.level(14) == 1
            if value:
                assert self.us - self.last_cs_rise >= 10
                self.last_rd_rise = self.us
            else:
                assert self.us - self.last_data_input >= 10
                self.last_rd_fall = self.us
        if gpio == 13:
            if value:
                self.last_cs_rise = self.us
            else:
                self.last_cs_fall = self.us
                if not self.level(15):
                    assert self.us - self.last_rd_fall >= 10
        if gpio == 14 and value and not self.level(13):
            assert self.level(15) == 1
            assert all(self.pins[i].mode == self.Pin.OUT for i in range(8))
            data = sum(self.level(i) << i for i in range(8))
            if self.stuck_low is not None:
                data &= ~(1 << self.stuck_low)
            if not self.level(8):
                self.address = data
            else:
                assert 0 <= self.address <= 10 or (self.allow_fm and 0x21 <= self.address <= 0xB2), "Unexpected FM or I/O-port write"
                self.registers[self.address] = data
                self.writes.append((self.address, data))
                if 8 <= self.address <= 10:
                    if self.allow_tone or self.allow_ssg_mix:
                        assert 0 <= data <= 10, "Diagnostic SSG level limit exceeded"
                    else:
                        assert data == 0, "SSG level must stay zero"

    def read_data(self):
        if self.forced_status is not None and not self.level(8):
            value = self.forced_status
        else:
            value = self.registers[self.address] if self.level(8) else 0
        if self.stuck_low is not None:
            value &= ~(1 << self.stuck_low)
        if self.bad_second_tone and self.tone_windows and self.level(8) and self.address == 2:
            value &= ~2
        return value

    def sleep_us(self, value):
        self.us += value

    def sleep_ms(self, value):
        if self.interrupt_tone and value == 2000 and self.level(19):
            self.interrupt_tone = False
            self.us += 1_000_000
            raise KeyboardInterrupt
        self.us += 1000 * value

    def ticks_ms(self):
        return (self.us // 1000) % (1 << 30)

    @staticmethod
    def ticks_diff(a, b):
        return ((a - b + (1 << 29)) % (1 << 30)) - (1 << 29)

    def load(self):
        spec = importlib.util.spec_from_file_location("rev_c_diagnostic", HERE / "rev_c_bus_check.py")
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, {"machine": types.SimpleNamespace(Pin=self.Pin)}):
            spec.loader.exec_module(module)
        module.time = self
        module._check_platform = lambda: None
        return module

    def assert_stopped(self):
        assert all(self.level(gpio) == 0 for gpio in (9, 19, 22, 26))
        assert all(self.pins[i].mode == self.Pin.IN for i in range(8))
        assert self.registers == [0] * len(self.registers)


class BusDiagnosticTests(unittest.TestCase):
    def test_readback_and_buffer_turnaround(self):
        model = BusModel()
        module = model.load()
        output = io.StringIO()
        with redirect_stdout(output):
            module.run()
        self.assertIn("PASS: silent bus read/write check complete", output.getvalue())
        self.assertEqual(output.getvalue().count("PASS reg="), 6)
        self.assertGreater(model.reads, 1000)
        self.assertTrue(model.writes)
        self.assertEqual({r for r, unused in model.writes}, set(range(11)) - {6})
        model.assert_stopped()

    def test_every_stuck_low_data_bit_is_detected(self):
        for bit in range(8):
            with self.subTest(bit=bit):
                model = BusModel(stuck_low=bit)
                with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                    model.load().run()
                model.assert_stopped()

    def test_permanent_busy_times_out_and_resets(self):
        model = BusModel(forced_status=0x80)
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "BUSY timeout"):
            model.load().run()
        self.assertGreaterEqual(model.us, 100000)
        self.assertLess(model.us, 200000)
        model.assert_stopped()

    def test_busy_timeout_across_ticks_wrap(self):
        model = BusModel(forced_status=0xFF)
        model.us = ((1 << 30) - 20) * 1000
        with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "BUSY timeout"):
            model.load().run()
        model.assert_stopped()

    def test_keyboard_interrupt_mutes_and_resets(self):
        model = BusModel(interrupt_at=50)
        with redirect_stdout(io.StringIO()), self.assertRaises(KeyboardInterrupt):
            model.load().run()
        model.assert_stopped()

    def test_partial_initialization_failure_disarms(self):
        model = BusModel(fail_pin=16)
        with redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            model.load().run()
        model.assert_stopped()

    def test_gpio_assignment_matches_manufactured_rev_c(self):
        module = BusModel().load()
        design = json.loads((HERE.parent / "rev-c/design.json").read_text())
        gp = {v["signal"]: v["gpio"] for v in design["gpio"]}
        for name, gpio in module.CONTROL_GPIO.items():
            self.assertEqual(gp[name.upper()], gpio)
        for bit, gpio in enumerate(module.DATA_GPIO):
            self.assertEqual(gp["D%d" % bit], gpio)
        self.assertEqual(module.FM_INPUT_GPIO, tuple(gp[n] for n in ("FM_SD", "FM_CLK", "FM_SH", "IRQ_N")))
        self.assertEqual(module.I2S_OUTPUT_GPIO, tuple(gp[n] for n in ("I2S_DATA", "I2S_BCLK", "I2S_LRCK")))
        self.assertNotIn(27, module.CONTROL_GPIO.values())

    def test_audio_enable_and_unsupported_registers_are_rejected(self):
        model = BusModel()
        module = model.load()
        board = module.RevCBus()
        try:
            board.start()
            for register, value in [(8, 1), (9, 16), (10, 15), (7, 0x3E), (14, 0), (0x28, 0xF0), (1, 16)]:
                with self.subTest(register=register), self.assertRaises(ValueError):
                    board.write_ssg(register, value)
        finally:
            board.close()
        self.assertEqual(model.writes, [])
        model.assert_stopped()


if __name__ == "__main__":
    unittest.main()
