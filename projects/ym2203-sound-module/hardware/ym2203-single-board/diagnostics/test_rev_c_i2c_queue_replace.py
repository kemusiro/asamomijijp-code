# SPDX-License-Identifier: MIT
"""Score replacement and cross-family reuse without stale notes or extra START."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import unittest
from unittest.mock import patch

from test_rev_c_i2c_queue_mute import fixture

HERE = Path(__file__).resolve().parent


def load(host):
    spec = importlib.util.spec_from_file_location('queue_replace',HERE/'rev_c_i2c_queue_replace_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules,{'rev_c_i2c_queue_mute_host':host}): spec.loader.exec_module(module)
    module.time = host.time
    return module


class ScoreReplacementTests(unittest.TestCase):
    def test_full_HOST_original_then_replacement_on_FM_and_reused_on_SSG_actual_registers(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        commands = []; played = []; apply = target.apply; record = target.record_note; poll = target.poll
        def command(value):
            if value == module.queue.CLEAR:
                self.assertEqual((target.applied,target.gates(),target.mode),(0,0,0))
            commands.append(value); apply(value)
        def note(elapsed):
            record(elapsed)
            score = module.SCALE if target.runs == 1 else module.ALTERNATE
            played.append((target.runs,target.voice,target.score[target.next_note-1]))
            self.assertEqual(bytes(target.score),bytes(score))
            mask = 15 if target.voice == 3 else 57
            self.assertEqual((target.mask,target.applied),(mask,mask))
            self.assertEqual((target.gates(),model.level(26),model.level(19)),(3,1,1))
            self.assertEqual(model.fm_keys,[bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11],[7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            for v in range(6):
                index = score[target.next_note-1] if v == target.voice else tm.pitch.INITIAL[v]
                if v < 3: self.assertEqual((model.registers[0xA4+v],model.registers[0xA0+v]),tm.control.live.PITCHES[index][1:])
                else: self.assertEqual(model.registers[2*(v-3)] | model.registers[2*(v-3)+1] << 8,tm.pitch.SSG_PERIODS[index])
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before,1)
        target.apply = command; target.record_note = note; target.poll = one_poll
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations),(3,3,0,0))
            self.assertEqual((target.jobs,target.writes,target.applied),(5,24,0))
            self.assertEqual((target.events,target.note_writes,target.partial_cancels),(27,54,0))
            self.assertEqual(list(target.run_masks),[57,57,15]); self.assertEqual(list(target.run_states),[4,4,4])
            self.assertEqual(list(target.run_notes),[9,9,9]); self.assertEqual(list(target.gate_notes),[3]*27)
            expected = [(1,0,n) for n in module.SCALE]+[(2,0,n) for n in module.ALTERNATE]+[(3,3,n) for n in module.ALTERNATE]
            self.assertEqual(played,expected)
            self.assertEqual(bytes(target.score),bytes(module.ALTERNATE))
            for run in range(3):
                self.assertEqual(target.times[run*9],0)
                for n in range(9): self.assertTrue(500*n <= target.times[run*9+n] <= 500*n+100)
            self.assertEqual(commands.count(module.queue.CLEAR),2)
            self.assertEqual(sum(module.queue.APPEND <= c < module.queue.APPEND+5 for c in commands),18)
            self.assertEqual(commands.count(8),1); self.assertTrue(all(c not in commands for c in (3,4,5)))
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,len(commands)&255); self.assertIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_invalid_diagnostic_scores_rejected_before_any_transfer(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        try:
            accesses = list(wire.regs.accesses)
            for score in ((),(0,)*8,(0,)*10,(0,)*8+(1,),(0,5,0,0,0,0,0,0,0),(0,True,0,0,0,0,0,0,0),(0,1.5,0,0,0,0,0,0,0)):
                with self.assertRaisesRegex(ValueError,'nine indices'): module.upload_score(wire,object(),score)
            self.assertEqual(wire.regs.accesses,accesses); self.assertEqual(wire.command_writes,0)
        finally: board.close(); target.close()

    def test_stale_original_readback_after_second_upload_prevents_new_PLAY(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host); read = wire.readfrom
        def readfrom(address,count):
            data = read(address,count)
            if count == 9 and target.runs == 1 and target.count == 9 and target.state == 0:
                return bytes(module.SCALE)
            return data
        wire.readfrom = readfrom
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'score readback mismatch'):
                module.check_live(wire)
            self.assertEqual((target.runs,target.completed,target.applied,target.gates()),(1,1,0,0))
            self.assertNotIn('SCORE 2/3',output.getvalue()); self.assertNotIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()

    def test_second_upload_transfer_fault_not_retried_and_no_implicit_PLAY(self):
        for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,tm,host,target,board,wire,values = fixture(); module = load(host); write = wire.writeto; attempts = []
            def writeto(address,data,stop=True):
                if data == b'\x20\xA0' and target.runs == 1 and target.count == 0:
                    attempts.append(data); raise fault('injected score replacement failure')
                return write(address,data,stop)
            wire.writeto = writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): module.check_live(wire)
                self.assertEqual(attempts,[b'\x20\xA0']); self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(5000); self.assertEqual((target.runs,target.applied,target.gates(),target.expirations),(1,0,0,0))
            finally: board.close(); target.close()

    def test_complete_three_scores_cross_ticks_wrap(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual((target.completed,target.aborted,target.expirations),(3,0,0))
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
            target.window.data[:8] = b'RCQAC01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'signature mismatch'): module.check_live(wire)
            self.assertEqual(wire.command_writes,0)
        finally: board.close(); target.close()


if __name__ == '__main__': unittest.main()
