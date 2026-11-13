# SPDX-License-Identifier: MIT
"""Repeated six-voice source/mute jobs over independently sampled I2C."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from test_rev_c_i2c_six import fixture

HERE=Path(__file__).resolve().parent


def load(six):
    spec=importlib.util.spec_from_file_location('six_cycle',HERE/'rev_c_i2c_six_cycle_host.py')
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_six_host':six}): spec.loader.exec_module(module)
    module.time=six.time
    return module


class SixCycleTests(unittest.TestCase):
    def test_all80_sections_mask_keys_levels_gates_jobs_and_ACK_wrap(self):
        model,target_module,six,target,board,wire,values=fixture(); module=load(six)
        states=[]
        original_commit=target._commit; original_apply=target.apply
        def record():
            mask=target.mask
            self.assertEqual(model.fm_keys,[bool(mask&(1<<i)) for i in range(3)])
            self.assertEqual(model.registers[8:11],[7 if mask&(1<<(i+3)) else 0 for i in range(3)])
            self.assertEqual(model.level(19),int(bool(mask) and target.mode!=5))
            self.assertEqual(model.level(26),int(bool(mask&7) and target.mode!=4))
            states.append((target.mode,mask))
        def commit(): original_commit(); record()
        def apply(command):
            original_apply(command)
            if command in (3,4,5): record()
        target._commit=commit; target.apply=apply
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30)
            text=output.getvalue()
            self.assertEqual(states[1:81],[(mode,mask) for _ in range(10) for c,mode,mask,label in module.SECTIONS])
            self.assertEqual((target.jobs,target.writes,target.job,target.applied),(45,192,-1,0))
            self.assertEqual(target.expirations,1)
            self.assertEqual(len(re.findall(r'SIX CYCLE \d+/10 SECTION',text)),80)
            self.assertEqual(len(re.findall(r'SIX CYCLE \d+/10 PASS',text)),10)
            count,wraps=map(int,re.search(r'SIX CYCLES COMPLETE / rounds=10 commands=(\d+) wraps=(\d+)',text).groups())
            self.assertGreaterEqual(count,256); self.assertGreaterEqual(wraps,1)
            final=int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',text)[1])
            self.assertEqual(final,(count+45)&255)
            self.assertEqual(target.window.data[0x10],final)
            self.assertTrue(target.window.finished)
            elapsed=int(re.search(r'SIX CYCLE 10/10 PASS / elapsed_ms=(\d+)',text)[1])
            self.assertLess(elapsed,260000) # leave room for preflight within the unchanged five-minute limit
            self.assertIn('HOST PASS:',text)
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_expired_prior_state_is_caught_before_new_STOP_or_mask(self):
        model,target_module,six,target,board,wire,values=fixture(); module=load(six)
        try:
            with redirect_stdout(io.StringIO()):
                remote=six.mixer.shared.preflight(wire,signature=six.SIGNATURE,remote_factory=six.Remote)
            remote.command(8,0)
            session=module.Session(wire,remote)
            session.last=8
            session.section(127,1,63)
            wire.sleep_ms(1400)
            before=wire.command_writes
            with self.assertRaisesRegex(RuntimeError,'Six-voice state mismatch'): session.section(0,0,0)
            self.assertEqual(wire.command_writes,before)
            self.assertEqual(target.applied,0)
        finally:
            board.close(); target.close()

    def test_transfer_exceptions_do_not_retry_or_advance_to_restore(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,target_module,six,target,board,wire,values=fixture(); module=load(six)
            original=wire.writeto; failures=[]
            def write(address,data,stop=True):
                if data==b'\x20\x04':
                    failures.append(data); raise error('injected six-cycle DAC mute failure')
                return original(address,data,stop)
            wire.writeto=write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error): module.check_live(wire)
                self.assertEqual(failures,[b'\x20\x04'])
                self.assertNotIn('SECTION 5/8',output.getvalue())
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1400)
                self.assertEqual((target.mode,target.applied),(0,0))
            finally:
                board.close(); target.close()

    def test_full_cycle_run_across_ticks_ms_wrap(self):
        model,target_module,six,target,board,wire,values=fixture(); module=load(six)
        try:
            model.us=((1<<30)-1000)*1000; wire.next_tick=model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.jobs,target.writes),(45,192))
        finally:
            board.close(); target.close()

    def test_old_wait_helper_rejected_before_startup(self):
        model,target_module,six,target,board,wire,values=fixture(); module=load(six)
        try:
            with patch.object(six.mixer.Remote,'ack_wait_ms',10),patch.object(six.staged.startup,'check') as startup,self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'):
                module.check(wire)
            startup.assert_not_called()
        finally:
            board.close(); target.close()

    def test_import_is_silent_and_does_not_touch_hardware(self):
        model,target_module,six,target,board,wire,values=fixture()
        try:
            before=list(wire.regs.accesses); writes=list(model.writes)
            with redirect_stdout(io.StringIO()) as output: load(six)
            self.assertEqual(output.getvalue(),'')
            self.assertEqual(wire.regs.accesses,before)
            self.assertEqual(model.writes,writes)
        finally:
            board.close(); target.close()


if __name__=='__main__': unittest.main()
