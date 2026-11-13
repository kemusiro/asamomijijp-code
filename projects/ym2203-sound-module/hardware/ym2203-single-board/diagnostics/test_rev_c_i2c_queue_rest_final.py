# SPDX-License-Identifier: MIT
"""Bounded final commissioning check:rest STOP,replay,and lease cleanup."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_queue_rest import fixture

HERE = Path(__file__).resolve().parent


def load(host):
    spec = importlib.util.spec_from_file_location('rest_final',HERE/'rev_c_i2c_queue_rest_final_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_queue_rest_host':host}): spec.loader.exec_module(module)
    module.time = host.time
    return module


class RestFinalTests(unittest.TestCase):
    def test_complete_HOST_rest_STOP_full_replay_no_traffic_lease_and_quiet_integrity(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        commands = []; waits = []; transfers = [0]; apply = target.apply; poll = target.poll
        read,write = wire.readfrom,wire.writeto
        def readfrom(*args,**kwargs): transfers[0] += 1; return read(*args,**kwargs)
        def writeto(*args,**kwargs): transfers[0] += 1; return write(*args,**kwargs)
        def command(c):
            if c == 0 and target.active():
                self.assertEqual((target.next_note,target.applied),(3,56))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[7,7,7])
            commands.append(c); apply(c)
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before,1)
        def sleep(ms):
            if ms in (module.QUIET_MS,module.NO_TRAFFIC_MS):
                before = transfers[0]; writes = len(model.writes); events = target.events
                wire.sleep_ms(ms); waits.append(ms); self.assertEqual(transfers[0],before)
                self.assertEqual((target.applied,target.gates(),target.state),(0,0,5))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                self.assertEqual((model.level(19),model.level(26)),(0,0))
                if ms == module.QUIET_MS:
                    self.assertEqual(len(model.writes),writes); self.assertEqual(target.events,events)
            else: wire.sleep_ms(ms)
        module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
        wire.readfrom,wire.writeto = readfrom,writeto; target.apply,target.poll = command,one_poll
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual(waits,[4000,1800,4000])
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations),(3,1,2,1))
            self.assertEqual(list(target.run_voices),[0,0,3]); self.assertEqual(list(target.run_masks),[57,57,15])
            self.assertEqual(list(target.run_states),[5,4,5]); self.assertEqual(list(target.run_notes[:2]),[3,9])
            last = target.run_notes[2]; self.assertTrue(4 <= last < 9)
            tones,rests,resumes = (sum(module.counts(n)[i] for n in target.run_notes) for i in range(3))
            self.assertEqual((target.tone_slots,target.rest_slots,target.resume_key_ons),(tones,rests,resumes))
            self.assertEqual((target.jobs,target.writes,target.applied),(6,24+2*resumes,0))
            self.assertEqual(target.events,tones+rests); self.assertTrue(2*tones <= target.note_writes <= 2*tones+4)
            self.assertLessEqual(target.partial_cancels,2)
            self.assertEqual(target.times[9],0)
            self.assertEqual(list(target.played_score[9:18]),list(host.SCORE))
            self.assertEqual(list(target.slot_masks[9:18]),[56 if n == 5 else 57 for n in host.SCORE])
            for n in range(9): self.assertTrue(n*500 <= target.times[9+n] <= n*500+100)
            self.assertEqual(commands.count(host.queue.CLEAR),1); self.assertEqual(commands.count(host.APPEND_REST),3)
            self.assertEqual(commands.count(8),1); self.assertTrue(all(c not in commands for c in (3,4,5)))
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,len(commands)&255); self.assertIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_corrupt_gate_counter_or_progress_in_first_quiet_prevents_replay(self):
        for fault in ('gate','counter','progress'):
            model,tm,host,target,board,wire,values = fixture(); module = load(host)
            corrupt = []; read = wire.readfrom
            def readfrom(address,count):
                data = read(address,count)
                return b'\x03' if fault == 'gate' and corrupt and count == 1 and target.window.pointer == 0x2A else data
            wire.readfrom = readfrom
            def sleep(ms):
                wire.sleep_ms(ms)
                if ms == module.QUIET_MS:
                    if fault == 'gate': corrupt.append(True)
                    else: target.window.data[0x2A if fault == 'counter' else 0x1E] += 1
            module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'gate readback|counts mismatch|state/pitch/lease'):
                    module.check_live(wire)
                self.assertEqual((target.runs,target.applied),(1,0))
                self.assertNotIn('FINAL 2/3 /',output.getvalue()); self.assertNotIn('HOST PASS:',output.getvalue())
            finally: board.close(); target.close()

    def test_first_STOP_or_final_lease_clear_fault_not_retried_or_followed_by_automatic_play(self):
        for stage in ('rest_STOP','lease_clear'):
            for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
                model,tm,host,target,board,wire,values = fixture(); module = load(host); write = wire.writeto; attempts = []
                def writeto(address,data,stop=True):
                    match = target.active() if stage == 'rest_STOP' else target.state == 5 and target.window.data[0x13] == 1
                    if data == b'\x20\x00' and match:
                        attempts.append(data); raise fault('injected final STOP failure')
                    return write(address,data,stop)
                wire.writeto = writeto
                try:
                    with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): module.check_live(wire)
                    self.assertEqual(attempts,[b'\x20\x00']); self.assertNotIn('HOST PASS:',output.getvalue())
                    self.assertEqual(target.runs,1 if stage == 'rest_STOP' else 3)
                    wire.sleep_ms(1600); self.assertEqual((target.applied,target.gates()),(0,0))
                    saved = target.events; wire.sleep_ms(4000); self.assertEqual(target.events,saved)
                finally: board.close(); target.close()

    def test_missed_rest_and_KEEP_transfer_failure_abort_without_retry_and_lease_stops(self):
        for fault in ('miss',OSError):
            model,tm,host,target,board,wire,values = fixture(); module = load(host)
            read,write = wire.readfrom,wire.writeto; attempts = []
            def readfrom(address,count):
                data = read(address,count)
                return b'\x02\x04' if fault == 'miss' and count == 2 and target.active() else data
            def writeto(address,data,stop=True):
                if fault is OSError and data == b'\x20\x06' and target.active():
                    attempts.append(data); raise OSError('injected KEEP failure')
                return write(address,data,stop)
            wire.readfrom,wire.writeto = readfrom,writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(RuntimeError if fault == 'miss' else OSError): module.check_live(wire)
                self.assertNotIn('HOST PASS:',output.getvalue()); self.assertEqual(len(attempts),int(fault is OSError))
                wire.sleep_ms(1600); self.assertEqual((target.applied,target.gates()),(0,0))
            finally: board.close(); target.close()

    def test_complete_sequence_crosses_ticks_wrap(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual((target.completed,target.aborted,target.expirations),(1,2,1))
        finally: board.close(); target.close()

    def test_silent_import_old_ACK_and_wrong_signature_rejected(self):
        model,tm,host,target,board,wire,values = fixture()
        try:
            accesses = list(wire.regs.accesses)
            with redirect_stdout(io.StringIO()) as output: module = load(host)
            self.assertEqual(output.getvalue(),''); self.assertEqual(wire.regs.accesses,accesses)
            with patch.object(module.mixer.Remote,'ack_wait_ms',10), patch.object(module.queue.pitch.six.staged.startup,'check') as startup:
                with self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'): module.check(wire)
                startup.assert_not_called()
            target.window.data[:8] = b'RCQMT01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'signature mismatch'): module.check_live(wire)
            self.assertEqual(wire.command_writes,0)
        finally: board.close(); target.close()


if __name__ == '__main__': unittest.main()
