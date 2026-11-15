# SPDX-License-Identifier: MIT
"""Reuse tested stage order, keep resources, then run existing live control."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

from test_rev_c_fm_ssg_check import MixerModel
from test_rev_c_i2c_fm import ClockedStream, command_events, load as load_control
from test_rev_c_i2c_check import Link


HERE = Path(__file__).resolve().parent


def load(model):
    control,mixer_host,shared,live,machine,transport,regs,guard = load_control(model)
    machine.I2C = object
    modules = {'machine':machine, 'rev_c_fm_live':live,
               'rev_c_i2c_target_check':transport, 'rev_c_bus_check':model.load(),
               'rev_c_i2c_fm_target':control, 'rev_c_i2c_fm_host':mixer_host}
    # The existing transport helper functions are shared by both host scripts.
    import types
    modules['rev_c_i2c_host_check'] = types.SimpleNamespace(
        checked_write=mixer_host.checked_write, read_at=mixer_host.read_at)
    def import_file(name):
        spec = importlib.util.spec_from_file_location(name,HERE / (name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules):
            spec.loader.exec_module(module)
        modules[name] = module
        return module
    startup = import_file('rev_c_i2c_isolation_target')
    startup_host = import_file('rev_c_i2c_isolation_host')
    target = import_file('rev_c_i2c_fm_staged_target')
    host = import_file('rev_c_i2c_fm_staged_host')
    startup.time = startup_host.time = host.time = model
    target.gc = startup.gc = live.gc
    return target,host,startup,startup_host,control,mixer_host,live,machine,transport,regs,guard


class StagedFMTests(unittest.TestCase):
    def test_six_startup_phases_keep_resources_then_all_live_modes_and_lease(self):
        model = MixerModel()
        target,host,startup,startup_host,control,mixer_host,live,machine,transport,regs,guard = load(model)
        phases = []
        ssg_calls = []
        original_ssg = control.MixerBus.ssg
        def ssg(board,mode):
            ssg_calls.append(mode)
            original_ssg(board,mode)
        def listen(endpoint):
            phase = endpoint.window.phase
            phases.append(phase)
            self.assertEqual(model.level(19),0)
            self.assertEqual(model.level(26),0)
            self.assertFalse(model.stream and model.stream.running)
            if phase == 5:
                self.assertEqual(model.level(22),1)
                self.assertFalse(model.audio.closed)
                self.assertEqual(model.registers[7],0x3E)
                self.assertEqual(model.registers[8:11],[0,0,0])
            wire = Link(endpoint,regs)
            startup_host.check_phase(wire,phase)
            wire.writeto(0x42,bytes((0x7F if phase == 5 else 0x7E,0xA5)))
        original_prepare = control.ControlTarget.prepare
        def prepare(endpoint):
            self.assertEqual(phases,list(range(6)))
            original_prepare(endpoint)
            events = command_events(8,5)
            for command in (1,0,2,0,3,4,3,5,3,0):
                events += command_events(command)
            events += command_events(3,110) + command_events(7,0)
            regs.events = deque(events)
        def collect():
            self.assertFalse(model.stream and model.stream.running)
            self.assertEqual(model.level(19),0)
        output = io.StringIO()
        with patch.object(live,'Stream',lambda:ClockedStream(model,guard)), patch.object(startup,'listen',listen), patch.object(control.ControlTarget,'prepare',prepare), patch.object(control.MixerBus,'ssg',ssg), patch.object(live.gc,'collect',collect), redirect_stdout(output):
            target.run()
        self.assertEqual(ssg_calls,['single'])
        self.assertEqual(model.stream.starts,2)
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertEqual(model.stream.deadline_misses,0)
        self.assertIn('lease_expirations=1',output.getvalue())
        self.assertIn('staged I2C + live FM mixer target v1.3',output.getvalue())
        self.assertNotIn('LINE/DAC remain muted throughout',output.getvalue())
        self.assertIn('SAFE:',output.getvalue())
        self.assertIn('DONE:',output.getvalue())
        states = set(model.mix_transfers)
        for state in ((True,1,1,(0,0,0),0x3E), (False,1,0,(10,0,0),0x3E),
                      (True,1,1,(10,0,0),0x3E), (True,1,0,(10,0,0),0x3E),
                      (True,0,1,(10,0,0),0x3E)):
            self.assertIn(state,states)
        self.assertEqual(regs.values[transport.IC_ENABLE],0)
        model.assert_stopped()

    def test_control_failure_after_startup_mutes_and_closes_shared_resources(self):
        for error in (KeyboardInterrupt,MemoryError):
            with self.subTest(error=error):
                model = MixerModel()
                target,host,startup,startup_host,control,mixer_host,live,machine,transport,regs,guard = load(model)
                original_prepare = control.ControlTarget.prepare
                def prepare(endpoint):
                    original_prepare(endpoint)
                    regs.events = deque(command_events(8,5)+command_events(3,5)+[error('injected')])
                def collect():
                    self.assertFalse(model.stream and model.stream.running)
                    self.assertEqual(model.level(19),0)
                output = io.StringIO()
                with patch.object(live,'Stream',lambda:ClockedStream(model,guard)), patch.object(startup,'listen',lambda endpoint:None), patch.object(control.ControlTarget,'prepare',prepare), patch.object(live.gc,'collect',collect), redirect_stdout(output), self.assertRaises(error):
                    target.run()
                self.assertTrue(model.stream.closed and model.audio.closed)
                self.assertEqual(regs.values[transport.IC_ENABLE],0)
                self.assertIn('SAFE:',output.getvalue())
                self.assertNotIn('DONE:',output.getvalue())
                model.assert_stopped()

    def test_host_starts_live_checks_only_after_all_silent_checks_complete(self):
        model = MixerModel()
        target,host,startup,startup_host,control,mixer_host,live,machine,transport,regs,guard = load(model)
        observed = []
        wire = object()
        def silent(i2c):
            self.assertIs(i2c,wire)
            observed.append('silent-complete')
        def audio(i2c):
            self.assertIs(i2c,wire)
            self.assertEqual(model.us,3000000)
            observed.append('live-check')
        with patch.object(startup_host,'check',silent), patch.object(mixer_host,'check',audio), redirect_stdout(io.StringIO()):
            host.check(wire)
        self.assertEqual(observed,['silent-complete','live-check'])
        with patch.object(startup_host,'check',side_effect=OSError('EIO')), patch.object(mixer_host,'check') as live_check, redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            host.check(wire)
        live_check.assert_not_called()
        with patch.object(mixer_host.Remote,'ack_wait_ms',10), patch.object(startup_host,'check') as silent_check, self.assertRaisesRegex(RuntimeError,'updated rev_c_i2c_fm_host'):
            host.check(wire)
        silent_check.assert_not_called()

    def test_import_does_not_touch_GPIO_or_peripherals(self):
        model = MixerModel()
        with redirect_stdout(io.StringIO()):
            loaded = load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(loaded[-2].accesses,[])


if __name__ == '__main__':
    unittest.main()
