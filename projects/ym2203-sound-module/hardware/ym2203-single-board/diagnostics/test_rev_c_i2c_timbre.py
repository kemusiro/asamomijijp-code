# SPDX-License-Identifier: MIT
"""Fixed TL/MULTI I2C traffic; harmonic quality is checked by listening on hardware."""
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
    staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
    def source(name,modules):
        spec = importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules):
            spec.loader.exec_module(module)
        return module
    helper = source('rev_c_fm_timbre_check',{'rev_c_fm_live':live,
        'rev_c_fm_ssg_check':types.SimpleNamespace(MixerBus=control.MixerBus,hold=None,PRIME_BLOCKS=12)})
    target = source('rev_c_i2c_timbre_target',{'rev_c_i2c_fm_staged_target':staged,'rev_c_fm_timbre_check':helper})
    host = source('rev_c_i2c_timbre_host',{'rev_c_i2c_fm_staged_host':oldhost})
    target.gc = live.gc
    return target,host,values


def fixture():
    model = MixerModel()
    module,host,values = load(model)
    staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
    board = module.TimbreBus()
    board.start()
    board.prepare()
    board.ssg('single')
    board.checked(8,0)
    board.configure('serial')
    board.timbre_ready = True
    model.stream = types.SimpleNamespace(starts=2)
    target = module.TimbreTarget(board)
    target.prepare()
    target._enable(1)
    wire = SampledLink(model,target,regs,transport)
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    host.time = mixer.time = mixer.shared.time = clock
    return model,module,host,target,board,wire,values


class I2CTimbreTests(unittest.TestCase):
    def test_complete_host_changes_three_modulators_without_key_or_carrier_writes(self):
        model,module,host,target,board,wire,values = fixture()
        parameters = []
        original = target.apply
        def apply(command):
            before = len(model.writes)
            original(command)
            if command >= 0x60:
                tl = command < 0x70
                index = command-(0x60 if tl else 0x70)
                value = (module.timbre.MOD_LEVELS if tl else module.timbre.MULTIPLES)[index]
                self.assertEqual(model.writes[before:],[(base+slot,value) for slot in (0,4,8) for base in ((0x40,) if tl else (0x30,))])
                self.assertEqual(model.registers[0x4C],64)
                self.assertEqual(model.registers[0x3C],1)
                self.assertEqual(model.registers[0xB0],0)
                if target.mode:
                    self.assertEqual(model.registers[0x28],0xF0)
                    parameters.append(command)
                self.assertEqual(model.registers[8:11],[0,0,0])
        target.apply = apply
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                host.check_live(wire)
            wire.sleep_ms(30)
            self.assertEqual(parameters,[0x60,0x61,0x62,0x63,0x62,0x70,0x71,0x72])
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
            self.assertEqual(target.window.data[0x14:0x16],bytes((2,0)))
            self.assertEqual([v for r,v in model.writes if r==0x28].count(0xF0),3)
            expected=int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(target.window.data[0x10],expected)
            self.assertEqual(expected,wire.command_writes&255)
            self.assertIn('HOST PASS:',output.getvalue())
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_guards_before_start_after_expiry_and_non_FM_modes(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            before=len(model.writes)
            for command in (0x60,0x70):
                with self.assertRaisesRegex(RuntimeError,'requires START'):
                    target.apply(command)
            for command in (-1,2,3,4,5,9,0x5F,0x64,0x6F,0x73,255,True):
                with self.assertRaises(ValueError):
                    target.apply(command)
            self.assertEqual(len(model.writes),before)
            target.live_started=True
            target.apply(1)
            wire.sleep_ms(1200)
            before=len(model.writes)
            for command in (0x60,0x70):
                with self.assertRaisesRegex(RuntimeError,'non-expired'):
                    target.apply(command)
            self.assertEqual(len(model.writes),before)
            self.assertEqual(target.mode,0)
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_unprepared_timbre_rejected_and_post_setup_key_mapping_is_bounded(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            board.timbre_ready=False
            with self.assertRaisesRegex(RuntimeError,'must be prepared'):
                module.TimbreTarget(board)
            board.timbre_ready=True
            for reg,value in ((0x4C,48),(0xB0,7),(0x28,0xF0),(0x28,True),(True,0)):
                with self.assertRaises(ValueError):
                    board.write_fm(reg,value)
            board.write_fm(0x28,0x10)
            self.assertEqual(model.registers[0x28],0xF0)
        finally:
            board.close()
            target.close()

    def test_partial_register_update_failure_does_not_commit_selection_or_ACK(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            target.live_started=True
            original=board._write_tone
            def write(reg,value):
                if reg==0x44:
                    raise RuntimeError('injected partial write')
                return original(reg,value)
            before=bytes(target.window.data[0x10:0x16])
            with patch.object(board,'_write_tone',write),self.assertRaisesRegex(RuntimeError,'partial write'):
                target.apply(0x60)
            self.assertEqual(bytes(target.window.data[0x10:0x16]),before)
        finally:
            board.close()
            target.close()

    def test_host_rejects_old_pitch_signature_and_bad_selection(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            target.window.data[:8]=b'RCPIT01!'
            with self.assertRaisesRegex(RuntimeError,'signature mismatch'):
                host.check_live(wire)
            self.assertEqual(wire.command_writes,0)
            remote=host.Remote(wire)
            target.window.data[0x14]=1
            with self.assertRaisesRegex(RuntimeError,'Timbre state mismatch'):
                host.verify(wire,remote,0,0,[2,0])
        finally:
            board.close()
            target.close()

    def test_transfer_failure_is_not_replayed_and_lease_stops_sound(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values = fixture()
            original=wire.writeto
            calls=[]
            def write(address,data,stop=True):
                if data==b'\x20\x61':
                    calls.append(data)
                    raise error('injected timbre transfer fault')
                return original(address,data,stop)
            wire.writeto=write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error):
                    host.check_live(wire)
                self.assertEqual(calls,[b'\x20\x61'])
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1200)
                self.assertEqual(target.mode,0)
                self.assertEqual(target.expirations,1)
            finally:
                board.close()
                target.close()
            model.assert_stopped()

    def test_staged_setup_muted_then_cleanup_for_parameter_faults_and_deadlines(self):
        for fault in (None,'slow',MemoryError,KeyboardInterrupt):
            with self.subTest(fault=fault):
                model=MixerModel()
                module,host,values=load(model)
                staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard=values
                def listen(endpoint):
                    if endpoint.window.phase==5:
                        self.assertEqual(model.level(19),0)
                        self.assertEqual(model.level(26),0)
                        self.assertFalse(model.stream.running)
                        self.assertEqual(model.registers[0x4C],64)
                        self.assertEqual(model.registers[0xB0],0)
                    endpoint.window.finished=True
                original=module.TimbreTarget.prepare
                def prepare(endpoint):
                    original(endpoint)
                    regs.events=deque(command_events(8,5)+command_events(1,5)+command_events(0x60,5)+command_events(7,0))
                original_mod=module.TimbreBus.modulation
                def modulation(bus,value):
                    if fault=='slow': model.us+=50000
                    elif fault is not None: raise fault('injected modulation fault')
                    original_mod(bus,value)
                output=io.StringIO()
                with patch.object(startup,'listen',listen),patch.object(live,'Stream',lambda:ClockedStream(model,guard)),patch.object(module.TimbreTarget,'prepare',prepare),patch.object(module.TimbreBus,'modulation',modulation),redirect_stdout(output):
                    if fault is None: module.run()
                    else:
                        with self.assertRaises(RuntimeError if fault=='slow' else fault): module.run()
                self.assertIn('SAFE:',output.getvalue())
                self.assertEqual('DONE:' in output.getvalue(),fault is None)
                self.assertTrue(model.stream.closed and model.audio.closed)
                self.assertEqual(regs.values[transport.IC_ENABLE],0)
                model.assert_stopped()

    def test_import_does_not_touch_gpio(self):
        model=MixerModel()
        module,host,values=load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(values[-2].accesses,[])


if __name__=='__main__':
    unittest.main()
