# SPDX-License-Identifier: MIT
"""Shortened model runs check continuity, GC guards and fail-closed cleanup."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_six_voice_check import PolyModel, PolyStream, load as load_six


HERE = Path(__file__).resolve().parent
SHORT_SEGMENTS = (3, 3, 3, 3, 3, 3)


def load(model):
    six, live, machine = load_six(model)
    model.deadline_check = live.Stream.check
    model.fdebug = live.FDEBUG
    spec = importlib.util.spec_from_file_location("endurance_diagnostic", HERE / "rev_c_endurance_check.py")
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {"rev_c_fm_live": live,
                                "rev_c_six_voice_check": six,
                                "rev_c_fm_ssg_check": types.SimpleNamespace(hold=six.hold)}):
        spec.loader.exec_module(module)
    return module, six, live, machine


class EnduranceStream(PolyStream):
    def __init__(self, model, fault=None):
        super().__init__(model)
        self.fault = fault
        self.continuous_states = []
        self.mem32 = {model.fdebug: 0}
        self.dmas = [types.SimpleNamespace(ctrl=0), types.SimpleNamespace(ctrl=0)]

    def start(self):
        super().start()
        self.started = self.model.ticks_us()

    def check(self):
        self.model.deadline_check(self)

    def take(self):
        if self.starts == 2 and self.model.level(19):
            self.continuous_states.append((self.starts, self.sequence,
                                           sum(r == 0x28 for r,v in self.model.writes)))
            if self.fault == "interrupt":
                raise KeyboardInterrupt
            if self.fault == "memory":
                raise MemoryError
            if self.fault == "deadline":
                self.model.us += 50000
            if self.fault == "signal":
                from test_rev_c_fm_live import packed
                return packed([0x600] * 625)
        return super().take()


class EnduranceTests(unittest.TestCase):
    def test_blocking_console_and_slow_gc_are_outside_continuous_stream(self):
        for gc_delay, console_delay in ((0,50000), (50000,0), (50000,50000)):
            with self.subTest(gc_delay=gc_delay, console_delay=console_delay):
                self.check_blocking_telemetry(gc_delay, console_delay)

    def check_blocking_telemetry(self, gc_delay, console_delay):
        model = PolyModel()
        module, six, live, machine = load(model)
        class BlockingOutput(io.StringIO):
            def write(self, data):
                # A slow USB/Thonny write consumes more than a DMA block's slack.
                if model.stream and model.stream.running and model.level(22):
                    raise AssertionError("Console output during active capture")
                model.us += console_delay
                return super().write(data)
        output = BlockingOutput()
        def collect():
            # Explicit heap walks are required to happen outside live capture.
            self.assertFalse(model.stream and model.stream.running and model.level(22))
            model.us += gc_delay
        with patch.object(module, "SEGMENT_BLOCKS", SHORT_SEGMENTS), patch.object(live, "Stream", lambda: EnduranceStream(model)), patch.object(live.gc, "collect", collect), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output):
            module.run()
        self.assertIn("DONE:", output.getvalue())
        self.assertEqual(len(model.stream.continuous_states), sum(SHORT_SEGMENTS))
        model.assert_stopped()

    def test_full_duration_is_180_seconds_without_oversized_counters(self):
        module, six, live, machine = load(PolyModel())
        self.assertEqual(sum(module.SEGMENT_BLOCKS), 16000)
        self.assertEqual(sum(module.SEGMENT_BLOCKS) * live.BLOCK_US, 180_000_000)
        self.assertTrue(all(29_990_000 <= n * live.BLOCK_US <= 30_010_000 for n in module.SEGMENT_BLOCKS))
        # Both absolute-duration math and a 625-frame DMA block fit small ints.
        self.assertLess(180_000_000, 1 << 29)

    def test_six_reports_preserve_one_stream_and_keys_then_stop_sources(self):
        model = PolyModel()
        module, six, live, machine = load(model)
        output = io.StringIO()
        snapshots = []
        def free():
            self.assertFalse(model.stream.running)
            snapshots.append((model.stream.starts, model.stream.running))
            return 262144
        with patch.object(module, "SEGMENT_BLOCKS", SHORT_SEGMENTS), patch.object(live, "Stream", lambda: EnduranceStream(model)), patch.object(live.gc, "mem_free", free), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output):
            module.run()
        states = model.stream.continuous_states
        self.assertEqual(len(states), sum(SHORT_SEGMENTS))
        self.assertEqual(len({keys for starts, seq, keys in states}), 1)
        self.assertEqual([seq for starts, seq, keys in states], list(range(12,30)))
        self.assertEqual(snapshots, [(1,False), (1,False), (2,False)])
        self.assertEqual(sum("/6 /" in line for line in output.getvalue().splitlines()), 6)
        self.assertIn("ENDURANCE COMPLETE / blocks=18 nominal_ms=202", output.getvalue())
        self.assertIn("delta=0", output.getvalue())
        observed = {(keys,line,dac,levels) for keys,line,dac,levels,periods in model.poly_transfers}
        self.assertIn(((True,True,True),1,1,(7,7,7)), observed)
        self.assertIn(((False,False,False),1,1,(0,0,0)), observed)
        self.assertIn("SAFE:", output.getvalue())
        self.assertIn("DONE:", output.getvalue())
        model.assert_stopped()
        self.assertTrue(model.stream.closed and model.audio.closed)

    def test_memory_sampling_rejects_running_capture_before_heap_walk(self):
        model = PolyModel()
        module, six, live, machine = load(model)
        with patch.object(live.gc, "collect", side_effect=AssertionError("Heap walk should not happen")), self.assertRaisesRegex(RuntimeError, "stopped"):
            module.memory_snapshot(types.SimpleNamespace(running=True))

    def test_real_deadline_guard_still_rejects_a_late_audio_block(self):
        self.check_fault("deadline", RuntimeError, "deadline")

    def test_low_post_gc_memory_is_detected_and_muted(self):
        for fault in ("low", "low_final"):
            with self.subTest(fault=fault):
                self.check_fault(fault, RuntimeError, "recovery margin")

    def test_interrupt_and_oom_during_continuous_audio_mute_and_close(self):
        for fault, exception in (("interrupt", KeyboardInterrupt), ("memory", MemoryError)):
            with self.subTest(fault=fault):
                self.check_fault(fault, exception)

    def test_lost_fm_signal_is_detected_and_muted(self):
        self.check_fault("signal", RuntimeError, "disappeared")

    def check_fault(self, fault, exception, message=None):
        model = PolyModel()
        module, six, live, machine = load(model)
        output = io.StringIO()
        free_calls = 0
        def free():
            nonlocal free_calls
            free_calls += 1
            return 32768 if (fault == "low" and free_calls == 2) or (fault == "low_final" and free_calls == 3) else 262144
        expectation = self.assertRaisesRegex(exception, message) if message else self.assertRaises(exception)
        with patch.object(module, "SEGMENT_BLOCKS", SHORT_SEGMENTS), patch.object(live, "Stream", lambda: EnduranceStream(model, fault)), patch.object(live.gc, "mem_free", free), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output), expectation:
            module.run()
        model.assert_stopped()
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertIn("SAFE:", output.getvalue())
        self.assertNotIn("DONE:", output.getvalue())

    def test_import_does_not_touch_pins(self):
        model = PolyModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
