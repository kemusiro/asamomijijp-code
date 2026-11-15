# SPDX-License-Identifier: MIT
"""Bounded combined pitch/timbre commands; native harmonic audio is not modeled."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from test_rev_c_fm_ssg_check import MixerModel
from test_rev_c_i2c_fm import ClockedStream, command_events
from test_rev_c_i2c_timbre import fixture as timbre_fixture, load as load_timbre

HERE = Path(__file__).resolve().parent


def extend(target,host):
    def source(name,modules):
        spec=importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module=importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules): spec.loader.exec_module(module)
        return module
    combined=source('rev_c_i2c_combined_target',{'rev_c_i2c_timbre_target':target})
    remote=source('rev_c_i2c_combined_host',{'rev_c_i2c_timbre_host':host})
    combined.gc=target.gc
    remote.time=host.time
    return combined,remote


def fixture():
    model,timbre,timbre_host,old,board,wire,values=timbre_fixture()
    module,host=extend(timbre,timbre_host)
    target=module.CombinedTarget(board)
    target.prepare()
    target._enable(1)
    wire.target=target
    return model,module,host,target,board,wire,values


class CombinedTests(unittest.TestCase):
    def test_four_separate_scales_with_exact_register_values_and_presets(self):
        model,module,host,target,board,wire,values=fixture()
        events=[]
        original=target.apply
        def apply(command):
            before=len(model.writes)
            original(command)
            if command>=0x40:
                if command<0x60:
                    note=command-0x40
                    name,hi,lo=module.control.live.PITCHES[note]
                    expected=[(0xA4,hi),(0xA0,lo)]
                else:
                    tl=command<0x70
                    index=command-(0x60 if tl else 0x70)
                    value=(module.timbre.timbre.MOD_LEVELS if tl else module.timbre.timbre.MULTIPLES)[index]
                    expected=[((0x40 if tl else 0x30)+slot,value) for slot in (0,4,8)]
                self.assertEqual(model.writes[before:],expected)
                self.assertEqual(model.registers[0x4C],64)
                self.assertEqual(model.registers[0x3C],1)
                self.assertEqual(model.registers[0xB0],0)
                self.assertEqual(model.registers[8:11],[0,0,0])
                if target.mode:
                    self.assertEqual(model.registers[0x28],0xF0)
                    events.append(command)
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()) as output:
                host.check_live(wire)
            wire.sleep_ms(30)
            expected=[]
            for tl,multi in host.PRESETS:
                # Each initial C/timbre is prepared with the gate closed.
                expected += [0x40+n for n in host.MELODY[1:]]
            self.assertEqual(events,expected)
            self.assertEqual([v for r,v in model.writes if r==0x28].count(0xF0),5)
            self.assertEqual(target.window.data[0x14:0x17],bytes((2,2,0)))
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
            final=int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(target.window.data[0x10],final)
            self.assertEqual(final,wire.command_writes&255)
            self.assertEqual(len(re.findall(r'SCALE \d/4 NOTE \d/9',output.getvalue())),36)
            self.assertIn('HOST PASS:',output.getvalue())
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_pitch_before_start_after_expiry_and_invalid_commands_are_rejected(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            before=len(model.writes)
            with self.assertRaisesRegex(RuntimeError,'requires START'): target.apply(0x40)
            for value in (-1,2,3,4,5,9,0x3F,0x45,0x50,0x64,0x73,255,True):
                with self.assertRaises(ValueError): target.apply(value)
            self.assertEqual(len(model.writes),before)
            target.live_started=True
            target.apply(1)
            wire.sleep_ms(1200)
            before=len(model.writes)
            for value in (0x40,0x60,0x70):
                with self.assertRaisesRegex(RuntimeError,'non-expired'): target.apply(value)
            self.assertEqual(len(model.writes),before)
            self.assertEqual(target.mode,0)
        finally:
            board.close(); target.close()

    def test_partial_pitch_write_does_not_commit_ACK_or_selection(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.live_started=True
            before=bytes(target.window.data[0x10:0x17])
            original=board._write_port
            def write(port,value):
                if port==0 and value==0xA0: raise RuntimeError('injected low pitch byte fault')
                original(port,value)
            with patch.object(board,'_write_port',write),self.assertRaisesRegex(RuntimeError,'pitch byte fault'):
                target.apply(0x40)
            self.assertEqual(bytes(target.window.data[0x10:0x17]),before)
        finally:
            board.close(); target.close()

    def test_old_signature_rejected_before_any_sound_command(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            target.window.data[:8]=b'RCTIM01!'
            with self.assertRaisesRegex(RuntimeError,'signature mismatch'): host.check_live(wire)
            self.assertEqual(wire.command_writes,0)
            self.assertFalse(target.live_started)
        finally:
            board.close(); target.close()

    def test_corrupted_pitch_readback_stops_before_next_note_command(self):
        model,module,host,target,board,wire,values=fixture()
        original=wire.readfrom
        def read(address,count):
            data=original(address,count)
            if count==7 and data[2]==1 and data[1]==6 and data[6]==0:
                return data[:6]+b'\x04'
            return data
        wire.readfrom=read
        try:
            with redirect_stdout(io.StringIO()) as output,self.assertRaisesRegex(RuntimeError,'Combined state mismatch'):
                host.check_live(wire)
            self.assertNotIn('NOTE 2/9',output.getvalue())
            self.assertNotIn('HOST PASS:',output.getvalue())
            wire.sleep_ms(1200)
            self.assertEqual(target.mode,0)
        finally:
            board.close(); target.close()

    def test_note_transfer_exceptions_do_not_retry_or_continue(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values=fixture()
            original=wire.writeto
            calls=[]
            def write(address,data,stop=True):
                if data==b'\x20\x41':
                    calls.append(data)
                    raise error('injected combined note failure')
                return original(address,data,stop)
            wire.writeto=write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error): host.check_live(wire)
                self.assertEqual(calls,[b'\x20\x41'])
                self.assertNotIn('NOTE 3/9',output.getvalue())
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1200)
                self.assertEqual(target.mode,0)
            finally:
                board.close(); target.close()

    def test_staged_pitch_faults_mute_and_stop_native_stream(self):
        for fault in (None,'slow',MemoryError,KeyboardInterrupt):
            model=MixerModel()
            timbre,timbre_host,values=load_timbre(model)
            module,host=extend(timbre,timbre_host)
            staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
            def listen(endpoint): endpoint.window.finished=True
            original=module.CombinedTarget.prepare
            def prepare(endpoint):
                original(endpoint)
                regs.events=deque(command_events(8,5)+command_events(1,5)+command_events(0x40,5)+command_events(0x61,5)+command_events(7,0))
            original_pitch=timbre.TimbreBus.pitch
            def pitch(bus,note):
                if fault=='slow': model.us+=50000
                elif fault is not None: raise fault('injected combined fault')
                original_pitch(bus,note)
            with patch.object(startup,'listen',listen),patch.object(live,'Stream',lambda:ClockedStream(model,guard)),patch.object(module.CombinedTarget,'prepare',prepare),patch.object(timbre.TimbreBus,'pitch',pitch),redirect_stdout(io.StringIO()) as output:
                if fault is None: module.run()
                else:
                    with self.assertRaises(RuntimeError if fault=='slow' else fault): module.run()
            self.assertIn('SAFE:',output.getvalue())
            self.assertEqual('DONE:' in output.getvalue(),fault is None)
            self.assertTrue(model.stream.closed and model.audio.closed)
            self.assertEqual(regs.values[transport.IC_ENABLE],0)
            model.assert_stopped()

    def test_ticks_ms_wrap_across_combined_sequence(self):
        model,module,host,target,board,wire,values=fixture()
        try:
            model.us=((1<<30)-1000)*1000
            wire.next_tick=model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
        finally:
            board.close(); target.close()

    def test_import_and_invalid_HOST_selection_are_silent(self):
        model=MixerModel()
        timbre,timbre_host,values=load_timbre(model)
        module,host=extend(timbre,timbre_host)
        self.assertEqual(model.pins,{})
        self.assertEqual(values[-2].accesses,[])
        for value in (0,0x45,0x50,0x64,0x73,True):
            with self.assertRaises(ValueError): host.select(None,None,value,0,[2,0,255])


if __name__=='__main__': unittest.main()
