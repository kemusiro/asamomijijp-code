# SPDX-License-Identifier: MIT
"""Six-voice mask jobs, audio-budget interleaving and actual YM bus operations."""
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

from test_rev_c_i2c_fm import ClockedStream, command_events
from test_rev_c_i2c_fm_staged import load as load_staged
from test_rev_c_i2c_fm_scheduling import SampledLink
from test_rev_c_six_voice_check import PolyModel, PolyStream

HERE=Path(__file__).resolve().parent


def load(model):
    values=load_staged(model)
    staged,staged_host,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
    def source(name,modules):
        spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules): spec.loader.exec_module(module)
        return module
    poly=source('rev_c_six_voice_check',{'rev_c_fm_live':live,'rev_c_fm_ssg_check':types.SimpleNamespace(MixerBus=control.MixerBus,hold=None,PRIME_BLOCKS=12)})
    target=source('rev_c_i2c_six_target',{'rev_c_i2c_fm_staged_target':staged,'rev_c_six_voice_check':poly})
    host=source('rev_c_i2c_six_host',{'rev_c_i2c_fm_staged_host':staged_host})
    target.gc=live.gc
    return target,host,values


def fixture():
    model=PolyModel(); module,host,values=load(model)
    staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
    board=module.SixBus(); board.start(); board.prepare(); board.configure_three(); board.bass()
    for reg in (8,9,10): board.checked(reg,0)
    model.stream=types.SimpleNamespace(starts=2)
    target=module.SixTarget(board); target.prepare(); target._enable(1)
    wire=SampledLink(model,target,regs,transport)
    host.time=mixer.time=mixer.shared.time=types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    return model,module,host,target,board,wire,values


class ClockedPolyStream(ClockedStream):
    def __init__(self,model,guard):
        super().__init__(model,guard)
        self.phases=[0.0]*3
        self.missing=None; self.loud=False
    def take(self):
        due=self.initial_us+(self.sequence+1)*11250
        self.model.us=max(self.model.us,due)-11250
        return PolyStream.take(self)


class SixI2CTests(unittest.TestCase):
    def test_full_HOST_solos_chords_mutes_and_final_split_cleanup(self):
        model,module,host,target,board,wire,values=fixture()
        states=[]; writes=[]; last_write=[None]
        original_voice=board.voice; original_commit=target._commit; original_apply=target.apply
        def voice(index,enabled):
            before=len(model.writes)
            self.assertEqual((model.level(19),model.level(26)),(0,0))
            original_voice(index,enabled)
            self.assertEqual(model.writes[before:],[(0x28,index|(0x10 if enabled else 0))] if index<3 else [(8+index-3,7 if enabled else 0)])
            writes.append((index,enabled)); last_write[0]=model.us
        def record():
            states.append((target.mask,target.mode,tuple(model.fm_keys),tuple(model.registers[8:11]),model.level(19),model.level(26)))
        def commit():
            if target.desired:
                self.assertGreaterEqual(model.us-last_write[0],12*11250)
            original_commit(); record()
        def apply(command):
            original_apply(command)
            if command in (3,4,5): record()
        board.voice=voice; target._commit=commit; target.apply=apply
        try:
            with redirect_stdout(io.StringIO()) as output: host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.jobs,target.writes),(15,38))
            self.assertEqual((target.job,target.applied,target.prime_left),(-1,0,0))
            self.assertEqual(target.expirations,1)
            masks=[s[0] for s in states if s[0] and s[1]==1]
            self.assertEqual(masks[:9],[1,2,4,7,8,16,32,56,63])
            for mask,mode,keys,levels,line,dac in states:
                self.assertEqual(keys,tuple(bool(mask&(1<<i)) for i in range(3)))
                self.assertEqual(levels,tuple(7 if mask&(1<<(i+3)) else 0 for i in range(3)))
                self.assertEqual(line,int(bool(mask) and mode!=5))
                self.assertEqual(dac,int(bool(mask&7) and mode!=4))
            self.assertIn((63,4,(True,True,True),(7,7,7),1,0),states)
            self.assertIn((63,5,(True,True,True),(7,7,7),0,1),states)
            final=int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(target.window.data[0x10],final)
            self.assertEqual(final,wire.command_writes&255) # expiry has neither a wire command nor an ACK
            self.assertIn('HOST PASS:',output.getvalue())
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_job_writes_one_register_per_poll_then_primes_before_ACK(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            target.apply(0x7F)
            for index in range(6):
                before=len(model.writes)
                target.poll()
                self.assertEqual(len(model.writes)-before,1)
                self.assertEqual(target.window.data[0x10],0)
                self.assertEqual((model.level(19),model.level(26)),(0,0))
            for unused in range(11):
                target.poll()
                self.assertEqual(target.window.data[0x10],0)
            target.poll()
            self.assertEqual(bytes(target.window.data[0x10:0x16]),bytes((1,127,1,0,63,0)))
        finally:
            board.close(); target.close()

    def test_expiry_closes_gates_immediately_before_all_six_registers_finish(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True; target.apply(127); wire.sleep_ms(250)
            self.assertEqual(target.mask,63)
            model.us+=1000000
            target.poll()
            self.assertEqual((target.mode,target.mask,model.level(19),model.level(26)),(0,0,0,0))
            self.assertEqual(target.window.data[0x13:0x16],bytes((1,0,1)))
            self.assertNotEqual(target.applied,0)
            wire.next_tick=model.us+11250
            wire.sleep_ms(150)
            self.assertEqual((target.job,target.applied),(-1,0))
            before=len(model.writes)
            target.apply(6)
            with self.assertRaisesRegex(RuntimeError,'non-expired'): target.apply(127)
            self.assertEqual(len(model.writes),before)
        finally:
            board.close(); target.close()

    def test_invalid_commands_prestart_pending_and_direct_voice_values_rejected(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            before=len(model.writes)
            for command in (-1,1,2,9,0x3F,0x80,255,True):
                with self.assertRaises(ValueError): target.apply(command)
            with self.assertRaisesRegex(RuntimeError,'requires START'): target.apply(65)
            with self.assertRaisesRegex(RuntimeError,'active unexpired'): target.apply(4)
            target.live_started=True; target.apply(65)
            for command in (6,0,7,66):
                with self.assertRaisesRegex(RuntimeError,'pending'): target.apply(command)
            for index,enabled in ((-1,0),(6,1),(True,1),(0,True),(0,2)):
                with self.assertRaises(ValueError): board.voice(index,enabled)
            self.assertEqual(len(model.writes),before)
        finally:
            board.close(); target.close()

    def test_partial_voice_failure_leaves_ACK_uncommitted_and_output_closed(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True; target.apply(127)
            original=board.voice
            def voice(index,enabled):
                if index==3: raise RuntimeError('injected SSG failure')
                original(index,enabled)
            with patch.object(board,'voice',voice),self.assertRaisesRegex(RuntimeError,'SSG failure'):
                for unused in range(6): target.poll()
            self.assertEqual(target.window.data[0x10],0)
            self.assertEqual(target.window.data[0x15],1)
            self.assertEqual((model.level(19),model.level(26)),(0,0))
        finally:
            board.close(); target.close()

    def test_old_signature_and_corrupted_voice_state_stop_HOST_before_next_section(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.window.data[:8]=b'RCENV02!'
            with self.assertRaisesRegex(RuntimeError,'signature mismatch'): host.check_live(wire)
            self.assertEqual(wire.command_writes,0)
            remote=host.Remote(wire)
            target.window.data[0x14]=1
            with self.assertRaisesRegex(RuntimeError,'Six-voice state mismatch'): host.verify(wire,remote,0,0,0)
        finally:
            board.close(); target.close()

    def test_transfer_faults_are_not_retried_and_all_voices_lease_mute(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values=fixture()
            original=wire.writeto; calls=[]
            def write(address,data,stop=True):
                if data==b'\x20\x44':
                    calls.append(data); raise error('injected FM3 transfer failure')
                return original(address,data,stop)
            wire.writeto=write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error): host.check_live(wire)
                self.assertEqual(calls,[b'\x20\x44'])
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1300)
                self.assertEqual((target.mode,target.applied),(0,0))
            finally:
                board.close(); target.close()

    def test_native_audio_budget_split_jobs_and_cleanup_with_six_voice_waveform(self):
        for fault in (None,'slow',MemoryError,KeyboardInterrupt):
            model=PolyModel(); module,host,values=load(model)
            staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
            def listen(endpoint):
                if endpoint.window.phase==5:
                    self.assertFalse(model.stream.running)
                    self.assertEqual((model.level(19),model.level(26)),(0,0))
                    self.assertEqual(model.registers[8:11],[0,0,0])
                endpoint.window.finished=True
            original_prepare=module.SixTarget.prepare
            def prepare(endpoint):
                original_prepare(endpoint)
                commands=((8,40),(127,40),(4,40),(3,40),(5,40),(3,40),(0,40),(127,130),(7,0))
                regs.events=deque(e for c,w in commands for e in command_events(c,w))
            original_voice=module.SixBus.voice
            def voice(bus,index,enabled):
                model.us+=50000 if fault=='slow' else 2300
                if fault in (MemoryError,KeyboardInterrupt): raise fault('injected voice failure')
                original_voice(bus,index,enabled)
            with patch.object(startup,'listen',listen),patch.object(live,'Stream',lambda:ClockedPolyStream(model,guard)),patch.object(module.SixTarget,'prepare',prepare),patch.object(module.SixBus,'voice',voice),redirect_stdout(io.StringIO()) as output:
                if fault is None: module.run()
                else:
                    with self.assertRaises(RuntimeError if fault=='slow' else fault): module.run()
            self.assertIn('SAFE:',output.getvalue())
            self.assertEqual('DONE:' in output.getvalue(),fault is None)
            self.assertTrue(model.stream.closed and model.audio.closed)
            model.assert_stopped()

    def test_import_is_silent_and_complete_HOST_crosses_ticks_wrap(self):
        model=PolyModel(); module,host,values=load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(values[-2].accesses,[])
        model,module,host,target,board,wire,values=fixture()
        try:
            model.us=((1<<30)-1000)*1000; wire.next_tick=model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
        finally:
            board.close(); target.close()


if __name__=='__main__': unittest.main()
