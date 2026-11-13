# SPDX-License-Identifier: MIT
"""Sustained changing six-voice traffic and failures against actual pitch jobs."""
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_voice_pitch import fixture

HERE = Path(__file__).resolve().parent


def load(pitch):
    spec = importlib.util.spec_from_file_location('voice_pitch_endurance', HERE/'rev_c_i2c_voice_pitch_endurance_host.py')
    module = importlib.util.module_from_spec(spec)
    with patch.dict(sys.modules, {'rev_c_i2c_voice_pitch_host': pitch}):
        spec.loader.exec_module(module)
    module.time = pitch.time
    return module


class DynamicPitchTests(unittest.TestCase):
    def test_full_180_seconds_all_six_keys_levels_gates_pitches_and_ACK_wrap(self):
        model, target_module, pitch, target, board, wire, values = fixture(); module = load(pitch)
        active = []; commands = []
        step, apply = board.pitch_step, target.apply
        def write(voice, note, part):
            step(voice, note, part)
            if target.mode:
                self.assertEqual((target.mask, target.applied), (63, 63))
                self.assertEqual(model.fm_keys, [True]*3)
                self.assertEqual(model.registers[8:11], [7]*3)
                self.assertEqual((model.level(19), model.level(26)), (1, 1))
                if part == 1:
                    active.append((voice, note))
        def command(value):
            commands.append(value); apply(value)
        board.pitch_step = write; target.apply = command
        try:
            with redirect_stdout(io.StringIO()) as output:
                module.check_live(wire)
            wire.sleep_ms(30)
            text = output.getvalue()
            elapsed, groups, updates, keeps, count, wraps = map(int, re.search(
                r'DYNAMIC PITCH COMPLETE / elapsed_ms=(\d+) groups=(\d+) updates=(\d+) KEEP=(\d+) commands=(\d+) wraps=(\d+)', text).groups())
            self.assertGreaterEqual(elapsed, 180000); self.assertLess(elapsed, 184000)
            self.assertEqual((updates, keeps, count), (groups*6, groups, groups*7))
            self.assertGreaterEqual(count, 256); self.assertGreaterEqual(wraps, 1)
            self.assertEqual(active, [(v, pitch.MELODY[(g+pitch.INITIAL[v]) % 9]) for g in range(groups) for v in range(6)])
            self.assertEqual((target.pitch_updates, target.pitch_writes, target.pitch_cancelled), (groups*6+12, groups*12+24, 0))
            self.assertEqual((target.jobs, target.writes, target.job, target.applied), (7, 24, -1, 0))
            self.assertEqual(target.expirations, 1)
            self.assertEqual(bytes(target.window.data[0x16:0x1C]), bytes(pitch.INITIAL))
            expected = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', text)[1])
            self.assertEqual(expected, (groups*7+59) & 255)
            self.assertEqual(expected, len(commands) & 255)
            self.assertEqual(target.window.data[0x10], expected)
            self.assertEqual([int(x) for x in re.findall(r'DYNAMIC PITCH (\d)/6', text)], list(range(1, 7)))
            self.assertTrue(target.window.finished)
            self.assertIn('HOST PASS:', text)
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_complete_run_crosses_ticks_ms_wrap(self):
        model, target_module, pitch, target, board, wire, values = fixture(); module = load(pitch)
        try:
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()):
                module.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.expirations, target.pitch_cancelled), (1, 0))
        finally:
            board.close(); target.close()

    def test_transfer_faults_are_not_retried_and_all_sources_lease_mute(self):
        for error in (OSError, RuntimeError, MemoryError, KeyboardInterrupt):
            model, target_module, pitch, target, board, wire, values = fixture(); module = load(pitch)
            original = wire.writeto; attempts = []
            def write(address, data, stop=True):
                if data == b'\x20\x81' and target.mode == 1:
                    attempts.append(data); raise error('injected live note failure')
                return original(address, data, stop)
            wire.writeto = write
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(error):
                    module.check_live(wire)
                self.assertEqual(attempts, [b'\x20\x81'])
                self.assertNotIn('HOST PASS:', output.getvalue())
                wire.sleep_ms(1500)
                self.assertEqual((target.mode, target.applied, model.level(19), model.level(26)), (0, 0, 0, 0))
            finally:
                board.close(); target.close()

    def test_corrupt_other_voice_pitch_is_caught_before_next_change(self):
        model, target_module, pitch, target, board, wire, values = fixture(); module = load(pitch)
        original = wire.readfrom; count_at_failure = []
        def read(address, count):
            data = original(address, count)
            if count == 12 and data[1:3] == b'\x06\x01':
                count_at_failure.append(wire.command_writes)
                return data[:-1]+bytes(((data[-1]+1) % 5,))
            return data
        wire.readfrom = read
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError, 'Per-voice state mismatch'):
                module.check_live(wire)
            self.assertEqual(count_at_failure, [wire.command_writes])
            self.assertNotIn('HOST PASS:', output.getvalue())
            wire.sleep_ms(1500)
            self.assertEqual(target.applied, 0)
        finally:
            board.close(); target.close()

    def test_unexpected_HOST_delay_is_not_cleared_by_STOP_or_following_note(self):
        model, target_module, pitch, target, board, wire, values = fixture(); module = load(pitch)
        pauses = []
        def sleep(milliseconds):
            if milliseconds == module.PAUSE_MS and target.mode == 1:
                pauses.append(milliseconds)
                wire.sleep_ms(1500)
            else:
                wire.sleep_ms(milliseconds)
        module.time = types.SimpleNamespace(ticks_ms=model.ticks_ms, ticks_diff=model.ticks_diff, sleep_ms=sleep)
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError, 'Per-voice state mismatch'):
                module.check_live(wire)
            self.assertEqual(pauses, [module.PAUSE_MS])
            self.assertEqual((target.applied, target.window.data[0x13]), (0, 1))
            self.assertNotIn('STOP acknowledged', output.getvalue())
            self.assertNotIn('HOST PASS:', output.getvalue())
        finally:
            board.close(); target.close()

    def test_incomplete_coverage_rejected_old_helper_rejected_and_import_silent(self):
        model, target_module, pitch, target, board, wire, values = fixture()
        try:
            before = list(wire.regs.accesses)
            with redirect_stdout(io.StringIO()) as output:
                module = load(pitch)
            self.assertEqual(output.getvalue(), '')
            self.assertEqual(wire.regs.accesses, before)
            with patch.object(pitch.mixer.Remote, 'ack_wait_ms', 10), patch.object(pitch.six.staged.startup, 'check') as startup:
                with self.assertRaisesRegex(RuntimeError, 'v1.3 FM HOST'):
                    module.check(wire)
                startup.assert_not_called()
            module.DURATION_MS = 1000
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError, 'coverage incomplete'):
                module.check_live(wire)
            self.assertNotIn('HOST PASS:', output.getvalue())
            wire.sleep_ms(1500)
            self.assertEqual(target.applied, 0)
        finally:
            board.close(); target.close()


if __name__ == '__main__':
    unittest.main()
