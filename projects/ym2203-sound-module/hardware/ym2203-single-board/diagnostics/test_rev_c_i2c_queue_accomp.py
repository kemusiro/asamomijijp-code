# SPDX-License-Identifier: MIT
"""Four-voice queued score,one-write budget,and actual mask cleanup paths."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_fm import command_events
from test_rev_c_i2c_fm_scheduling import SampledLink
from test_rev_c_i2c_queue import load as load_queue
from test_rev_c_i2c_six import ClockedPolyStream
from test_rev_c_six_voice_check import PolyModel

HERE = Path(__file__).resolve().parent


def load(model):
    queue_target, queue_host, values = load_queue(model)
    def source(name, modules):
        spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules): spec.loader.exec_module(module)
        return module
    target = source('rev_c_i2c_queue_accomp_target', {'rev_c_i2c_queue_target': queue_target})
    host = source('rev_c_i2c_queue_accomp_host', {'rev_c_i2c_queue_host': queue_host})
    target.gc = target.pitch.gc
    return target, host, values


def fixture():
    model = PolyModel(); module, host, values = load(model)
    board = module.pitch.PitchBus(); board.start(); board.prepare(); board.configure_three(); board.bass()
    for register in (8, 9, 10): board.checked(register, 0)
    model.stream = types.SimpleNamespace(starts=2)
    target = module.AccompaniedTarget(board); target.prepare(); target._enable(1)
    wire = SampledLink(model, target, values[-2], values[-3])
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms, ticks_ms=model.ticks_ms, ticks_diff=model.ticks_diff)
    host.time = host.queue.time = host.mixer.time = host.mixer.shared.time = clock
    return model, module, host, target, board, wire, values


def ready(module, host, target, wire):
    with redirect_stdout(io.StringIO()):
        remote = host.mixer.shared.preflight(wire, signature=host.SIGNATURE, remote_factory=host.queue.Remote)
        remote.command(8, 0); host.queue.upload(wire, remote)
    return remote


class AccompaniedQueueTests(unittest.TestCase):
    def test_full_HOST_four_voice_masks_held_chords_timed_notes_and_lease_cleanup(self):
        model, module, host, target, board, wire, values = fixture()
        record = target.record_note; poll = target.poll; commands = []; apply = target.apply
        def command(value): commands.append(value); apply(value)
        def one_poll():
            before = len(model.writes)
            poll()
            self.assertLessEqual(len(model.writes)-before, 1)
        def note(elapsed):
            record(elapsed)
            mask = 57 if target.voice == 0 else 15
            self.assertEqual((target.mask, target.applied), (mask, mask))
            self.assertEqual((model.level(19), model.level(26)), (1, 1))
            self.assertEqual(model.fm_keys, [bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11], [7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            for voice in range(6):
                index = target.score[target.next_note-1] if voice == target.voice else module.pitch.INITIAL[voice]
                if voice < 3:
                    self.assertEqual((model.registers[0xA4+voice], model.registers[0xA0+voice]), module.control.live.PITCHES[index][1:])
                else:
                    self.assertEqual(model.registers[2*(voice-3)] | model.registers[2*(voice-3)+1] << 8, module.pitch.SSG_PERIODS[index])
        target.record_note = note; target.poll = one_poll; target.apply = command
        try:
            with redirect_stdout(io.StringIO()) as output: host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.runs, target.completed, target.aborted, target.expirations), (3, 2, 1, 1))
            self.assertEqual(list(target.run_masks), [57, 15, 15])
            self.assertEqual(list(target.run_notes), [9, 9, 2])
            self.assertEqual((target.events, target.note_writes, target.partial_cancels), (20, 40, 0))
            self.assertEqual((target.jobs, target.writes, target.applied), (6, 24, 0))
            for run in (0, 1):
                for n in range(9): self.assertTrue(n*500 <= target.times[run*9+n] <= n*500+100)
                self.assertTrue(4500 <= target.run_off[run] <= 4600)
                self.assertGreaterEqual(target.run_end[run]-target.run_off[run], 135)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', output.getvalue())[1])
            self.assertEqual(final, len(commands) & 255)
            self.assertEqual(target.window.data[0x10], final)
            self.assertIn('HOST PASS:', output.getvalue())
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_STOP_and_lease_while_companions_on_but_output_still_muted_clean_all_bits(self):
        for fault in ('STOP', 'lease'):
            model, module, host, target, board, wire, values = fixture()
            try:
                remote = ready(module, host, target, wire)
                remote.command(host.queue.PLAY_FM, None)
                self.assertEqual(target.state, 1)
                self.assertTrue(target.applied & 56)
                self.assertEqual((model.level(19), model.level(26)), (0, 0))
                if fault == 'STOP': remote.command(0, 0)
                else:
                    transport, regs = values[-3], values[-2]
                    regs.values[transport.IC_STATUS] = 0x40
                    wire.sleep_ms(1200)
                    regs.values[transport.IC_STATUS] = 0
                wire.sleep_ms(200)
                self.assertEqual((target.state, target.applied, target.events), (5, 0, 0))
                self.assertEqual(target.expirations, int(fault == 'lease'))
                self.assertEqual(model.registers[8:11], [0, 0, 0])
                self.assertFalse(any(model.fm_keys))
            finally:
                board.close(); target.close()

    def test_STOP_during_partial_normal_end_preserves_actual_bits_until_cleanup(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            remote = ready(module, host, target, wire)
            remote.command(host.queue.PLAY_FM, None)
            while target.next_note < 9:
                wire.sleep_ms(100); remote.command(6, None)
            model.us = target.epoch*1000+4500000; wire.next_tick = model.us+11250
            target.poll()
            self.assertEqual((target.state, target.applied), (3, 56))
            remote.command(0, 0); wire.sleep_ms(200)
            self.assertEqual((target.state, target.applied, target.completed, target.aborted), (5, 0, 0, 1))
            self.assertEqual(model.registers[8:11], [0, 0, 0])
            self.assertFalse(any(model.fm_keys))
        finally:
            board.close(); target.close()

    def test_mask_corruption_and_transfer_faults_fail_without_replay_and_lease_cleans_chord(self):
        for fault in ('mask', OSError, RuntimeError, MemoryError, KeyboardInterrupt):
            model, module, host, target, board, wire, values = fixture()
            read = wire.readfrom; write = wire.writeto; attempts = []
            def readfrom(address, count):
                data = read(address, count)
                return b'\x3F' if fault == 'mask' and count == 1 and target.mode == 1 else data
            def writeto(address, data, stop=True):
                if isinstance(fault, type) and data == b'\x20\x06' and target.active():
                    attempts.append(data); raise fault('injected accompanied KEEP failure')
                return write(address, data, stop)
            wire.readfrom = readfrom; wire.writeto = writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(RuntimeError if fault == 'mask' else fault): host.check_live(wire)
                self.assertNotIn('HOST PASS:', output.getvalue())
                self.assertEqual(len(attempts), int(isinstance(fault, type)))
                wire.sleep_ms(1600)
                self.assertEqual((target.applied, model.level(19), model.level(26)), (0, 0, 0))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11], [0, 0, 0])
            finally:
                board.close(); target.close()

    def test_overdue_note_closes_every_output_and_cleans_full_mask_without_catchup(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            remote = ready(module, host, target, wire)
            remote.command(host.queue.PLAY_SSG, None); wire.sleep_ms(300)
            self.assertEqual((target.applied, target.next_note), (15, 1))
            model.us = target.epoch*1000+650000; wire.next_tick = model.us+11250
            with self.assertRaisesRegex(RuntimeError, 'late by more'): target.poll()
            self.assertEqual((target.state, target.events, model.level(19), model.level(26)), (5, 1, 0, 0))
            wire.sleep_ms(200)
            self.assertEqual(target.applied, 0)
        finally:
            board.close(); target.close()

    def test_native_deadline_and_cleanup_for_normal_cost_slow_write_and_key_or_pitch_exception(self):
        for fault in (None, 'slow', 'voice', 'pitch'):
            model = PolyModel(); module, host, values = load(model)
            staged, oldhost, startup, startup_host, control, mixer, live, machine, transport, regs, guard = values
            def listen(endpoint): endpoint.window.finished = True
            prepare = module.AccompaniedTarget.prepare; step = module.pitch.PitchBus.pitch_step; voice = module.pitch.PitchBus.voice
            def init(endpoint):
                prepare(endpoint)
                score = tuple(0xA0+n for n in host.queue.pitch.MELODY)
                commands = ((8, 40), (host.queue.CLEAR, 40)) + tuple((c, 40) for c in score)
                commands += ((host.queue.PLAY_SSG, 0),) + ((6, 40),)*12 + ((0, 40), (7, 0))
                regs.events = deque(e for c, wait in commands for e in command_events(c, wait))
            def cost(kind):
                if model.stream and model.stream.running:
                    model.us += 50000 if fault == 'slow' else 2300
                    if fault == kind: raise MemoryError('injected '+kind+' failure')
            def write(bus, v, note, part): cost('pitch'); step(bus, v, note, part)
            def key(bus, v, enabled): cost('voice'); voice(bus, v, enabled)
            with patch.object(startup, 'listen', listen), patch.object(live, 'Stream', lambda: ClockedPolyStream(model, guard)), patch.object(module.AccompaniedTarget, 'prepare', init), patch.object(module.pitch.PitchBus, 'pitch_step', write), patch.object(module.pitch.PitchBus, 'voice', key), redirect_stdout(io.StringIO()) as output:
                if fault is None: module.run()
                else:
                    with self.assertRaises(RuntimeError if fault == 'slow' else MemoryError): module.run()
            self.assertIn('SAFE:', output.getvalue())
            self.assertEqual('DONE:' in output.getvalue(), fault is None)
            if fault is None:
                self.assertEqual(model.stream.deadline_misses, 0)
                self.assertIn('completed=1', output.getvalue())
            self.assertTrue(model.stream.closed and model.audio.closed)
            model.assert_stopped()

    def test_complete_run_across_ticks_wrap_and_old_wait_rejected_before_startup(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            with patch.object(host.mixer.Remote, 'ack_wait_ms', 10), patch.object(host.queue.pitch.six.staged.startup, 'check') as startup:
                with self.assertRaisesRegex(RuntimeError, 'v1.3 FM HOST'): host.check(wire)
                startup.assert_not_called()
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
        finally:
            board.close(); target.close()

    def test_signature_mismatch_prevents_start_and_import_is_silent(self):
        model = PolyModel()
        with redirect_stdout(io.StringIO()) as output: module, host, values = load(model)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(model.pins, {}); self.assertEqual(values[-2].accesses, [])
        model, module, host, target, board, wire, values = fixture()
        try:
            target.window.data[:8] = b'RCQUE01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError, 'signature mismatch'): host.check_live(wire)
            self.assertEqual(wire.command_writes, 0)
        finally:
            board.close(); target.close()


if __name__ == '__main__': unittest.main()
