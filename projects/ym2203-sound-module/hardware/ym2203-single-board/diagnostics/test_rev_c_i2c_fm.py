# SPDX-License-Identifier: MIT
"""Audio-block/I2C interleaving, control modes and fail-closed cleanup."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_fm_live import TestStream
from test_rev_c_fm_ssg_check import MixerModel, load as load_mixer
from test_rev_c_i2c_check import Registers, Link, load as load_transport
from test_rev_c_ssg_check import load_sound


HERE = Path(__file__).resolve().parent


class AudioRegisters(Registers):
    def __init__(self, model):
        super().__init__(model,allow_ssg=True,allow_fm=True)
        self.events = None
        self.values.update({0x400280A4:3,0x400280AC:3,0xD0000004:3 << 20})

    def __getitem__(self,address):
        if address == 0x40090034 and self.events is not None:
            event = self.events.popleft() if self.events else None
            self.values[address] = 0
            if isinstance(event,BaseException):
                raise event
            if isinstance(event,int):
                self.rx.append(event)
                self.values[0x40090070] = 0x40
            elif event == 'stop':
                self.values[0x40090070] = 0
                self.values[address] = 0x200
        return super().__getitem__(address)


def load(model):
    mixer,live,machine = load_mixer(model)
    real_check = live.Stream.check
    transport,host_link,regs = load_transport(model,AudioRegisters)
    ssg_bus = load_sound(model)
    modules = {'rev_c_fm_live':live,'rev_c_fm_ssg_check':mixer,
               'rev_c_i2c_target_check':transport,'rev_c_i2c_host_check':host_link,
               'rev_c_ssg_check':ssg_bus,'rev_c_bus_check':ssg_bus,
               'machine':types.SimpleNamespace(Pin=model.Pin,I2C=object)}
    def import_file(name,filename):
        spec = importlib.util.spec_from_file_location(name,HERE / filename)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules):
            spec.loader.exec_module(module)
        return module
    old_target = import_file('shared_ssg_target','rev_c_i2c_ssg_target.py')
    modules['rev_c_i2c_ssg_target'] = old_target
    shared_host = import_file('shared_ssg_host','rev_c_i2c_ssg_host.py')
    modules['rev_c_i2c_ssg_host'] = shared_host
    target = import_file('live_i2c_target','rev_c_i2c_fm_target.py')
    host = import_file('live_i2c_host','rev_c_i2c_fm_host.py')
    return target,host,shared_host,live,machine,transport,regs,real_check


class ClockedStream(TestStream):
    def __init__(self,model,real_check,fault=None):
        super().__init__(model,fault)
        self.real_check = real_check
        self.mem32 = {0x50200008:0}
        self.dmas = [types.SimpleNamespace(ctrl=0),types.SimpleNamespace(ctrl=0)]
        self.initial_us = 0

    def start(self):
        super().start()
        self.started = self.model.ticks_us()
        self.initial_us = self.model.us

    def take(self):
        # Capture advances on its own fixed clock, not on Python's bus-work time.
        due = self.initial_us + (self.sequence+1)*11250
        self.model.us = max(self.model.us,due)-11250
        return super().take()

    def check(self):
        self.real_check(self)


def command_events(command,wait=20):
    return [0x820,command,'stop'] + [None]*wait


class LiveI2CTests(unittest.TestCase):
    def test_ready_is_printed_only_after_i2c_is_enabled_while_capture_stopped(self):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        original = module.ControlTarget.prepare
        def prepare(target):
            original(target)
            regs.events = deque(command_events(7,0))
        class ReadyOutput(io.StringIO):
            def write(output,data):
                if data.startswith('READY:'):
                    self.assertEqual(regs.values.get(transport.IC_ENABLE,0),1,
                                     'READY advertised before address ACK was enabled')
                    self.assertFalse(model.stream.running)
                return super().write(data)
        with patch.object(live,'Stream',lambda:ClockedStream(model,guard)), patch.object(module.ControlTarget,'prepare',prepare), patch.dict(sys.modules,{'machine':machine}), redirect_stdout(ReadyOutput()):
            module.run()
        self.assertEqual(model.stream.starts,1)  # only the earlier silent preflight
        self.assertEqual(regs.values[transport.IC_ENABLE],0)
        model.assert_stopped()

    def test_changed_i2c_pin_mux_after_start_is_reported_and_stopped(self):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        original = module.ControlTarget.prepare
        def prepare(target):
            original(target)
            regs.events = deque(command_events(8,0))
        class BrokenMuxStream(ClockedStream):
            def start(stream):
                super().start()
                if stream.starts == 2:
                    regs.values[0x400280A4] = 5
        output = io.StringIO()
        with patch.object(live,'Stream',lambda:BrokenMuxStream(model,guard)), patch.object(module.ControlTarget,'prepare',prepare), patch.dict(sys.modules,{'machine':machine}), redirect_stdout(output), self.assertRaisesRegex(RuntimeError,'configuration mismatch after_start=True'):
            module.run()
        self.assertIn('I2C CONFIG BEFORE LIVE: [804, 66, 1, 1, 0, 3, 3, 3]',output.getvalue())
        self.assertIn('I2C CONFIG AFTER LIVE: [804, 66, 1, 1, 0, 5, 3, 3]',output.getvalue())
        self.assertIn('SAFE:',output.getvalue())
        self.assertNotIn('DONE:',output.getvalue())
        self.assertEqual(regs.values[transport.IC_ENABLE],0)
        self.assertTrue(model.stream.closed and model.audio.closed)
        model.assert_stopped()

    def test_runner_continuously_streams_all_modes_and_lease_mute(self):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        events = command_events(8,5)
        for command in (1,0,2,0,3,4,3,5,3,0):
            events += command_events(command)
        events += command_events(3,110)  # >1 s without a keepalive
        events += command_events(7,0)
        original = module.ControlTarget.prepare
        def prepare(target):
            original(target)
            regs.events = deque(events)
        def collect():
            self.assertFalse(model.stream and model.stream.running)
            self.assertEqual(model.level(19),0)
        output = io.StringIO()
        with patch.object(live,'Stream',lambda:ClockedStream(model,guard)), patch.object(live.gc,'collect',collect), patch.object(module.ControlTarget,'prepare',prepare), patch.dict(sys.modules,{'machine':machine}), redirect_stdout(output):
            module.run()
        states = set(model.mix_transfers)
        for state in ((True,1,1,(0,0,0),0x3E),(False,1,0,(10,0,0),0x3E),
                      (True,1,1,(10,0,0),0x3E),(True,1,0,(10,0,0),0x3E),
                      (True,0,1,(10,0,0),0x3E),(False,0,0,(0,0,0),0x3E)):
            self.assertIn(state,states)
        self.assertEqual(model.stream.starts,2)  # silent preflight, then one continuous run
        self.assertIn('lease_expirations=1',output.getvalue())
        self.assertIn('HOST I2C GP20/21'.lower(),output.getvalue().lower())
        self.assertNotIn('Host I2C disconnected',output.getvalue())
        self.assertIn('SAFE:',output.getvalue())
        self.assertIn('DONE:',output.getvalue())
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertEqual(regs.values[transport.IC_ENABLE],0)
        model.assert_stopped()

    def test_complete_hardware_host_script_with_audio_between_i2c_bytes(self):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        board = module.MixerBus()
        stream = ClockedStream(model,guard)
        pcm = bytearray(2160)
        target = module.ControlTarget(board)
        try:
            board.start()
            board.prepare()
            board.ssg('single')
            board.checked(8,0)
            stream.starts = 1  # this focused test starts after the preflight
            audio = model.I2S()
            target.prepare()
            target._enable(1)
            target.snapshot(False)
            def frame():
                target.poll()
                if target.start_requested and not target.live_started:
                    stream.start()
                    target.live_started = True
                    target.snapshot(True)
                if stream.running:
                    stream.check()
                    live.step(stream,pcm,audio)
                else:
                    model.us += 11250
            wire = Link(types.SimpleNamespace(poll=frame),regs)
            def sleep(ms):
                until = model.us + ms*1000
                while model.us < until:
                    frame()
            clock = types.SimpleNamespace(sleep_ms=sleep,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
            host.time = shared.time = clock
            output = io.StringIO()
            with redirect_stdout(output):
                host.check(wire)
            self.assertIn('capture STOPPED',output.getvalue())
            self.assertIn('live capture START acknowledged',output.getvalue())
            self.assertIn('FM capture running',output.getvalue())
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
            self.assertEqual(stream.starts,2)
            self.assertEqual(stream.deadline_misses,0)
        finally:
            board.close()
            stream.stop()
            target.close()
        model.assert_stopped()

    def test_bus_work_that_exceeds_audio_deadline_is_not_hidden(self):
        self.run_failure('slow')

    def test_interrupt_and_memory_error_while_mixed_mute_before_gc(self):
        for exception in (KeyboardInterrupt(),MemoryError()):
            with self.subTest(exception=type(exception)):
                self.run_failure(exception)

    def run_failure(self,fault):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        original_prepare = module.ControlTarget.prepare
        original_poll = module.ControlTarget.poll
        def prepare(target):
            original_prepare(target)
            events = command_events(8,5) + command_events(3,5)
            if isinstance(fault,BaseException):
                events += [fault]
            regs.events = deque(events)
        def poll(target):
            original_poll(target)
            if target.mode == 3 and fault == 'slow':
                model.us += 50000
        def collect():
            self.assertEqual(model.level(19),0)
            self.assertFalse(model.stream and model.stream.running)
        output = io.StringIO()
        exception = type(fault) if isinstance(fault,BaseException) else RuntimeError
        with patch.object(live,'Stream',lambda:ClockedStream(model,guard)), patch.object(live.gc,'collect',collect), patch.object(module.ControlTarget,'prepare',prepare), patch.object(module.ControlTarget,'poll',poll), patch.dict(sys.modules,{'machine':machine}), redirect_stdout(output), self.assertRaises(exception):
            module.run()
        self.assertIn('SAFE:',output.getvalue())
        self.assertNotIn('DONE:',output.getvalue())
        self.assertEqual(regs.values[transport.IC_ENABLE],0)
        self.assertTrue(model.stream.closed and model.audio.closed)
        model.assert_stopped()

    def test_invalid_modes_and_late_keep_never_enable_unrequested_sound(self):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        board = module.MixerBus()
        target = module.ControlTarget(board)
        try:
            board.start()
            for value in (-1,6,8,True):
                with self.assertRaises(ValueError):
                    target.set_mode(value)
            before = len(model.writes)
            for command in (9,255):
                with self.assertRaises(ValueError):
                    target.apply(command)
            self.assertEqual(len(model.writes),before)
            for command in range(1,6):
                with self.assertRaisesRegex(RuntimeError,'START must complete'):
                    target.apply(command)
            self.assertEqual(len(model.writes),before)
            target.window.data[0x13] = 1
            target.apply(6)
            self.assertEqual(target.mode,0)
            self.assertEqual(target.window.data[0x13],1)
            self.assertEqual(model.level(19),0)
        finally:
            board.close()
        model.assert_stopped()

    def test_import_does_not_touch_pins_or_peripheral(self):
        model = MixerModel()
        module,host,shared,live,machine,transport,regs,guard = load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(regs.accesses,[])


if __name__ == '__main__':
    unittest.main()
