# SPDX-License-Identifier: MIT
"""Live conversion arithmetic, bounded DMA ownership, and mute-on-failure."""
import ctypes
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
from test_rev_c_fm_playback import load as load_playback


HERE = Path(__file__).resolve().parent


def viper_reference(function):
    def call(source, destination):
        assert len(source) >= 625 * 4 and len(destination) >= 540 * 4
        return function(memoryview(source).cast("I"), memoryview(destination).cast("H"))
    return call


class LiveModel(BusModel):
    def __init__(self):
        super().__init__(allow_fm=True, allow_dac=True, allow_line=True)
        self.stream = None
        self.audio = None
        self.transfers = []
        self.gc_enabled = True
        model = self

        class I2S:
            TX, STEREO = 0, 1

            def __init__(self, *args, **kwargs):
                assert model.level(19) == model.level(26) == 0
                self.closed = False
                model.audio = self

            def write(self, data):
                if len(data) == 2160:
                    model.transfers.append((model.level(19), model.level(26), bytes(data)))
                return len(data)

            def deinit(self):
                assert model.level(19) == model.level(26) == model.level(22) == 0
                self.closed = True
        self.I2S = I2S

    def changed(self, gpio, old, value):
        super().changed(gpio, old, value)
        if self.level(19):
            assert self.level(26) == self.level(22) == self.level(9) == 1
            assert self.stream.starts >= 2, "Unmuted before silent stream preflight"

    def ticks_us(self):
        return self.us % (1 << 30)


def load(model):
    # Existing playback loader creates the verified capture and DAC helpers.
    playback, machine = load_playback(model)
    machine.I2S = model.I2S
    spec = importlib.util.spec_from_file_location("live_diagnostic", HERE / "rev_c_fm_live.py")
    module = importlib.util.module_from_spec(spec)
    module.ptr32 = module.ptr16 = object
    with patch.dict(sys.modules, {
        "machine": machine, "micropython": types.SimpleNamespace(viper=viper_reference),
        "rev_c_bus_check": types.SimpleNamespace(
            I2S_OUTPUT_GPIO=(10, 11, 12), _check_platform=lambda: None,
            _diagnose=playback._diagnose, _emergency_stop=playback._emergency_stop,
        ),
        "rev_c_fm_capture": types.SimpleNamespace(RevCFMBus=playback.RevCFMBus),
        "rev_c_dac_check": types.SimpleNamespace(_send=playback._send, _write=playback._write),
    }):
        spec.loader.exec_module(module)
    module.time = model
    module.gc = types.SimpleNamespace(
        isenabled=lambda: model.gc_enabled, collect=lambda: None,
        mem_free=lambda: 262144,
        mem_alloc=lambda: 65536,
        disable=lambda: setattr(model, "gc_enabled", False),
        enable=lambda: setattr(model, "gc_enabled", True),
    )
    return module, machine


def packed(values):
    return b"".join(struct.pack("<I", value << 19) for value in values)


class TestStream:
    __test__ = False

    def __init__(self, model, fault=None):
        self.model, self.fault = model, fault
        model.stream = self
        self.starts = self.sequence = self.max_convert_us = self.deadline_misses = 0
        self.closed = self.running = False
        self.phase = 0.0

    def open(self):
        pass

    def start(self):
        self.running = True
        self.starts += 1
        self.sequence = 0

    def take(self):
        assert self.running
        if self.starts >= 2 and self.fault == "deadline":
            raise RuntimeError("FM stream deadline missed")
        if self.starts >= 2 and self.fault == "interrupt":
            raise KeyboardInterrupt
        self.model.us += 11250
        registers = self.model.registers
        fnum = ((registers[0xA4] & 7) << 8) | registers[0xA0]
        block = (registers[0xA4] >> 3) & 7
        frequency = 4000000 / 72 * fnum * 2 ** block / 2 ** 21
        keyed = registers[0x28] == 0x10
        words = []
        for i in range(625):
            value = round(127 * math.sin(self.phase)) if keyed else 0
            self.phase = (self.phase + 2 * math.pi * frequency / (4000000 / 72)) % (2 * math.pi)
            words.append(0x400 | (512 + value))
        if self.starts >= 2 and self.fault == "invalid":
            words[0] = 0
        return packed(words)

    def check(self):
        assert self.running

    def release(self):
        self.sequence += 1

    def stop(self):
        self.running = False

    def close(self):
        self.model.assert_stopped()
        self.closed = True
        self.running = False


class LiveTests(unittest.TestCase):
    def test_pio_receiver_recovers_last13_at_each_sh_fall(self):
        module, unused = load(LiveModel())
        instructions, labels = [], {}
        rp2 = types.SimpleNamespace(PIO=types.SimpleNamespace(SHIFT_RIGHT=1),
                                    asm_pio=lambda **kwargs: lambda f: f)
        function = module.program(rp2)
        def emit(op):
            return lambda *args: instructions.append((op,) + args)
        with patch.dict(function.__globals__, {
            "wrap_target": lambda: None, "wrap": lambda: None,
            "label": lambda name: labels.update({name: len(instructions)}),
            "wait": emit("wait"), "set": emit("set"), "in_": emit("in"), "jmp": emit("jmp"),
            "gpio": "gpio", "pins": "pins", "x": "x", "x_dec": "x_dec",
        }):
            function()
        pc = counter = shifted = bits = 0
        recovered = []
        for cycle in range(8000):
            snapshot = cycle // 2  # 32 MHz PIO vs 16 MHz synthetic time base
            frame, within = divmod(snapshot, 288)
            bit, sub = divmod(within, 12)
            expected = 0x400 | (512 + (frame * 37 % 127))
            sd = (expected >> (bit - 11)) & 1 if bit >= 11 else 0
            pins = sd | (int(sub >= 6) << 1) | (int(within >= 276) << 2)
            instruction = instructions[pc]
            op = instruction[0]
            if op == "wait":
                _, polarity, kind, pin = instruction
                self.assertEqual(kind, "gpio")
                if (pins >> (pin - 16)) & 1 != polarity:
                    continue
            elif op == "set":
                counter = instruction[2]
            elif op == "in":
                self.assertEqual(instruction[1:], ("pins", 1))
                shifted = (shifted >> 1) | ((pins & 1) << 31)
                bits += 1
                if bits == 24:
                    recovered.append((shifted >> 19) & 8191)
                    bits = shifted = 0
            elif op == "jmp":
                old, counter = counter, (counter - 1) & 0xFFFFFFFF
                if old:
                    pc = labels[instruction[2]]
                    continue
            pc = (pc + 1) % len(instructions)
        self.assertGreater(len(recovered), 10)
        self.assertEqual(recovered, [0x400 | (512 + (i * 37 % 127)) for i in range(1, len(recovered) + 1)])

    def test_resampling_bounds_dc_silence_and_user_frame(self):
        module, unused = load(LiveModel())
        output = bytearray(2160)
        self.assertEqual(module.convert(packed([0x600] * 625), output), 0)
        self.assertFalse(any(output))
        self.assertEqual(module.convert(packed([0x67F] * 625), output), 127 * 32)
        self.assertTrue(all(l == 4064 and r == 0 for l, r in struct.iter_unpack("<hh", output)))
        for word in (0, 0x1FFF, 0x1C00):
            result = module.convert(packed([word] * 625), output)
            self.assertNotEqual(result >> 16, 0)
            self.assertTrue(all(abs(l) <= 4096 and r == 0 for l, r in struct.iter_unpack("<hh", output)))

    def test_native_arithmetic_matches_scalar_linear_interpolation(self):
        module, unused = load(LiveModel())
        values = [round(127 * math.sin(i * 0.17)) for i in range(625)]
        output = bytearray(2160)
        module.convert(packed([0x400 | (512 + v) for v in values]), output)
        samples = [l for l, r in struct.iter_unpack("<hh", output)]
        for i, actual in enumerate(samples):
            index, frac = divmod(i * 125, 108)
            self.assertEqual(actual, ((values[index] * (108 - frac) + values[index + 1] * frac) * 32) // 108)
        self.assertEqual((539 * 125) // 108 + 1, 624)
        self.assertEqual(540 * 125, 625 * 108)

    def test_live_scale_pitch_updates_and_muted_preflight(self):
        model = LiveModel()
        module, machine = load(model)
        with patch.object(module, "Stream", lambda: TestStream(model)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()):
            module.run()
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertTrue(model.gc_enabled)
        self.assertEqual(sum(g == 19 and old == 0 and value == 1 for t, g, old, value in model.steps), 2)
        self.assertTrue(any(line and any(data) for line, dac, data in model.transfers))
        self.assertTrue(any(not line and not dac and any(data) for line, dac, data in model.transfers))
        pitch_low = [v for r, v in model.writes if r == 0xA0]
        self.assertTrue(all(low in pitch_low for name, high, low in module.PITCHES))
        model.assert_stopped()

    def test_deadline_invalid_word_and_ctrl_c_mute_before_cleanup(self):
        for fault, error in (("deadline", RuntimeError), ("invalid", RuntimeError), ("interrupt", KeyboardInterrupt)):
            model = LiveModel()
            module, machine = load(model)
            with self.subTest(fault=fault), patch.object(module, "Stream", lambda: TestStream(model, fault)), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()), self.assertRaises(error):
                module.run()
            model.assert_stopped()
            self.assertTrue(model.stream.closed and model.audio.closed)
            self.assertTrue(model.gc_enabled)

    def test_memory_error_mutes_and_collects_before_allocating_cleanup(self):
        model = LiveModel()
        module, machine = load(model)
        failed = [False]

        class MemoryFaultStream(TestStream):
            def take(self):
                if self.model.level(19):
                    failed[0] = True
                    model.gc_enabled = False
                    raise MemoryError
                return super().take()

        def collect():
            if failed[0]:
                self.assertTrue(model.gc_enabled)
                self.assertEqual(model.level(19), 0)
                self.assertEqual(model.level(22), 0)

        original_close = module.LiveBus.close
        def close(bus):
            if not model.gc_enabled:
                raise MemoryError("Cleanup attempted while GC disabled")
            original_close(bus)

        module.gc.collect = collect
        output = io.StringIO()
        with patch.object(module, "Stream", lambda: MemoryFaultStream(model)), patch.object(module.LiveBus, "close", close), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(output), self.assertRaises(MemoryError):
            module.run()
        self.assertTrue(failed[0])
        self.assertIn("SAFE:", output.getvalue())
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertTrue(model.gc_enabled)
        model.assert_stopped()

    def test_gc_stays_enabled_during_live_playback_and_restores_previous_state(self):
        for initially_enabled in (True, False):
            model = LiveModel()
            model.gc_enabled = initially_enabled
            module, machine = load(model)
            original_write = model.I2S.write
            def write(audio, data):
                self.assertTrue(model.gc_enabled)
                return original_write(audio, data)
            with self.subTest(initial=initially_enabled), patch.object(module, "Stream", lambda: TestStream(model)), patch.object(model.I2S, "write", write), patch.dict(sys.modules, {"machine": machine}), redirect_stdout(io.StringIO()):
                module.run()
            self.assertEqual(model.gc_enabled, initially_enabled)

    def test_stream_deadline_and_dma_error_flags_fail_closed(self):
        model = LiveModel()
        module, unused = load(model)
        stream = module.Stream()
        stream.running = True
        stream.started = 0
        stream.mem32 = {module.FDEBUG: 0}
        stream.dmas = [types.SimpleNamespace(ctrl=0), types.SimpleNamespace(ctrl=0)]
        for elapsed, flags, dma_flags, message in ((22000, 0, 0, "deadline"), (0, 1, 0, "FIFO"), (0, 0, 1 << 29, "bus error")):
            model.us = elapsed
            stream.mem32[module.FDEBUG] = flags
            stream.dmas[0].ctrl = dma_flags
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                stream.check()

    def test_ping_pong_wait_rearm_order_and_clock_wrap(self):
        model = LiveModel()
        module, unused = load(model)
        origin = (1 << 30) - 10000
        model.us = origin
        calls = []

        class DMA:
            ctrl = 0

            def __init__(self, index):
                self.index = index

            def active(self):
                return ((model.us - origin) // 11250) % 2 == self.index

            def config(self, **kwargs):
                calls.append((self.index, kwargs))

        stream = module.Stream()
        stream.running = True
        stream.started = origin
        stream.mem32 = {module.FDEBUG: 0}
        stream.buffers = [bytearray(4096), bytearray(4096)]
        stream.dmas = [DMA(0), DMA(1)]
        self.assertIs(stream.take(), stream.buffers[0])
        self.assertEqual(model.us - origin, 11250)
        self.assertEqual(calls, [])
        stream.release()
        self.assertEqual(stream.sequence, 1)
        self.assertIs(stream.take(), stream.buffers[1])
        self.assertEqual(model.us - origin, 22500)
        stream.release()
        self.assertEqual([c[0] for c in calls], [0, 1])
        for index, kwargs in calls:
            self.assertIs(kwargs["write"], stream.buffers[index])
            self.assertEqual(kwargs["count"], 625)

    def test_lost_ownership_does_not_rearm_dma(self):
        model = LiveModel()
        module, unused = load(model)
        stream = module.Stream()
        stream.running = True
        stream.mem32 = {module.FDEBUG: 0}
        calls = []
        stream.buffers = [bytearray(4096), bytearray(4096)]
        stream.dmas = [types.SimpleNamespace(ctrl=0, active=lambda: True, config=lambda **k: calls.append(k)),
                       types.SimpleNamespace(ctrl=0, active=lambda: False, config=lambda **k: calls.append(k))]
        with self.assertRaisesRegex(RuntimeError, "ownership"):
            stream.release()
        self.assertEqual(calls, [])

    def test_ring_alignment_and_channel_links(self):
        model = LiveModel()
        module, machine = load(model)
        dmas = []

        class DMA:
            ctrl = 0

            def __init__(self):
                self.channel = 3 if not dmas else 6
                self.calls = []
                dmas.append(self)

            def pack_ctrl(self, **kwargs):
                self.options = kwargs
                return 0

            def config(self, **kwargs):
                self.calls.append(kwargs)

        sm = types.SimpleNamespace()
        machine.mem32 = {}
        with patch.object(module, "program", return_value="program"), patch.dict(sys.modules, {
            "rp2": types.SimpleNamespace(DMA=DMA, StateMachine=lambda *a, **k: sm),
            "machine": machine,
            "uctypes": types.SimpleNamespace(addressof=lambda b: ctypes.addressof(ctypes.c_char.from_buffer(b))),
        }):
            stream = module.Stream()
            stream.open()
        for i in range(2):
            buffer = stream.buffers[i]
            address = ctypes.addressof(ctypes.c_char.from_buffer(buffer))
            self.assertEqual(address % 4096, 0)
            self.assertEqual(len(buffer), 4096)
            self.assertEqual(dmas[i].options["chain_to"], dmas[1 - i].channel)
            self.assertEqual(dmas[i].options["ring_size"], 12)
            self.assertTrue(dmas[i].options["ring_sel"])
            self.assertEqual(dmas[i].calls[0]["count"], 625)

    def test_import_does_not_touch_gpio(self):
        model = LiveModel()
        load(model)
        self.assertEqual(model.pins, {})


if __name__ == "__main__":
    unittest.main()
