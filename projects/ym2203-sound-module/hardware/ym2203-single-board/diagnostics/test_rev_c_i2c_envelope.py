# SPDX-License-Identifier: MIT
"""Envelope/key protocol and bus writes; no FM envelope waveform is simulated."""
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
from test_rev_c_i2c_timbre import load as load_timbre
from test_rev_c_i2c_fm_scheduling import SampledLink

HERE=Path(__file__).resolve().parent


def load(model):
    timbre,host,values=load_timbre(model)
    def source(name,modules):
        spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules): spec.loader.exec_module(module)
        return module
    target=source('rev_c_i2c_envelope_target',{'rev_c_i2c_timbre_target':timbre})
    remote=source('rev_c_i2c_envelope_host',{'rev_c_i2c_timbre_host':host})
    target.gc=timbre.gc
    return target,remote,values


def fixture():
    model=MixerModel()
    module,host,values=load(model)
    staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
    board=module.EnvelopeBus()
    board.start(); board.prepare(); board.ssg('single'); board.checked(8,0)
    board.configure('serial'); board.timbre_ready=True; board.envelope(1)
    model.stream=types.SimpleNamespace(starts=2)
    target=module.EnvelopeTarget(board)
    target.prepare(); target._enable(1)
    wire=SampledLink(model,target,regs,transport)
    host.time=mixer.time=mixer.shared.time=types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    return model,module,host,target,board,wire,values


class EnvelopeTests(unittest.TestCase):
    def test_complete_HOST_presets_and_key_off_leave_both_audio_gates_open(self):
        model,module,host,target,board,wire,values=fixture()
        presets=[]; keys=[]
        pending=[]
        original=target.apply
        original_commit=target._commit_preset
        def commit():
            command,before=pending.pop()
            p=command-0x80
            self.assertEqual(model.writes[before:],[(base+slot,value) for slot in (0,4,8,12) for base,value in ((0x60,12 if p else 0),(0x80,0x8F if p else 15))])
            self.assertEqual((model.level(19),model.level(26)),(0,0))
            original_commit()
            presets.append(p)
        target._commit_preset=commit
        def apply(command):
            before=len(model.writes)
            original(command)
            if command in (0x80,0x81):
                self.assertEqual(model.writes[before:],[])
                self.assertEqual((model.level(19),model.level(26)),(0,0))
                self.assertEqual(model.registers[0x4C],64)
                pending.append((command,before))
            if command in (0x30,0x31):
                keyed=int(command==0x30)
                self.assertEqual(model.writes[before:],[(0x28,0xF0 if keyed else 0)])
                self.assertEqual((target.mode,target.mask,target.keyed),(1,1,bool(keyed)))
                self.assertEqual((model.level(19),model.level(26)),(1,1))
                self.assertEqual(target.window.data[0x15],keyed)
                keys.append(command)
            self.assertEqual(model.registers[8:11],[0,0,0])
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()) as output: host.check_live(wire)
            wire.sleep_ms(30)
            self.assertEqual(presets,[0,1,0])
            self.assertEqual((target.preset_updates,target.preset_writes),(3,24))
            self.assertEqual(keys,[0x31,0x30,0x31,0x30])
            self.assertEqual([v for r,v in model.writes if r==0x28].count(0xF0),5)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
            self.assertEqual((target.mode,target.keyed),(0,False))
            self.assertEqual(target.window.data[0x14:0x16],b'\0\0')
            expected=int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(target.window.data[0x10],expected)
            self.assertEqual(expected,wire.command_writes&255)
            self.assertIn('HOST PASS:',output.getvalue())
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_prestart_invalid_wrong_mode_and_duplicate_key_commands_rejected(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            before=len(model.writes)
            for c in (0x30,0x31,0x80,0x81):
                with self.assertRaisesRegex(RuntimeError,'requires START'): target.apply(c)
            for c in (-1,2,3,4,5,9,0x2F,0x32,0x40,0x60,0x7F,0x82,255,True):
                with self.assertRaises(ValueError): target.apply(c)
            self.assertEqual(len(model.writes),before)
            target.live_started=True
            with self.assertRaisesRegex(ValueError,'open FM mode'): target.apply(0x30)
            target.apply(1)
            for c in (0x80,0x81):
                with self.assertRaisesRegex(ValueError,'require STOP'): target.apply(c)
            with self.assertRaisesRegex(ValueError,'repeat'): target.apply(0x30)
            target.apply(0x31)
            with self.assertRaisesRegex(ValueError,'repeat'): target.apply(0x31)
            before=len(model.writes)
            target.apply(1) # repeated FM mode does not retrigger a held-off key
            self.assertEqual(len(model.writes),before)
            self.assertFalse(target.keyed)
            self.assertEqual(target.window.data[0x15],0)
        finally:
            board.close(); target.close()

    def test_key_off_state_lease_expiry_closes_gates_and_late_commands_cannot_restart(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            target.apply(1); target.apply(0x31)
            self.assertEqual((target.mode,model.level(19),model.level(26)),(1,1,1))
            wire.sleep_ms(1200)
            self.assertEqual((target.mode,target.keyed,model.level(19),model.level(26)),(0,False,0,0))
            target.apply(6)
            self.assertEqual(target.window.data[0x13],1)
            before=len(model.writes)
            for c in (0x30,0x31,0x80,0x81):
                with self.assertRaisesRegex(RuntimeError,'non-expired'): target.apply(c)
            self.assertEqual(len(model.writes),before)
        finally:
            board.close(); target.close()

    def test_partial_envelope_write_failure_does_not_commit_preset_or_ACK(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            original=board._write_tone
            def write(reg,value):
                if reg==0x88: raise RuntimeError('injected partial envelope failure')
                original(reg,value)
            before=bytes(target.window.data[0x10:0x16])
            with patch.object(board,'_write_tone',write),self.assertRaisesRegex(RuntimeError,'partial envelope'):
                target.apply(0x80)
                for unused in range(8): target.poll()
            self.assertEqual(bytes(target.window.data[0x10:0x16]),before)
        finally:
            board.close(); target.close()

    def test_signature_and_key_state_mismatch_rejected(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            for signature in (b'RCTIM01!',b'RCENV01!'):
                target.window.data[:8]=signature
                with self.assertRaisesRegex(RuntimeError,'signature mismatch'): host.check_live(wire)
            self.assertEqual(wire.command_writes,0)
            remote=host.Remote(wire)
            target.window.data[0x15]=1
            with self.assertRaisesRegex(RuntimeError,'Envelope state mismatch'): host.verify(wire,remote,0,0,1,0)
        finally:
            board.close(); target.close()

    def test_key_off_transfer_faults_are_not_replayed_and_watchdog_mutes(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values=fixture()
            original=wire.writeto; calls=[]
            def write(address,data,stop=True):
                if data==b'\x20\x31':
                    calls.append(data)
                    raise error('injected key off transfer failure')
                return original(address,data,stop)
            wire.writeto=write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error): host.check_live(wire)
                self.assertEqual(calls,[b'\x20\x31'])
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1200)
                self.assertEqual((target.mode,target.keyed),(0,False))
            finally:
                board.close(); target.close()

    def test_muted_setup_and_staged_cleanup_for_preset_deadline_and_exceptions(self):
        for fault in (None,'slow',MemoryError,KeyboardInterrupt):
            model=MixerModel(); module,host,values=load(model)
            staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
            def listen(endpoint):
                if endpoint.window.phase==5:
                    self.assertFalse(model.stream.running)
                    self.assertEqual((model.level(19),model.level(26)),(0,0))
                    for slot in (0,4,8,12):
                        self.assertEqual((model.registers[0x60+slot],model.registers[0x80+slot]),(12,0x8F))
                endpoint.window.finished=True
            original=module.EnvelopeTarget.prepare
            def prepare(endpoint):
                original(endpoint)
                regs.events=deque(command_events(8,5)+command_events(0x80,40)+command_events(1,5)+command_events(0x31,5)+command_events(0x30,5)+command_events(7,0))
            original_env=module.EnvelopeBus.envelope_step
            def envelope(bus,preset,index):
                if model.stream and model.stream.running:
                    if fault=='slow': model.us+=50000
                    elif fault is not None: raise fault('injected envelope fault')
                original_env(bus,preset,index)
            with patch.object(startup,'listen',listen),patch.object(live,'Stream',lambda:ClockedStream(model,guard)),patch.object(module.EnvelopeTarget,'prepare',prepare),patch.object(module.EnvelopeBus,'envelope_step',envelope),redirect_stdout(io.StringIO()) as output:
                if fault is None: module.run()
                else:
                    with self.assertRaises(RuntimeError if fault=='slow' else fault): module.run()
            self.assertIn('SAFE:',output.getvalue())
            self.assertEqual('DONE:' in output.getvalue(),fault is None)
            self.assertTrue(model.stream.closed and model.audio.closed)
            self.assertEqual(regs.values[transport.IC_ENABLE],0)
            model.assert_stopped()

    def test_complete_HOST_across_ticks_ms_wrap(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            model.us=((1<<30)-1000)*1000; wire.next_tick=model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
        finally:
            board.close(); target.close()

    def test_import_and_direct_bus_preset_policy_are_bounded(self):
        model=MixerModel(); module,host,values=load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(values[-2].accesses,[])
        board=module.EnvelopeBus()
        try:
            board.start()
            with self.assertRaisesRegex(RuntimeError,'must be prepared'): module.EnvelopeTarget(board)
            before=len(model.writes)
            for p in (-1,2,True,1.0):
                with self.assertRaises(ValueError): board.envelope(p)
            self.assertEqual(len(model.writes),before)
        finally: board.close()


if __name__=='__main__': unittest.main()
