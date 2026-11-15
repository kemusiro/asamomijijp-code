# SPDX-License-Identifier: MIT
"""Muted lease stops sources;reads cannot replay and explicit STOP/PLAY recovers."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_queue_mute import fixture
from test_rev_c_i2c_queue_stop import load as load_stop

HERE = Path(__file__).resolve().parent


def load(host):
    stop = load_stop(host.queue)
    spec = importlib.util.spec_from_file_location('queue_mute_lease',HERE/'rev_c_i2c_queue_mute_lease_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_queue_mute_host':host,'rev_c_i2c_queue_stop_host':stop}):
        spec.loader.exec_module(module)
    module.time = host.time
    return module


class MutedLeaseTests(unittest.TestCase):
    def test_full_HOST_no_traffic_cancels_two_runs_reads_stay_silent_and_explicit_replay(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        commands = []; waits = []; transfers = [0]; write = wire.writeto; read = wire.readfrom
        apply = target.apply; poll = target.poll; record = target.record_note
        def writeto(*args,**kwargs): transfers[0] += 1; return write(*args,**kwargs)
        def readfrom(*args,**kwargs): transfers[0] += 1; return read(*args,**kwargs)
        wire.writeto = writeto; wire.readfrom = readfrom
        def command(value):
            if value == 0 and target.state == 5: self.assertEqual(target.window.data[0x13],1)
            commands.append(value); apply(value)
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before,1)
        def note(elapsed):
            record(elapsed)
            mask = 15 if target.voice == 3 else 57
            self.assertEqual((target.applied,target.mask),(mask,mask))
            self.assertEqual(model.fm_keys,[bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11],[7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            self.assertEqual(target.gates(),model.level(26) | model.level(19) << 1)
            if target.runs == 2: self.assertEqual(target.gates(),3)
        def sleep(ms):
            if ms in (module.NO_TRAFFIC_MS,module.stop.QUIET_MS):
                before = transfers[0]; writes = len(model.writes); events = target.events
                wire.sleep_ms(ms); self.assertEqual(transfers[0],before)
                waits.append(ms)
                self.assertEqual((target.applied,target.gates(),target.state),(0,0,5))
                self.assertEqual((model.level(19),model.level(26)),(0,0))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                self.assertEqual(target.window.data[0x13],1)
                if ms == module.stop.QUIET_MS:
                    self.assertEqual(len(model.writes),writes); self.assertEqual(target.events,events)
                else: self.assertGreater(target.events,events)
            else: wire.sleep_ms(ms)
        module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
        target.apply = command; target.poll = one_poll; target.record_note = note
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual(waits,[1800,4000,1800,4000])
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations),(3,1,2,2))
            self.assertEqual(list(target.run_masks),[57,57,15]); self.assertEqual(list(target.run_states),[5,4,5])
            self.assertEqual(list(target.run_notes),[5,9,5])
            self.assertEqual((target.jobs,target.writes,target.applied),(7,24,0))
            self.assertEqual((target.gate_commands,target.dac_mutes,target.line_mutes,target.restores,target.gates()),(2,1,1,0,0))
            self.assertEqual(target.events,sum(target.run_notes))
            self.assertEqual(target.note_writes,2*target.events+target.partial_cancels); self.assertLessEqual(target.partial_cancels,2)
            self.assertEqual(list(target.gate_notes[9:18]),[3]*9); self.assertEqual(target.times[9],0)
            for n in range(9): self.assertTrue(500*n <= target.times[9+n] <= 500*n+100)
            self.assertEqual(commands.count(module.queue.CLEAR),1)
            self.assertEqual(sum(module.queue.APPEND <= c < module.queue.APPEND+5 for c in commands),9)
            self.assertEqual(commands.count(8),1); self.assertNotIn(3,commands)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,len(commands)&255); self.assertIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_expired_flag_gate_or_score_corruption_prevents_recovery_PLAY(self):
        for fault in ('lease','gate','score'):
            model,tm,host,target,board,wire,values = fixture(); module = load(host)
            corrupt = []; read = wire.readfrom
            def readfrom(address,count):
                data = read(address,count)
                return b'\x03' if fault == 'gate' and corrupt and count == 1 and target.window.pointer == 0x2A else data
            wire.readfrom = readfrom
            def sleep(ms):
                wire.sleep_ms(ms)
                if ms == module.stop.QUIET_MS:
                    if fault == 'gate': corrupt.append(True)
                    else: target.window.data[0x13 if fault == 'lease' else 0x30] ^= 1
            module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'state mismatch|gate readback|changed uploaded score'):
                    module.check_live(wire)
                self.assertEqual((target.runs,target.applied),(1,0))
                self.assertNotIn('RECOVERY PLAY',output.getvalue()); self.assertNotIn('HOST PASS:',output.getvalue())
            finally: board.close(); target.close()

    def test_recovery_STOP_transfer_fault_in_either_run_is_not_retried_or_followed_by_PLAY(self):
        for voice in (0,3):
            for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
                model,tm,host,target,board,wire,values = fixture(); module = load(host)
                write = wire.writeto; attempts = []
                def writeto(address,data,stop=True):
                    if data == b'\x20\x00' and target.state == 5 and target.voice == voice:
                        attempts.append(data); raise fault('injected recovery STOP failure')
                    return write(address,data,stop)
                wire.writeto = writeto
                try:
                    with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): module.check_live(wire)
                    self.assertEqual(attempts,[b'\x20\x00']); self.assertNotIn('HOST PASS:',output.getvalue())
                    self.assertEqual(target.runs,1 if voice == 0 else 3)
                    saved = target.events; wire.sleep_ms(4000)
                    self.assertEqual((target.events,target.applied,target.gates()),(saved,0,0))
                finally: board.close(); target.close()

    def test_mute_transfer_failure_uses_existing_lease_without_retry(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        write = wire.writeto; attempts = []
        def writeto(address,data,stop=True):
            if data == b'\x20\x04': attempts.append(data); raise OSError('injected mute failure')
            return write(address,data,stop)
        wire.writeto = writeto
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaises(OSError): module.check_live(wire)
            self.assertEqual(attempts,[b'\x20\x04']); self.assertNotIn('HOST PASS:',output.getvalue())
            wire.sleep_ms(1600); self.assertEqual((target.applied,target.gates()),(0,0))
        finally: board.close(); target.close()

    def test_complete_sequence_across_ticks_wrap(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual((target.completed,target.aborted,target.expirations),(1,2,2))
        finally: board.close(); target.close()

    def test_silent_import_old_ACK_wait_and_wrong_signature_rejected(self):
        model,tm,host,target,board,wire,values = fixture()
        try:
            accesses = list(wire.regs.accesses)
            with redirect_stdout(io.StringIO()) as output: module = load(host)
            self.assertEqual(output.getvalue(),''); self.assertEqual(wire.regs.accesses,accesses)
            with patch.object(module.mixer.Remote,'ack_wait_ms',10), patch.object(module.queue.pitch.six.staged.startup,'check') as startup:
                with self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'): module.check(wire)
                startup.assert_not_called()
            target.window.data[:8] = b'RCQAC01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'signature mismatch'): module.check_live(wire)
            self.assertEqual(wire.command_writes,0)
        finally: board.close(); target.close()


if __name__ == '__main__': unittest.main()
