# SPDX-License-Identifier: MIT
"""Muted STOP cancels keys and queue;PLAY alone resets gate state for replay."""
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
    spec = importlib.util.spec_from_file_location('queue_mute_stop', HERE/'rev_c_i2c_queue_mute_stop_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'rev_c_i2c_queue_mute_host':host,'rev_c_i2c_queue_stop_host':stop}):
        spec.loader.exec_module(module)
    module.time = host.time
    return module


class MutedStopTests(unittest.TestCase):
    def test_complete_HOST_muted_STOP_all_sources_quiet_and_unmuted_PLAY_only_replay(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        commands = []; quiet = []; apply = target.apply; poll = target.poll; record = target.record_note
        def command(value):
            commands.append(value)
            if value == 0 and target.active(): self.assertIn(target.gates(),(1,2))
            apply(value)
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before,1)
        def note(elapsed):
            record(elapsed)
            mask = 15 if target.voice == 3 else 57
            self.assertEqual(target.applied,mask)
            self.assertEqual(model.fm_keys,[bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11],[7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            self.assertEqual(target.gates(),model.level(26) | model.level(19) << 1)
            if target.runs == 2: self.assertEqual(target.gates(),3)
        def sleep(ms):
            if ms == module.stop.QUIET_MS:
                quiet.append(model.us)
                self.assertEqual((target.applied,target.gates(),model.level(19),model.level(26)),(0,0,0,0))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                before = len(model.writes); wire.sleep_ms(ms); self.assertEqual(len(model.writes),before)
            else: wire.sleep_ms(ms)
        target.apply = command; target.poll = one_poll; target.record_note = note
        module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations),(3,1,2,0))
            self.assertEqual(list(target.run_states),[5,4,5]); self.assertEqual(list(target.run_masks),[57,57,15])
            first,full,last = target.run_notes
            self.assertTrue(5 <= first < 9 and 5 <= last < 9); self.assertEqual(full,9)
            self.assertEqual((target.gate_commands,target.dac_mutes,target.line_mutes,target.restores),(2,1,1,0))
            self.assertEqual((target.jobs,target.writes,target.applied),(5,24,0)); self.assertEqual(len(quiet),2)
            self.assertEqual(target.events,first+9+last)
            self.assertEqual(target.note_writes,2*target.events+target.partial_cancels); self.assertLessEqual(target.partial_cancels,2)
            self.assertEqual(list(target.gate_notes[9:18]),[3]*9)
            for run,muted in ((0,2),(2,1)):
                trace = list(target.gate_notes[run*9:run*9+target.run_notes[run]])
                self.assertEqual(trace[0],3); self.assertGreaterEqual(trace.count(muted),2)
                self.assertEqual(list(target.gate_notes[run*9+target.run_notes[run]:(run+1)*9]),[255]*(9-target.run_notes[run]))
            self.assertEqual(commands.count(module.queue.CLEAR),1)
            self.assertEqual(sum(module.queue.APPEND <= c < module.queue.APPEND+5 for c in commands),9)
            self.assertEqual(commands.count(8),1); self.assertNotIn(3,commands)
            self.assertEqual(target.times[9],0)
            for n in range(9): self.assertTrue(500*n <= target.times[9+n] <= 500*n+100)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,len(commands)&255); self.assertIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_STOP_faults_in_either_mute_are_not_retried_and_lease_closes_all_sources(self):
        for gate in (2,1):
            for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
                model,tm,host,target,board,wire,values = fixture(); module = load(host)
                write = wire.writeto; attempts = []
                def writeto(address,data,stop=True):
                    if data == b'\x20\x00' and target.active() and target.gates() == gate:
                        attempts.append(data); raise fault('injected muted STOP failure')
                    return write(address,data,stop)
                wire.writeto = writeto
                try:
                    with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): module.check_live(wire)
                    self.assertEqual(attempts,[b'\x20\x00']); self.assertNotIn('HOST PASS:',output.getvalue())
                    self.assertEqual(target.runs,1 if gate == 2 else 3)
                    wire.sleep_ms(1600)
                    self.assertEqual((target.gates(),target.applied),(0,0))
                    self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                    saved = target.events; wire.sleep_ms(4000); self.assertEqual(target.events,saved)
                finally: board.close(); target.close()

    def test_corrupted_gate_or_progress_or_score_during_quiet_rejected_before_replay(self):
        for fault in ('gate','progress','score'):
            model,tm,host,target,board,wire,values = fixture(); module = load(host)
            corrupt = []; read = wire.readfrom
            def readfrom(address,count):
                data = read(address,count)
                if fault == 'gate' and corrupt and count == 1 and target.window.pointer == 0x2A:
                    return b'\x03'
                return data
            wire.readfrom = readfrom
            def sleep(ms):
                wire.sleep_ms(ms)
                if ms == module.stop.QUIET_MS:
                    if fault == 'gate': corrupt.append(True)
                    else: target.window.data[0x1E if fault == 'progress' else 0x30] += 1
            module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff,sleep_ms=sleep)
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'gate readback|progress changed|changed uploaded score'):
                    module.check_live(wire)
                self.assertNotIn('RESTART FM',output.getvalue()); self.assertNotIn('HOST PASS:',output.getvalue())
                self.assertEqual((target.runs,target.applied),(1,0))
            finally: board.close(); target.close()

    def test_mute_transfer_fault_fails_without_retry_and_lease_stops_the_chord(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        write = wire.writeto; attempts = []
        def writeto(address,data,stop=True):
            if data == b'\x20\x04': attempts.append(data); raise OSError('injected DAC mute failure')
            return write(address,data,stop)
        wire.writeto = writeto
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaises(OSError): module.check_live(wire)
            self.assertEqual(attempts,[b'\x20\x04']); self.assertNotIn('HOST PASS:',output.getvalue())
            wire.sleep_ms(1600); self.assertEqual((target.applied,target.gates()),(0,0))
        finally: board.close(); target.close()

    def test_complete_sequence_crosses_ticks_wrap(self):
        model,tm,host,target,board,wire,values = fixture(); module = load(host)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual((target.completed,target.aborted,target.expirations),(1,2,0))
        finally: board.close(); target.close()

    def test_silent_import_old_wait_and_old_signature_rejected(self):
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
