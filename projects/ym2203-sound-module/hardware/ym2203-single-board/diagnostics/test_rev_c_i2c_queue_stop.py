# SPDX-License-Identifier: MIT
"""Physical STOP semantics,quiet beyond the original end,and score replay."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_queue import fixture

HERE = Path(__file__).resolve().parent


def load(queue):
    spec = importlib.util.spec_from_file_location('queue_stop', HERE/'rev_c_i2c_queue_stop_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'rev_c_i2c_queue_host': queue}): spec.loader.exec_module(module)
    module.time = queue.time
    return module


class QueueStopTests(unittest.TestCase):
    def test_complete_HOST_cancels_two_runs_replays_same_FM_score_from_start(self):
        model, target_module, queue, target, board, wire, values = fixture(); module = load(queue)
        commands = []; cancelled_at = []; original = target.apply
        def apply(command):
            commands.append(command)
            if command == 0 and target.active(): cancelled_at.append((model.us, target.next_note))
            original(command)
        target.apply = apply
        try:
            with redirect_stdout(io.StringIO()) as output: module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.runs, target.completed, target.aborted), (3, 1, 2))
            self.assertEqual(list(target.run_states), [5, 4, 5])
            self.assertEqual(list(target.run_voices), [0, 0, 3])
            first, full, last = target.run_notes
            self.assertTrue(3 <= first < 9 and 3 <= last < 9)
            self.assertEqual(full, 9)
            self.assertEqual(target.events, first+9+last)
            self.assertLessEqual(target.partial_cancels, 2)
            self.assertEqual(target.note_writes, target.events*2+target.partial_cancels)
            self.assertEqual((target.jobs, target.writes, target.applied, target.expirations), (5, 6, 0, 0))
            self.assertEqual(bytes(target.score), bytes(queue.pitch.MELODY))
            self.assertEqual(sum(queue.APPEND <= c < queue.APPEND+5 for c in commands), 9)
            self.assertEqual(commands.count(queue.CLEAR), 1)
            self.assertEqual(commands.count(8), 1)
            self.assertEqual([c for c in commands if c in (queue.PLAY_FM, queue.PLAY_SSG)], [queue.PLAY_FM, queue.PLAY_FM, queue.PLAY_SSG])
            self.assertEqual(target.times[9], 0)
            for n in range(9): self.assertTrue(n*500 <= target.times[9+n] <= n*500+100)
            # Replay began only after waiting beyond the abandoned run's old end.
            self.assertGreater(model.us-cancelled_at[-1][0], 4000000)
            self.assertEqual(len(cancelled_at), 2)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', output.getvalue())[1])
            self.assertEqual(final, len(commands) & 255)
            self.assertEqual(target.window.data[0x10], final)
            self.assertIn('HOST PASS:', output.getvalue())
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_progress_corruption_during_quiet_wait_is_caught_before_restart(self):
        model, target_module, queue, target, board, wire, values = fixture(); module = load(queue)
        def sleep(milliseconds):
            wire.sleep_ms(milliseconds)
            if milliseconds == module.QUIET_MS: target.window.data[0x1E] += 1
        module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms, ticks_diff=model.ticks_diff, sleep_ms=sleep)
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError, 'progress changed'):
                module.check_live(wire)
            self.assertEqual(target.runs, 1)
            self.assertNotIn('RESTART FM', output.getvalue())
            self.assertNotIn('HOST PASS:', output.getvalue())
            self.assertEqual(target.applied, 0)
        finally:
            board.close(); target.close()

    def test_STOP_transfer_faults_are_not_retried_or_followed_by_replay(self):
        for error in (OSError, RuntimeError, MemoryError, KeyboardInterrupt):
            model, target_module, queue, target, board, wire, values = fixture(); module = load(queue)
            write = wire.writeto; attempts = []
            def writeto(address, data, stop=True):
                if data == b'\x20\x00' and target.active():
                    attempts.append(data); raise error('injected STOP failure')
                return write(address, data, stop)
            wire.writeto = writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(error): module.check_live(wire)
                self.assertEqual(attempts, [b'\x20\x00'])
                self.assertNotIn('RESTART FM', output.getvalue())
                self.assertNotIn('HOST PASS:', output.getvalue())
                wire.sleep_ms(1600)
                self.assertEqual((target.applied, target.state, target.expirations), (0, 5, 1))
            finally:
                board.close(); target.close()

    def test_unrelated_pitch_corruption_after_STOP_is_rejected_before_replay(self):
        model, target_module, queue, target, board, wire, values = fixture(); module = load(queue)
        read = wire.readfrom
        def readfrom(address, count):
            data = read(address, count)
            if count == 16 and data[1] == 0 and data[13] == 5:
                data = data[:7]+bytes(((data[7]+1) % 5,))+data[8:]
            return data
        wire.readfrom = readfrom
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError, 'STOP queue state mismatch'):
                module.check_live(wire)
            self.assertEqual(target.runs, 1)
            self.assertNotIn('RESTART FM', output.getvalue())
            self.assertEqual(target.applied, 0)
        finally:
            board.close(); target.close()

    def test_full_run_crosses_ticks_wrap(self):
        model, target_module, queue, target, board, wire, values = fixture(); module = load(queue)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.completed, target.aborted, target.expirations), (1, 2, 0))
        finally:
            board.close(); target.close()

    def test_import_silent_and_old_wait_rejected_before_startup(self):
        model, target_module, queue, target, board, wire, values = fixture()
        try:
            accesses = list(wire.regs.accesses)
            with redirect_stdout(io.StringIO()) as output: module = load(queue)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(wire.regs.accesses, accesses)
            with patch.object(queue.mixer.Remote, 'ack_wait_ms', 10), patch.object(queue.pitch.six.staged.startup, 'check') as startup:
                with self.assertRaisesRegex(RuntimeError, 'v1.3 FM HOST'): module.check(wire)
                startup.assert_not_called()
        finally:
            board.close(); target.close()


if __name__ == '__main__': unittest.main()
