# SPDX-License-Identifier: MIT
"""Repeated source/mute changes over independently sampled I2C traffic."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from test_rev_c_i2c_endurance import load as load_endurance
from test_rev_c_i2c_fm_scheduling import fixture


HERE = Path(__file__).resolve().parent


def load(host,wire,model):
    endurance,staged = load_endurance(host,wire,model)
    spec = importlib.util.spec_from_file_location('mode_cycle_host',HERE/'rev_c_i2c_cycle_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_endurance_host':endurance}):
        spec.loader.exec_module(module)
    module.time = endurance.time
    return module,endurance,staged


class CycleTests(unittest.TestCase):
    def test_all_80_sections_real_commands_state_readbacks_wrap_and_lease(self):
        model,control,host,target,board,wire = fixture()
        module,endurance,staged = load(host,wire,model)
        seen = []
        original = target.set_mode
        def mode(value):
            original(value)
            if value:
                seen.append((value,model.level(19),model.level(26),model.registers[8],model.registers[0x28]))
        target.set_mode = mode
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
            self.assertEqual(target.mode,0)
            self.assertEqual(len(re.findall(r'CYCLE \d+/10 SECTION',output.getvalue())),80)
            self.assertEqual(len(re.findall(r'CYCLE \d+/10 PASS',output.getvalue())),10)
            match = re.search(r'CYCLES COMPLETE / rounds=10 commands=(\d+) wraps=(\d+)',output.getvalue())
            commands,wraps = map(int,match.groups())
            self.assertGreaterEqual(commands,256)
            self.assertGreaterEqual(wraps,1)
            for expected in ((1,1,1,0,0x10),(2,1,0,10,0),(3,1,1,10,0x10),
                             (4,1,0,10,0x10),(5,0,1,10,0x10)):
                self.assertIn(expected,seen)
            self.assertEqual([s[0] for s in seen[:70]], [1,2,3,4,3,5,3]*10)
            final_ack = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final_ack,(commands+45)&255)
            self.assertEqual(target.window.data[0x10],final_ack)
            self.assertIn('HOST PASS:',output.getvalue())
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_expired_previous_state_is_detected_before_restarting_sources(self):
        model,control,host,target,board,wire = fixture()
        module,endurance,staged = load(host,wire,model)
        try:
            with redirect_stdout(io.StringIO()):
                remote = endurance.live_remote(wire)
            session = module.Session(wire,remote)
            session.section(3)
            wire.sleep_ms(1200)
            self.assertEqual(target.expirations,1)
            before = wire.command_writes
            with self.assertRaisesRegex(RuntimeError,'state changed unexpectedly'):
                session.section(1)
            self.assertEqual(wire.command_writes,before)
            self.assertEqual(target.mode,0)
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_section_transfer_failures_do_not_replay_or_continue(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            with self.subTest(error=error):
                model,control,host,target,board,wire = fixture()
                module,endurance,staged = load(host,wire,model)
                original = wire.writeto
                calls = []
                def write(address,data,stop=True):
                    if data == b'\x20\x04':
                        calls.append(data)
                        raise error('injected DAC MUTE error')
                    return original(address,data,stop)
                wire.writeto = write
                try:
                    with redirect_stdout(io.StringIO()) as output,self.assertRaises(error):
                        module.check_live(wire)
                    self.assertEqual(calls,[b'\x20\x04'])
                    self.assertNotIn('CYCLE 1/10 SECTION 5',output.getvalue())
                    self.assertNotIn('HOST PASS:',output.getvalue())
                    wire.sleep_ms(1200)
                    self.assertEqual(target.mode,0)
                finally:
                    board.close()
                    target.close()
                model.assert_stopped()

    def test_cycle_timer_and_ACK_wrap_with_ticks_ms_wrap(self):
        model,control,host,target,board,wire = fixture()
        module,endurance,staged = load(host,wire,model)
        try:
            model.us = ((1 << 30)-1000)*1000
            wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()):
                module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
        finally:
            board.close()
            target.close()

    def test_old_HOST_helpers_fail_before_silent_startup(self):
        model,control,host,target,board,wire = fixture()
        module,endurance,staged = load(host,wire,model)
        try:
            with patch.object(host.Remote,'ack_wait_ms',10),patch.object(staged.startup,'check') as startup,self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'):
                module.check(wire)
            startup.assert_not_called()
        finally:
            board.close()
            target.close()

    def test_import_has_no_output_or_hardware_changes(self):
        model,control,host,target,board,wire = fixture()
        accesses = list(wire.regs.accesses)
        writes = list(model.writes)
        try:
            with redirect_stdout(io.StringIO()) as output:
                module,endurance,staged = load(host,wire,model)
            self.assertEqual(output.getvalue(),'')
            self.assertEqual(wire.regs.accesses,accesses)
            self.assertEqual(model.writes,writes)
        finally:
            board.close()
            target.close()


if __name__ == '__main__':
    unittest.main()
