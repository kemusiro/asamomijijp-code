# SPDX-License-Identifier: MIT
"""Three-minute six-voice KEEP/status traffic and failure behavior in model time."""
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
    spec=importlib.util.spec_from_file_location('six_endurance',HERE/'rev_c_i2c_six_endurance_host.py')
    module=importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_six_host':six}): spec.loader.exec_module(module)
    module.time=six.time
    return module


class SixEnduranceTests(unittest.TestCase):
    def test_full_180_seconds_six_voices_mask_integrity_and_ACK_wrap(self):
        model,target_module,six,target,board,wire,values=fixture()
        module=load(six)
        active_keeps=[]
        original=target.apply
        def apply(command):
            original(command)
            if command==6 and target.mode==1:
                active_keeps.append(model.us)
                self.assertEqual((target.mask,target.applied,target.job),(63,63,-1))
                self.assertEqual(model.fm_keys,[True,True,True])
                self.assertEqual(model.registers[8:11],[7,7,7])
                self.assertEqual((model.level(19),model.level(26)),(1,1))
        target.apply=apply
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30)
            text=output.getvalue()
            match=re.search(r'SIX ENDURANCE COMPLETE / elapsed_ms=(\d+) KEEP=(\d+) wraps=(\d+)',text)
            elapsed,count,wraps=map(int,match.groups())
            self.assertGreaterEqual(elapsed,180000); self.assertLess(elapsed,181000)
            self.assertGreaterEqual(count,256); self.assertGreaterEqual(wraps,1)
            self.assertEqual(len(active_keeps),count)
            self.assertEqual([int(x) for x in re.findall(r'SIX ENDURANCE (\d)/6',text)],list(range(1,7)))
            self.assertEqual((target.jobs,target.writes,target.job,target.applied),(7,24,-1,0))
            self.assertEqual(target.expirations,1)
            expected=int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',text)[1])
            self.assertEqual(expected,(count+47)&255)
            self.assertEqual(target.window.data[0x10],expected)
            self.assertTrue(target.window.finished)
            self.assertIn('HOST PASS:',text)
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_complete_run_crosses_ticks_ms_wrap(self):
        model,target_module,six,target,board,wire,values=fixture(); module=load(six)
        try:
            model.us=((1<<30)-1000)*1000; wire.next_tick=model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
        finally:
            board.close(); target.close()

    def test_KEEP_exception_is_not_retried_and_six_voices_lease_stop(self):
        for error in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,target_module,six,target,board,wire,values=fixture(); module=load(six)
            original=wire.writeto; failures=[]
            def write(address,data,stop=True):
                if data==b'\x20\x06' and target.mode==1:
                    failures.append(data); raise error('injected six-voice KEEP failure')
                return original(address,data,stop)
            wire.writeto=write
            try:
                with redirect_stdout(io.StringIO()) as output,self.assertRaises(error): module.check_live(wire)
                self.assertEqual(failures,[b'\x20\x06'])
                self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1400)
                self.assertEqual((target.mode,target.applied),(0,0))
                self.assertEqual((model.level(19),model.level(26)),(0,0))
            finally:
                board.close(); target.close()

    def test_corrupted_mask_after_KEEP_is_rejected_without_restart(self):
        model,target_module,six,target,board,wire,values=fixture(); module=load(six)
        original=wire.readfrom
        def read(address,count):
            data=original(address,count)
            if count==6 and data[1:3]==b'\x06\x01': return data[:4]+b'\x07'+data[5:]
            return data
        wire.readfrom=read
        try:
            with redirect_stdout(io.StringIO()) as output,self.assertRaisesRegex(RuntimeError,'Six-voice state mismatch'):
                module.check_live(wire)
            self.assertNotIn('HOST PASS:',output.getvalue())
            wire.sleep_ms(1400)
            self.assertEqual(target.applied,0)
        finally:
            board.close(); target.close()

    def test_old_wait_helper_rejected_before_startup_and_import_is_silent(self):
        model,target_module,six,target,board,wire,values=fixture()
        try:
            before=list(wire.regs.accesses)
            with redirect_stdout(io.StringIO()) as output: module=load(six)
            self.assertEqual(output.getvalue(),'')
            self.assertEqual(wire.regs.accesses,before)
            with patch.object(six.mixer.Remote,'ack_wait_ms',10),patch.object(six.staged.startup,'check') as startup,self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'):
                module.check(wire)
            startup.assert_not_called()
        finally:
            board.close(); target.close()


if __name__=='__main__': unittest.main()
