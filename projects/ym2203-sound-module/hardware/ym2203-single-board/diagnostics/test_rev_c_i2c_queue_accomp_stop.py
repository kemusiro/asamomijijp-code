# SPDX-License-Identifier: MIT
"""Accompanied STOP: actual four-voice cleanup,quiet,and unchanged score replay."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_queue_accomp import fixture
from test_rev_c_i2c_queue_stop import load as load_stop

HERE = Path(__file__).resolve().parent


def load(host):
    stop = load_stop(host.queue)
    spec = importlib.util.spec_from_file_location('accomp_stop', HERE/'rev_c_i2c_queue_accomp_stop_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'rev_c_i2c_queue_accomp_host':host, 'rev_c_i2c_queue_stop_host':stop}):
        spec.loader.exec_module(module)
    module.time = host.time
    return module


class AccompaniedStopTests(unittest.TestCase):
    def test_full_HOST_cleans_four_sources_quiet_then_replays_one_unchanged_upload(self):
        model, target_module, host, target, board, wire, values = fixture(); module = load(host)
        commands = []; quiet = []; original = target.apply; record = target.record_note; poll = target.poll
        def apply(command): commands.append(command); original(command)
        def note(elapsed):
            record(elapsed)
            mask = 57 if target.voice == 0 else 15
            self.assertEqual(target.applied, mask)
            self.assertEqual(model.fm_keys, [bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11], [7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            for v in range(6):
                index = target.score[target.next_note-1] if v == target.voice else target_module.pitch.INITIAL[v]
                if v < 3:
                    self.assertEqual((model.registers[0xA4+v], model.registers[0xA0+v]), target_module.control.live.PITCHES[index][1:])
                else:
                    self.assertEqual(model.registers[2*(v-3)] | model.registers[2*(v-3)+1] << 8, target_module.pitch.SSG_PERIODS[index])
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before, 1)
        def sleep(ms):
            if ms == module.stop.QUIET_MS:
                quiet.append(model.us)
                self.assertEqual((target.applied, model.level(19), model.level(26)), (0,0,0))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11], [0,0,0])
                before = len(model.writes); wire.sleep_ms(ms)
                self.assertEqual(len(model.writes), before)
            else: wire.sleep_ms(ms)
        target.apply = apply; target.record_note = note; target.poll = one_poll
        module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms, ticks_diff=model.ticks_diff, sleep_ms=sleep)
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations), (3,1,2,0))
            self.assertEqual(list(target.run_masks), [57,57,15]); self.assertEqual(list(target.run_states), [5,4,5])
            self.assertEqual(list(target.run_voices), [0,0,3]); self.assertEqual(list(target.run_notes), [3,9,3])
            self.assertEqual((target.jobs,target.writes,target.applied), (5,24,0))
            self.assertEqual(target.events, sum(target.run_notes))
            self.assertEqual(target.note_writes, target.events*2+target.partial_cancels)
            self.assertLessEqual(target.partial_cancels, 2)
            self.assertEqual(commands.count(module.queue.CLEAR), 1)
            self.assertEqual(sum(module.queue.APPEND <= c < module.queue.APPEND+5 for c in commands), 9)
            self.assertEqual(commands.count(8), 1); self.assertEqual(len(quiet), 2)
            self.assertEqual(bytes(target.score), bytes(module.queue.pitch.MELODY))
            self.assertEqual(target.times[9], 0)
            for n in range(9): self.assertTrue(n*500 <= target.times[9+n] <= n*500+100)
            self.assertGreaterEqual(target.run_end[1]-target.run_off[1], 135)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', output.getvalue())[1])
            self.assertEqual(final, len(commands)&255); self.assertIn('HOST PASS:', output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_corrupted_live_or_planned_masks_prevent_STOP_test_passing_and_lease_mutes(self):
        for address in (0x28,0x14):
            model, tm, host, target, board, wire, values = fixture(); module = load(host)
            read = wire.readfrom
            def readfrom(addr,count):
                data = read(addr,count)
                return b'\x3F' if count == 1 and target.window.pointer == address+1 else data
            # SampledLink leaves the current pointer after the requested read.
            wire.readfrom = readfrom
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'mask mismatch'):
                    module.check_live(wire)
                self.assertNotIn('HOST PASS:', output.getvalue())
                wire.sleep_ms(1600)
                self.assertEqual((target.applied,model.level(19),model.level(26)), (0,0,0))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
            finally: board.close(); target.close()

    def test_STOP_transfer_fault_not_retried_and_no_replay_then_lease_cleans_every_source(self):
        for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model, tm, host, target, board, wire, values = fixture(); module = load(host)
            write = wire.writeto; attempts = []
            def writeto(address,data,stop=True):
                if data == b'\x20\x00' and target.active():
                    attempts.append(data); raise fault('injected STOP failure')
                return write(address,data,stop)
            wire.writeto = writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): module.check_live(wire)
                self.assertEqual(attempts,[b'\x20\x00']); self.assertEqual(target.runs,1)
                self.assertNotIn('RESTART FM',output.getvalue()); self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1600)
                self.assertEqual((target.applied,target.expirations), (0,1))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                self.assertEqual((model.level(19),model.level(26)), (0,0))
            finally: board.close(); target.close()

    def test_quiet_progress_or_score_corruption_rejected_before_replay(self):
        for fault in ('progress','score'):
            model, tm, host, target, board, wire, values = fixture(); module = load(host)
            def sleep(ms):
                wire.sleep_ms(ms)
                if ms == module.stop.QUIET_MS:
                    target.window.data[0x1E if fault == 'progress' else 0x30] += 1
            module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'progress changed|changed uploaded score'):
                    module.check_live(wire)
                self.assertEqual(target.runs,1); self.assertEqual(target.applied,0)
                self.assertNotIn('RESTART FM',output.getvalue()); self.assertNotIn('HOST PASS:',output.getvalue())
            finally: board.close(); target.close()

    def test_complete_sequence_across_ticks_wrap(self):
        model, tm, host, target, board, wire, values = fixture(); module = load(host)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.completed,target.aborted,target.expirations),(1,2,0))
        finally: board.close(); target.close()

    def test_silent_import_old_wait_rejection_and_wrong_target_signature(self):
        model, tm, host, target, board, wire, values = fixture()
        try:
            accesses = list(wire.regs.accesses)
            with redirect_stdout(io.StringIO()) as output: module = load(host)
            self.assertEqual(output.getvalue(),''); self.assertEqual(wire.regs.accesses,accesses)
            with patch.object(module.mixer.Remote,'ack_wait_ms',10), patch.object(module.queue.pitch.six.staged.startup,'check') as startup:
                with self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'): module.check(wire)
                startup.assert_not_called()
            target.window.data[:8] = b'RCQUE01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'signature mismatch'): module.check_live(wire)
            self.assertEqual(wire.command_writes,0)
        finally: board.close(); target.close()


if __name__ == '__main__': unittest.main()
