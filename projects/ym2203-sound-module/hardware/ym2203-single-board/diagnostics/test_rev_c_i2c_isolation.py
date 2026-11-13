# SPDX-License-Identifier: MIT
"""Silent staged setup, actual host RAM checks, and cleanup on interruption."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_fm_live import LiveModel, TestStream, load as load_live
from test_rev_c_i2c_check import Registers, Link, load as load_transport


HERE = Path(__file__).resolve().parent


class ProbeRegisters(Registers):
    def __init__(self, model):
        super().__init__(model, allow_ssg=True, allow_fm=True)
        self.values.update({0x400280A4:3, 0x400280AC:3,
                            0x40038054:0x5A, 0x40038058:0x5A, 0xD0000004:3 << 20})

    def __getitem__(self, address):
        assert self.bus.level(19) == self.bus.level(26) == 0
        return super().__getitem__(address)

    def __setitem__(self, address, value):
        assert self.bus.level(19) == self.bus.level(26) == 0
        return super().__setitem__(address, value)


def load(model):
    live, machine = load_live(model)
    transport, helper, regs = load_transport(model, ProbeRegisters)
    base = model.load()
    modules = {'machine':machine, 'rev_c_bus_check':base,
               'rev_c_fm_live':live, 'rev_c_i2c_target_check':transport,
               'rev_c_i2c_host_check':helper}
    machine.I2C = object
    def import_file(name, filename):
        spec = importlib.util.spec_from_file_location(name,HERE / filename)
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        return module
    target = import_file('isolation_target', 'rev_c_i2c_isolation_target.py')
    host = import_file('isolation_host', 'rev_c_i2c_isolation_host.py')
    target.time = host.time = model
    return target, host, live, machine, transport, regs


class IsolationTests(unittest.TestCase):
    def test_actual_runner_and_host_checks_all_six_stages_without_unmuting(self):
        model = LiveModel()
        target, host, live, machine, transport, regs = load(model)
        seen = []
        output = io.StringIO()
        def listen(endpoint):
            phase = endpoint.window.phase
            self.assertEqual(regs.values[transport.IC_ENABLE],1)
            self.assertFalse(model.stream and model.stream.running)
            self.assertEqual(model.stream is not None,phase >= 2)
            self.assertEqual(model.audio is not None and not model.audio.closed,3 <= phase < 5)
            self.assertEqual(model.level(19),0)
            self.assertEqual(model.level(26),0)
            wire = Link(endpoint,regs)
            host.check_phase(wire,phase)
            # Command changes phase only after STOP / idle.
            wire.writeto(0x42,bytes((0x7F if phase == 5 else 0x7E,0xA5)))
            self.assertTrue(endpoint.window.finished if phase == 5 else endpoint.window.advance)
            seen.append(phase)
        with patch.object(live,'Stream',lambda:TestStream(model)), patch.object(target,'listen',listen), redirect_stdout(output):
            target.run()
        self.assertEqual(seen,list(range(6)))
        self.assertEqual(model.stream.sequence,56)
        self.assertEqual(model.stream.starts,1)
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertEqual(regs.values[transport.IC_ENABLE],0)
        self.assertIn('SAFE:',output.getvalue())
        self.assertIn('DONE:',output.getvalue())
        model.assert_stopped()

    def test_complete_host_advances_once_and_observes_transition_delay(self):
        model = LiveModel()
        target, host, live, machine, transport, regs = load(model)
        endpoints = []
        def next_phase(phase):
            endpoint = target.ProbeTarget(phase)
            endpoint.prepare()
            endpoint._enable(1)
            endpoints.append(endpoint)
            return endpoint
        endpoint = next_phase(0)
        sleeps = []
        def sleep(ms):
            nonlocal endpoint
            self.assertEqual(ms,3000)
            self.assertTrue(endpoint.window.advance)
            phase = endpoint.window.phase + 1
            endpoint.close()
            endpoint = next_phase(phase)
            wire.target = endpoint
            sleeps.append(ms)
        wire = Link(endpoint,regs)
        host.time = types.SimpleNamespace(sleep_ms=sleep)
        try:
            with redirect_stdout(io.StringIO()):
                host.check(wire)
            self.assertEqual(sleeps,[3000]*5)
            self.assertTrue(endpoint.window.finished)
        finally:
            endpoint.close()

    def test_interrupt_memory_and_bus_error_at_every_phase_mute_and_release(self):
        for phase in range(6):
            for error in (KeyboardInterrupt,MemoryError,OSError):
                with self.subTest(phase=phase,error=error):
                    model = LiveModel()
                    target, host, live, machine, transport, regs = load(model)
                    def listen(endpoint):
                        if endpoint.window.phase == phase:
                            raise error('injected')
                        endpoint.window.advance = True
                    output = io.StringIO()
                    with patch.object(live,'Stream',lambda:TestStream(model)), patch.object(target,'listen',listen), redirect_stdout(output), self.assertRaises(error):
                        target.run()
                    self.assertIn('SAFE:',output.getvalue())
                    self.assertNotIn('DONE:',output.getvalue())
                    self.assertEqual(regs.values[transport.IC_ENABLE],0)
                    if model.stream:
                        self.assertTrue(model.stream.closed)
                    if model.audio:
                        self.assertTrue(model.audio.closed)
                    model.assert_stopped()

    def test_preflight_error_stops_capture_before_error_logs(self):
        model = LiveModel()
        target, host, live, machine, transport, regs = load(model)
        original = live.step
        def step(*args):
            if model.registers[0x28] == 0x10:
                raise RuntimeError('injected conversion failure')
            return original(*args)
        output = io.StringIO()
        with patch.object(live,'Stream',lambda:TestStream(model)), patch.object(live,'step',step), patch.object(target,'listen',lambda endpoint:None), redirect_stdout(output), self.assertRaisesRegex(RuntimeError,'conversion failure'):
            target.run()
        self.assertFalse(model.stream.running)
        self.assertTrue(model.stream.closed and model.audio.closed)
        self.assertIn('SAFE:',output.getvalue())
        model.assert_stopped()

    def test_control_requires_correct_phase_and_exact_one_token(self):
        model = LiveModel()
        target, host, live, machine, transport, regs = load(model)
        for phase, pointer, payload in ((0,0x7F,[0xA5]),(5,0x7E,[0xA5]),
                                         (0,0x7E,[0]),(0,0x7E,[0xA5,0xA5])):
            window = target.ProbeWindow(phase)
            window.receive(0x800 | pointer)
            with self.assertRaises(ValueError):
                for byte in payload:
                    window.receive(byte)

    def test_read_only_configuration_probe_reports_mismatch_without_remuxing(self):
        model = LiveModel()
        target, host, live, machine, transport, regs = load(model)
        endpoint = target.ProbeTarget(0)
        try:
            endpoint.prepare()
            endpoint._enable(1)
            regs.values[0x400280A4] = 5
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'configuration mismatch'):
                endpoint.report_config()
            self.assertFalse(any(access[0] == 'write' and access[1] < 0x40090000 for access in regs.accesses))
        finally:
            endpoint.close()

    def test_host_failure_releases_only_host_pins_without_retry(self):
        model = LiveModel()
        target, host, live, machine, transport, regs = load(model)
        class BrokenWire:
            calls = 0
            def writeto(wire,*args):
                wire.calls += 1
                raise OSError('EIO')
        wire = BrokenWire()
        host.I2C = lambda *args,**kwargs:wire
        with redirect_stdout(io.StringIO()), self.assertRaises(OSError):
            host.run()
        self.assertEqual(wire.calls,1)
        self.assertEqual(set(model.pins),{0,1})
        self.assertTrue(all(pin.mode == model.Pin.IN for pin in model.pins.values()))

    def test_import_is_silent_and_has_no_gpio_access(self):
        model = LiveModel()
        with redirect_stdout(io.StringIO()) as output:
            target, host, live, machine, transport, regs = load(model)
        self.assertEqual(model.pins,{})
        self.assertEqual(regs.accesses,[])
        self.assertEqual(output.getvalue(),'')


if __name__ == '__main__':
    unittest.main()
