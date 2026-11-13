# SPDX-License-Identifier: MIT
"""Bounded pitch changes through real bus methods and independently timed I2C."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_fm_ssg_check import MixerModel
from test_rev_c_i2c_fm import ClockedStream, command_events
from test_rev_c_i2c_fm_staged import load as load_staged
from test_rev_c_i2c_fm_scheduling import SampledLink

HERE = Path(__file__).resolve().parent


def load(model):
    values = load_staged(model)
    staged,host,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
    def source(name,modules):
        spec = importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules):
            spec.loader.exec_module(module)
        return module
    target = source('rev_c_i2c_pitch_target',{'rev_c_i2c_fm_staged_target':staged})
    remote = source('rev_c_i2c_pitch_host',{'rev_c_i2c_fm_staged_host':host})
    target.gc = live.gc
    return target,remote,values


def fixture():
    model = MixerModel()
    target_module,host,values = load(model)
    staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
    board = control.MixerBus()
    board.start()
    board.prepare()
    board.ssg('single')
    board.checked(8,0)
    model.stream = types.SimpleNamespace(starts=2)
    target = target_module.PitchTarget(board)
    target.prepare()
    target._enable(1)
    wire = SampledLink(model,target,regs,transport)
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    host.time = mixer.time = mixer.shared.time = clock
    return model,target_module,host,target,board,wire,values


class PitchTests(unittest.TestCase):
    def test_complete_36_note_host_and_real_register_values_with_idle_sampling(self):
        model,module,host,target,board,wire,values = fixture()
        notes = []
        original = target.apply
        def apply(command):
            before = len(model.writes)
            original(command)
            if command in (1,2) and len(notes) < 36:
                notes.append((command,0))  # preselected C begins at gate-on
            if command >= 0x40:
                fm = command < 0x50
                note = command-(0x40 if fm else 0x50)
                expected = [(0xA4,module.control.live.PITCHES[note][1]),(0xA0,module.control.live.PITCHES[note][2])] if fm else [(0,module.SSG_PERIODS[note]&255),(1,module.SSG_PERIODS[note]>>8)]
                self.assertEqual(model.writes[before:],expected)
                self.assertEqual(model.level(19),int(target.mode != 0))
                if target.mode:
                    self.assertEqual(target.mode,1 if fm else 2)
                    notes.append((target.mode,note))
        target.apply = apply
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                host.check_live(wire)
            wire.sleep_ms(30)
            self.assertEqual(notes,[(mode,n) for mode in (1,2) for _ in range(2) for n in host.MELODY])
            self.assertEqual(target.expirations,1)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.window.data[0x14:0x16],b'\0\0')
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,target.window.data[0x10])
            self.assertIn('HOST PASS:',output.getvalue())
            self.assertEqual(len(re.findall(r'NOTE \d/9',output.getvalue())),36)
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_pitch_guards_before_start_expired_and_wrong_source(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            before = len(model.writes)
            with self.assertRaisesRegex(RuntimeError,'requires START'):
                target.apply(0x40)
            for command in (-1,9,0x3F,0x45,0x4F,0x55,255,True):
                with self.assertRaises(ValueError):
                    target.apply(command)
            self.assertEqual(len(model.writes),before)
            target.live_started = True
            target.apply(1)
            before = len(model.writes)
            with self.assertRaisesRegex(ValueError,'matching solo'):
                target.apply(0x50)
            self.assertEqual(len(model.writes),before)
            wire.sleep_ms(1200)
            self.assertEqual(target.mode,0)
            before = len(model.writes)
            for command in (0x40,0x50):
                with self.assertRaisesRegex(RuntimeError,'non-expired'):
                    target.apply(command)
            self.assertEqual(len(model.writes),before)
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_pitch_readback_error_does_not_commit_ack(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            target.live_started = True
            ack = target.window.data[0x10]
            with patch.object(board,'read_ssg',return_value=255),self.assertRaisesRegex(RuntimeError,'readback mismatch'):
                target.apply(0x50)
            self.assertEqual(target.window.data[0x10],ack)
            self.assertEqual(target.window.data[0x15],255)
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_host_pitch_transfer_failure_is_not_replayed(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values = fixture()
            original = wire.writeto
            calls = []
            def write(address,data,stop=True):
                if data == b'\x20\x41':
                    calls.append(data)
                    raise error('injected note failure')
                return original(address,data,stop)
            wire.writeto = write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error):
                    host.check_live(wire)
                self.assertEqual(calls,[b'\x20\x41'])
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1200)
                self.assertEqual(target.mode,0)
                self.assertEqual(target.expirations,1)
            finally:
                board.close()
                target.close()
            model.assert_stopped()

    def test_host_rejects_old_signature_before_sound_or_start(self):
        model,module,host,target,board,wire,values = fixture()
        target.window.data[:8] = b'RCMIX02!'
        try:
            with self.assertRaisesRegex(RuntimeError,'signature mismatch'):
                host.check_live(wire)
            self.assertEqual(wire.command_writes,0)
            self.assertFalse(target.live_started)
        finally:
            board.close()
            target.close()

    def test_state_verification_detects_corrupt_pitch_index(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            remote = host.Remote(wire)
            target.window.data[0x14] = 0
            with self.assertRaisesRegex(RuntimeError,'Pitch state mismatch'):
                host.verify(wire,remote,0,0,[255,255])
            self.assertEqual(wire.command_writes,0)
        finally:
            board.close()
            target.close()

    def test_staged_runner_pitch_work_and_failures_use_native_deadline_and_cleanup(self):
        for fault in (None,'slow',MemoryError,KeyboardInterrupt):
            with self.subTest(fault=fault):
                model = MixerModel()
                module,host,values = load(model)
                staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
                phases = []
                def listen(endpoint):
                    phases.append(endpoint.window.phase)
                    endpoint.window.finished = True
                original_prepare = module.PitchTarget.prepare
                def prepare(endpoint):
                    original_prepare(endpoint)
                    regs.events = deque(command_events(8,5)+command_events(0x40,5)+command_events(1,5)+command_events(0x41,5)+command_events(7,0))
                original_pitch = control.MixerBus.pitch
                def pitch(bus,note):
                    if note == 1:
                        if fault == 'slow':
                            model.us += 50000
                        elif fault is not None:
                            raise fault('injected pitch fault')
                    original_pitch(bus,note)
                output = io.StringIO()
                with patch.object(startup,'listen',listen),patch.object(live,'Stream',lambda:ClockedStream(model,guard)),patch.object(module.PitchTarget,'prepare',prepare),patch.object(control.MixerBus,'pitch',pitch),redirect_stdout(output):
                    if fault is None:
                        module.run()
                    else:
                        with self.assertRaises(RuntimeError if fault == 'slow' else fault):
                            module.run()
                self.assertEqual(phases,list(range(6)))
                self.assertIn('SAFE:',output.getvalue())
                self.assertEqual('DONE:' in output.getvalue(),fault is None)
                self.assertEqual(regs.values[transport.IC_ENABLE],0)
                self.assertTrue(model.stream.closed and model.audio.closed)
                model.assert_stopped()

    def test_import_is_silent(self):
        model = MixerModel()
        module,host,values = load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(values[-2].accesses,[])


if __name__ == '__main__':
    unittest.main()
