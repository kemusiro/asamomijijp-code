# SPDX-License-Identifier: MIT
"""Synthetic serial traces and fail-safe tests; not physical FM verification."""
from array import array
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_bus_check import BusModel


HERE = Path(__file__).resolve().parent


def trace(vary=False, missing=None, bad_timing=False, length=131072, frame_value=None):
    # A deliberately synthetic protocol source: 24 clocks/frame, 12 samples/clock,
    # SD changes at falling CLK, SH falls after S2. Last 13 bits are LSB-first.
    words = array("I")
    packed = 0
    for sample in range(length):
        frame, within = divmod(sample, 24 * 12)
        bit, sub = divmod(within, 12)
        value = (0x1500 + (frame * 37 % 511)) if vary else 0x1000
        if frame_value is not None:
            value = frame_value(frame)
        sd = (value >> (bit - 11)) & 1 if bit >= 11 else 0
        clk = int(sub >= 6)
        sh = int(within >= 23 * 12)  # high for last bit, falling at frame boundary
        if bad_timing and frame % 3 == 0 and bit == 20:
            clk = 0
        pins = sd | (clk << 1) | (sh << 2)
        if missing is not None:
            pins &= ~(1 << missing)
        packed |= pins << (8 + (sample % 8) * 3)
        if sample % 8 == 7:
            words.append(packed)
            packed = 0
    return words


def load(model):
    bus = model.load()
    spec = importlib.util.spec_from_file_location("fm_capture_diagnostic", HERE / "rev_c_fm_capture.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"machine": types.SimpleNamespace(Pin=model.Pin), "rev_c_bus_check": bus}):
        spec.loader.exec_module(module)
    module.time = model
    return module


class FakeCapture:
    def __init__(self, model, fail_open=False, fail_read=False):
        self.model, self.fail_open, self.fail_read = model, fail_open, fail_read
        self.closed = False
        self.keys = []

    def open(self):
        if self.fail_open:
            raise OSError("PIO/DMA unavailable")

    def read(self):
        if self.fail_read:
            raise KeyboardInterrupt
        assert self.model.level(19) == self.model.level(26) == 0
        key = self.model.registers[0x28]
        self.keys.append(key)
        return trace(vary=key == 0x10)

    def close(self):
        self.model.assert_stopped()
        self.closed = True


class FMCaptureTests(unittest.TestCase):
    def test_capture_allocation_without_array_repetition(self):
        module = load(BusModel())

        class MicroPythonArray(array):
            def __mul__(self, count):
                raise TypeError("unsupported types for __mul__: 'array', 'int'")

            __rmul__ = __mul__

        with patch.object(module, "array", MicroPythonArray):
            capture = module.Capture()
        self.assertEqual(len(capture.words), module.WORDS)
        self.assertEqual(capture.words.itemsize, 4)
        self.assertFalse(any(capture.words))
        self.assertEqual(memoryview(capture.words).nbytes, 65536)
        capture.words[-1] = 0xFFFFFFFF
        self.assertEqual(capture.words[-1], 0xFFFFFFFF)
        self.assertIsNone(capture.sm)
        self.assertIsNone(capture.dma)

    def capture_fixture(self, fault=None):
        model = BusModel()
        module = load(model)

        class Memory:
            value = 0

            def __setitem__(self, address, value):
                self.assert_address(address)
                self.value &= ~value  # write-one-to-clear, not ordinary RAM

            def __getitem__(self, address):
                self.assert_address(address)
                return self.value

            @staticmethod
            def assert_address(address):
                assert address == 0x50200008

        memory = Memory()

        class DMA:
            running = False
            closed = False
            ctrl = 0

            def pack_ctrl(self, **kwargs):
                self.settings = kwargs
                return 123

            def config(self, **kwargs):
                self.configured = kwargs
                self.running = kwargs["trigger"]

            def active(self, value=None):
                if value is not None:
                    self.running = bool(value)
                return self.running

            def unpack_ctrl(self, ctrl):
                return {k: fault == "bus" for k in ("read_err", "write_err", "ahb_err")}

            def close(self):
                self.running = False
                self.closed = True

        dma = DMA()

        class SM:
            running = False
            restarted = False
            stale = [1, 2]

            def active(self, value):
                self.running = bool(value)
                if value:
                    if fault == "stall":
                        memory.value |= 1
                    if fault != "timeout":
                        dma.running = False

            def restart(self):
                self.restarted = True

            def rx_fifo(self):
                return len(self.stale)

            def get(self):
                return self.stale.pop()

            def put(self, value):
                self.counter = value

        capture = module.Capture()
        capture.sm, capture.dma, capture.mem32 = SM(), dma, memory
        return model, module, capture

    def test_finite_dma_configuration_and_stale_fifo_drain(self):
        unused, module, capture = self.capture_fixture()
        self.assertIs(capture.read(), capture.words)
        self.assertTrue(capture.sm.restarted)
        self.assertEqual(capture.sm.stale, [])
        self.assertEqual(capture.sm.counter, 131072 - 1)
        self.assertEqual(capture.dma.configured["count"], 16384)
        self.assertIs(capture.dma.configured["read"], capture.sm)
        self.assertEqual(capture.dma.settings, {
            "size": 2, "inc_read": False, "inc_write": True, "treq_sel": 4,
            "high_pri": True, "bswap": False,
        })
        self.assertFalse(capture.sm.running)
        self.assertFalse(capture.dma.running)
        capture.close()
        self.assertTrue(capture.dma.closed)

    def test_dma_timeout_and_stall_bus_errors_do_not_return_bad_data(self):
        for fault, message in (("timeout", "timeout"), ("stall", "RX stalled"), ("bus", "bus error")):
            with self.subTest(fault=fault):
                model, module, capture = self.capture_fixture(fault)
                with self.assertRaisesRegex(RuntimeError, message):
                    capture.read()
                self.assertFalse(capture.sm.running)
                self.assertFalse(capture.dma.running)
                if fault == "timeout":
                    self.assertGreaterEqual(model.us, 500_000)
                    self.assertLess(model.us, 510_000)
                capture.close()

    def test_partial_capture_can_be_closed(self):
        model, module, capture = self.capture_fixture()
        dma = capture.dma
        capture.sm = None
        capture.close()
        self.assertTrue(dma.closed)
        capture.dma = None
        capture.close()

    def test_serial_order_partial_first_frame_and_frequency_measurement(self):
        module = load(BusModel())
        result = module.analyze(trace(vary=True))
        self.assertEqual(result["samples"], 131072)
        self.assertEqual(set(result["bit_counts"]), {24})
        self.assertGreater(result["frames"], 400)
        self.assertGreater(result["unique"], 100)
        self.assertAlmostEqual(result["clk_hz"], 16_000_000 / 12)
        self.assertAlmostEqual(result["sh_hz"], 16_000_000 / (24 * 12))
        # Initial partial frame is excluded. Frame 1 is the first complete frame.
        self.assertEqual(result["head"][:3], [0x1500 + i * 37 % 511 for i in (1, 2, 3)])
        with redirect_stdout(io.StringIO()):
            module.report("synthetic", result)

    def test_retaining_frames_is_explicit_and_does_not_change_statistics(self):
        module = load(BusModel())
        words = trace(vary=True)
        summary = module.analyze(words)
        full = module.analyze(words, keep_frames=True)
        self.assertNotIn("data", summary)
        frames = full.pop("data")
        self.assertEqual(full, summary)
        self.assertEqual(len(frames), summary["frames"])
        self.assertEqual(frames[:16], summary["head"])

    def test_missing_clocks_sync_and_inconsistent_frames_are_rejected(self):
        module = load(BusModel())
        for source in (trace(missing=1), trace(missing=2), trace(bad_timing=True)):
            with redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
                module.report("fault", module.analyze(source))

    def test_run_keeps_both_audio_gates_off_and_resets_before_capture_close(self):
        model = BusModel(allow_fm=True)
        module = load(model)
        capture = FakeCapture(model)
        output = io.StringIO()
        with patch.object(module, "Capture", return_value=capture), redirect_stdout(output):
            module.run()
        self.assertEqual(capture.keys, [0, 0x10, 0])
        self.assertTrue(capture.closed)
        self.assertIn("PASS: FM clocks/frames/key response detected.", output.getvalue())
        # SSG stays silent. Only channel 1/slot 1 is keyed on, no prescaler/test writes.
        keys = [v for r, v in model.writes if r == 0x28]
        self.assertEqual(keys, [0, 1, 2, 0, 0x10, 0])
        self.assertNotIn(0x2D, [r for r, v in model.writes])
        self.assertTrue(all(v == 0 for r, v in model.writes if r in (8, 9, 10)))
        self.assertTrue(all(v >= 48 for r, v in model.writes if r in (0x40, 0x44, 0x48, 0x4C)))
        model.assert_stopped()

    def test_fm_write_allowlist_rejects_other_channels_and_loud_levels(self):
        model = BusModel(allow_fm=True)
        module = load(model)
        bus = module.RevCFMBus()
        try:
            bus.start()
            for register, value in ((0x2D, 0), (0x21, 1), (0x41, 48), (0x40, 0),
                                    (0x28, 0xF0), (0x28, 0x20), (0xB0, 0),
                                    (True, 0), (0x40, True), (0x40, 48.0)):
                with self.subTest(register=register, value=value), self.assertRaises(ValueError):
                    bus.write_fm(register, value)
        finally:
            bus.close()
        self.assertEqual(model.writes, [])
        model.assert_stopped()

    def test_preflight_failure_never_initializes_capture_or_keys_on(self):
        model = BusModel(allow_fm=True, stuck_low=0)
        module = load(model)
        with patch.object(module, "Capture") as factory, redirect_stdout(io.StringIO()), self.assertRaises(RuntimeError):
            module.run()
        factory.assert_not_called()
        self.assertFalse(any(r == 0x28 and v == 0x10 for r, v in model.writes))
        model.assert_stopped()

    def test_open_failure_and_capture_interrupt_stop_and_close(self):
        for fail_open in (True, False):
            with self.subTest(fail_open=fail_open):
                model = BusModel(allow_fm=True)
                module = load(model)
                capture = FakeCapture(model, fail_open=fail_open, fail_read=not fail_open)
                with patch.object(module, "Capture", return_value=capture), redirect_stdout(io.StringIO()), self.assertRaises((OSError, KeyboardInterrupt)):
                    module.run()
                self.assertTrue(capture.closed)
                model.assert_stopped()

    def test_stuck_sd_or_unchanging_frames_do_not_pass(self):
        for missing in (None, 0):
            model = BusModel(allow_fm=True)
            module = load(model)
            capture = FakeCapture(model)
            capture.read = lambda: trace(missing=missing)
            with patch.object(module, "Capture", return_value=capture), redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, "did not change"):
                module.run()
            self.assertTrue(capture.closed)
            model.assert_stopped()

    def test_import_has_no_gpio_or_peripheral_side_effects(self):
        model = BusModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
