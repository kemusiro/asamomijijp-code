# SPDX-License-Identifier: MIT
"""Full 180 s virtual-time I2C endurance, counter wrap and failure behavior."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_fm_scheduling import fixture


HERE = Path(__file__).resolve().parent


def load(host, wire, model):
    startup = types.SimpleNamespace(check=lambda i2c:None)
    staged = types.SimpleNamespace(mixer=host,startup=startup)
    spec = importlib.util.spec_from_file_location('i2c_endurance_host',HERE/'rev_c_i2c_endurance_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_fm_staged_host':staged}):
        spec.loader.exec_module(module)
    module.time = types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    return module,staged


class I2CEnduranceTests(unittest.TestCase):
    def test_full_three_minutes_sampled_I2C_ack_wrap_and_only_final_lease_expiry(self):
        model,control,host,target,board,wire = fixture()
        module,staged = load(host,wire,model)
        output = io.StringIO()
        try:
            with redirect_stdout(output):
                module.check_live(wire)
            wire.sleep_ms(30)  # FINISH is committed at the next idle sample
            self.assertTrue(target.window.finished)
            self.assertEqual(target.expirations,1)
            self.assertEqual(target.mode,0)
            self.assertIn('HOST PASS:',output.getvalue())
            records = re.findall(r'ENDURANCE (\d)/6 / elapsed_ms=(\d+)',output.getvalue())
            self.assertEqual([int(x[0]) for x in records],list(range(1,7)))
            self.assertTrue(all(int(row[1]) >= 30000*int(row[0]) for row in records))
            match = re.search(r'ENDURANCE COMPLETE / elapsed_ms=(\d+) KEEP=(\d+) wraps=(\d+)',output.getvalue())
            elapsed,commands,wraps = map(int,match.groups())
            self.assertGreaterEqual(elapsed,180000)
            self.assertLess(elapsed,181000)
            self.assertGreaterEqual(commands,256)
            self.assertGreaterEqual(wraps,1)
            expected = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(target.window.data[0x10],expected)
            self.assertEqual(expected,(commands+47)&255)
        finally:
            board.close()
            target.close()
        model.assert_stopped()

    def test_three_minutes_and_ACK_wrap_across_ticks_ms_wrap(self):
        model,control,host,target,board,wire = fixture()
        module,staged = load(host,wire,model)
        # A lightweight real Remote substitute exercises only the HOST timer;
        # full actual command acknowledgement is covered by the sampled test.
        model.us = ((1 << 30)-1000)*1000
        class Remote:
            ack = 250
            calls = 0
            def command(remote,command,mode):
                self.assertEqual((command,mode),(6,3))
                model.sleep_ms(40)
                remote.ack = (remote.ack+1)&255
                remote.calls += 1
        remote = Remote()
        module.time.sleep_ms = model.sleep_ms
        try:
            with redirect_stdout(io.StringIO()):
                commands,wraps,maximum = module.endure(remote)
            self.assertEqual(commands,750)
            self.assertEqual(wraps,3)
            self.assertEqual(maximum,40)
        finally:
            board.close()
            target.close()

    def test_keep_failure_is_not_retried_and_target_lease_still_mutes(self):
        for error in (OSError,RuntimeError,MemoryError):
            with self.subTest(error=error):
                model,control,host,target,board,wire = fixture()
                module,staged = load(host,wire,model)
                original = wire.writeto
                failures = []
                def write(address,data,stop=True):
                    if data == b'\x20\x06' and target.mode == 3:
                        failures.append(data)
                        raise error('injected KEEP failure')
                    return original(address,data,stop)
                wire.writeto = write
                try:
                    with redirect_stdout(io.StringIO()) as output,self.assertRaises(error):
                        module.check_live(wire)
                    self.assertNotIn('HOST PASS:',output.getvalue())
                    self.assertEqual(len(failures),1)
                    wire.sleep_ms(1200)
                    self.assertEqual(target.mode,0)
                    self.assertEqual(target.expirations,1)
                finally:
                    board.close()
                    target.close()
                model.assert_stopped()

    def test_endurance_entry_rejects_old_helper_before_startup(self):
        model,control,host,target,board,wire = fixture()
        module,staged = load(host,wire,model)
        try:
            with patch.object(host.Remote,'ack_wait_ms',10),patch.object(staged.startup,'check') as startup,self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'):
                module.check(wire)
            startup.assert_not_called()
        finally:
            board.close()
            target.close()

    def test_import_has_no_output_or_hardware_changes(self):
        model,control,host,target,board,wire = fixture()
        before = list(wire.regs.accesses)
        writes = list(model.writes)
        try:
            with redirect_stdout(io.StringIO()) as output:
                module,staged = load(host,wire,model)
            self.assertEqual(output.getvalue(),'')
            self.assertEqual(wire.regs.accesses,before)
            self.assertEqual(model.writes,writes)
        finally:
            board.close()
            target.close()


if __name__ == '__main__':
    unittest.main()
