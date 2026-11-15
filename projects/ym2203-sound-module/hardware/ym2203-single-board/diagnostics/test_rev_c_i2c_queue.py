# SPDX-License-Identifier: MIT
"""Uploaded score,timed GPIO events,lease cancellation and native deadlines."""
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
from test_rev_c_i2c_six import ClockedPolyStream
from test_rev_c_i2c_voice_pitch import load as load_pitch
from test_rev_c_six_voice_check import PolyModel

HERE = Path(__file__).resolve().parent


def load(model):
    pitch_target, pitch_host, values = load_pitch(model)
    def source(name, modules):
        spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        return module
    target = source('rev_c_i2c_queue_target', {'rev_c_i2c_voice_pitch_target': pitch_target})
    host = source('rev_c_i2c_queue_host', {'rev_c_i2c_voice_pitch_host': pitch_host})
    target.gc = pitch_target.gc
    return target, host, values


def fixture():
    model = PolyModel(); module, host, values = load(model)
    board = module.pitch.PitchBus(); board.start(); board.prepare(); board.configure_three(); board.bass()
    for register in (8, 9, 10): board.checked(register, 0)
    model.stream = types.SimpleNamespace(starts=2)
    target = module.QueueTarget(board); target.prepare(); target._enable(1)
    wire = SampledLink(model, target, values[-2], values[-3])
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms, ticks_ms=model.ticks_ms, ticks_diff=model.ticks_diff)
    host.time = host.mixer.time = host.mixer.shared.time = clock
    return model, module, host, target, board, wire, values


def ready(module, host, target, wire):
    with redirect_stdout(io.StringIO()):
        remote = host.mixer.shared.preflight(wire, signature=host.SIGNATURE, remote_factory=host.Remote)
        remote.command(8, 0)
        host.upload(wire, remote)
    return remote


class QueueTests(unittest.TestCase):
    def test_complete_HOST_upload_readback_two_clocked_scales_and_lease_abort(self):
        model, module, host, target, board, wire, values = fixture()
        original = target.record_note; commands = []; active_commands = []
        apply = target.apply
        def command(value):
            commands.append(value)
            if target.active(): active_commands.append(value)
            apply(value)
        def note(elapsed):
            original(elapsed)
            voice = target.voice
            self.assertEqual(target.mask, 1 << voice)
            self.assertEqual(model.fm_keys, [voice == i for i in range(3)])
            self.assertEqual(model.registers[8:11], [7 if voice == i+3 else 0 for i in range(3)])
            self.assertEqual((model.level(19), model.level(26)), (1, int(voice < 3)))
            index = target.next_note-1; selected = target.score[index]
            if voice < 3:
                self.assertEqual((model.registers[0xA4+voice], model.registers[0xA0+voice]), module.control.live.PITCHES[selected][1:])
            else:
                self.assertEqual(model.registers[0] | model.registers[1] << 8, module.pitch.SSG_PERIODS[selected])
        target.apply = command; target.record_note = note
        try:
            with redirect_stdout(io.StringIO()) as output: host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.runs, target.completed, target.aborted), (3, 2, 1))
            self.assertEqual(list(target.run_states), [4, 4, 5])
            self.assertEqual(list(target.run_voices), [0, 3, 3])
            self.assertEqual(list(target.run_notes), [9, 9, 2])
            self.assertEqual((target.events, target.note_writes, target.partial_cancels), (20, 40, 0))
            for run in (0, 1):
                times = target.times[run*9:(run+1)*9]
                self.assertEqual(times[0], 0)
                for n, elapsed in enumerate(times):
                    self.assertGreaterEqual(elapsed, n*500)
                    self.assertLessEqual(elapsed, n*500+100)
                self.assertGreaterEqual(target.run_off[run], 4500)
                self.assertLessEqual(target.run_off[run], 4600)
            self.assertGreaterEqual(target.run_end[0]-target.run_off[0], 135)
            self.assertEqual(target.run_end[1], target.run_off[1])
            self.assertTrue(all(c == 6 for c in active_commands))
            self.assertEqual((target.jobs, target.writes, target.applied), (6, 6, 0))
            self.assertEqual(target.expirations, 1)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', output.getvalue())[1])
            self.assertEqual(final, len(commands) & 255)
            self.assertEqual(target.window.data[0x10], final)
            self.assertIn('HOST PASS:', output.getvalue())
            saved = list(target.times)
            with self.assertRaisesRegex(RuntimeError, 'fewer than three'):
                target.apply(module.PLAY_FM)
            self.assertEqual(target.times, saved)
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_STOP_cancels_half_written_note_without_later_events_or_ACK(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            remote = ready(module, host, target, wire)
            remote.command(module.PLAY_FM, None); wire.sleep_ms(250)
            self.assertEqual(target.next_note, 1)
            model.us = target.epoch*1000+500000
            wire.next_tick = model.us+11250
            target.poll()
            self.assertEqual(target.pair_step, 1)
            before = target.events
            remote.command(0, 0)
            wire.sleep_ms(2000)
            self.assertEqual((target.state, target.events, target.partial_cancels), (5, before, 1))
            self.assertEqual((target.applied, model.level(19), model.level(26)), (0, 0, 0))
            self.assertEqual(target.window.data[0x11], 0)
        finally:
            board.close(); target.close()

    def test_no_keepalive_during_ARMING_aborts_quietly_and_autonomous_events_never_extend_lease(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            remote = ready(module, host, target, wire)
            target.apply(module.PLAY_FM)
            transport, regs = values[-3], values[-2]
            regs.values[transport.IC_STATUS] = 0x40
            wire.sleep_ms(1200)
            self.assertEqual((target.state, target.events, target.expirations), (5, 0, 1))
            self.assertEqual((model.level(19), model.level(26)), (0, 0))
            regs.values[transport.IC_STATUS] = 0
            wire.sleep_ms(100)
            self.assertEqual(target.applied, 0)
        finally:
            board.close(); target.close()

    def test_overdue_event_stops_without_burst_catchup(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            remote = ready(module, host, target, wire)
            remote.command(module.PLAY_FM, None); wire.sleep_ms(250)
            model.us = target.epoch*1000+650000
            before = target.note_writes
            with self.assertRaisesRegex(RuntimeError, 'late by more'):
                target.poll()
            self.assertEqual((target.state, target.events, target.note_writes), (5, 1, before))
            self.assertEqual((model.level(19), model.level(26)), (0, 0))
        finally:
            board.close(); target.close()

    def test_capacity_prestart_invalid_commands_and_mutation_while_playing_rejected(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            for value in (-1, True, 0xA8, 128, 127):
                with self.assertRaises(ValueError): target.apply(value)
            with self.assertRaises(RuntimeError): target.apply(module.PLAY_FM)
            target.apply(module.CLEAR)
            for _ in range(9): target.apply(module.APPEND)
            before = bytes(target.score)
            with self.assertRaises(ValueError): target.apply(module.APPEND+1)
            self.assertEqual(bytes(target.score), before)
            target.live_started = True; target.apply(module.PLAY_FM)
            for value in (module.CLEAR, module.APPEND, module.PLAY_SSG, 8, 128):
                with self.assertRaisesRegex(RuntimeError, 'Queue active'): target.apply(value)
        finally:
            board.close(); target.close()

    def test_transfer_faults_and_wrong_signature_or_score_fail_without_retries(self):
        for fault in ('signature', 'score', OSError, RuntimeError, MemoryError, KeyboardInterrupt):
            model, module, host, target, board, wire, values = fixture()
            attempts = []; write = wire.writeto; read = wire.readfrom
            def writeto(address, data, stop=True):
                if isinstance(fault, type) and data == b'\x20\x06' and target.active():
                    attempts.append(data); raise fault('injected queued KEEP fault')
                return write(address, data, stop)
            def readfrom(address, count):
                result = read(address, count)
                return bytes(9) if fault == 'score' and count == 9 else result
            wire.writeto = writeto; wire.readfrom = readfrom
            try:
                if fault == 'signature': target.window.data[:8] = b'RCPOL01!'
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault if isinstance(fault, type) else RuntimeError):
                    host.check_live(wire)
                self.assertEqual(len(attempts), 1 if isinstance(fault, type) else 0)
                self.assertNotIn('HOST PASS:', output.getvalue())
                wire.sleep_ms(1500)
                self.assertEqual(target.applied, 0)
                self.assertEqual((model.level(19), model.level(26)), (0, 0))
            finally:
                board.close(); target.close()

    def test_complete_run_crosses_ticks_wrap_and_old_wait_is_rejected(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            with patch.object(host.mixer.Remote, 'ack_wait_ms', 10), patch.object(host.pitch.six.staged.startup, 'check') as startup:
                with self.assertRaisesRegex(RuntimeError, 'v1.3 FM HOST'): host.check(wire)
                startup.assert_not_called()
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
        finally:
            board.close(); target.close()

    def test_native_deadlines_hold_and_slow_registers_or_exceptions_stop_safely(self):
        for fault in (None, 'slow', MemoryError, KeyboardInterrupt):
            model = PolyModel(); module, host, values = load(model)
            staged, oldhost, startup, startup_host, control, mixer, live, machine, transport, regs, guard = values
            def listen(endpoint): endpoint.window.finished = True
            prepare = module.QueueTarget.prepare; step = module.pitch.PitchBus.pitch_step
            def init(endpoint):
                prepare(endpoint)
                score = tuple(0xA0+n for n in host.pitch.MELODY)
                commands = ((8, 40), (module.CLEAR, 40)) + tuple((c, 40) for c in score)
                commands += ((module.PLAY_FM, 0),) + ((6, 40),)*12 + ((0, 40), (7, 0))
                regs.events = deque(e for c, delay in commands for e in command_events(c, delay))
            def write(bus, voice, note, part):
                if model.stream and model.stream.running:
                    model.us += 50000 if fault == 'slow' else 2300
                    if fault in (MemoryError, KeyboardInterrupt): raise fault('injected scheduled write failure')
                step(bus, voice, note, part)
            with patch.object(startup, 'listen', listen), patch.object(live, 'Stream', lambda: ClockedPolyStream(model, guard)), patch.object(module.QueueTarget, 'prepare', init), patch.object(module.pitch.PitchBus, 'pitch_step', write), redirect_stdout(io.StringIO()) as output:
                if fault is None: module.run()
                else:
                    with self.assertRaises(RuntimeError if fault == 'slow' else fault): module.run()
            self.assertIn('SAFE:', output.getvalue())
            self.assertEqual('DONE:' in output.getvalue(), fault is None)
            if fault is None:
                self.assertEqual(model.stream.deadline_misses, 0)
                self.assertIn('completed=1', output.getvalue())
            self.assertTrue(model.stream.closed and model.audio.closed)
            model.assert_stopped()

    def test_import_is_silent_without_GPIO_or_register_access(self):
        model = PolyModel()
        with redirect_stdout(io.StringIO()) as output: module, host, values = load(model)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(model.pins, {})
        self.assertEqual(values[-2].accesses, [])


if __name__ == '__main__': unittest.main()
