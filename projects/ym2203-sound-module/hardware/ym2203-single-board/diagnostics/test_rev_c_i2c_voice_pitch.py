# SPDX-License-Identifier: MIT
"""Six independent pitch pairs, real bus writes and unchanged native guard."""
from collections import deque
from contextlib import redirect_stdout
import importlib.util
import io
import math
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

from test_rev_c_i2c_fm import command_events
from test_rev_c_i2c_fm_scheduling import SampledLink
from test_rev_c_i2c_six import ClockedPolyStream, load as load_six
from test_rev_c_six_voice_check import PolyModel

HERE = Path(__file__).resolve().parent


def load(model):
    six_module, six_host, values = load_six(model)
    def source(name, modules):
        spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules):
            spec.loader.exec_module(module)
        return module
    target = source('rev_c_i2c_voice_pitch_target', {'rev_c_i2c_six_target': six_module})
    host = source('rev_c_i2c_voice_pitch_host', {'rev_c_i2c_six_host': six_host})
    target.gc = target.control.live.gc
    return target, host, values


def fixture():
    model = PolyModel(); module, host, values = load(model)
    board = module.PitchBus(); board.start(); board.prepare(); board.configure_three(); board.bass()
    for register in (8, 9, 10):
        board.checked(register, 0)
    model.stream = types.SimpleNamespace(starts=2)
    target = module.PitchTarget(board); target.prepare(); target._enable(1)
    wire = SampledLink(model, target, values[-2], values[-3])
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms, ticks_ms=model.ticks_ms, ticks_diff=model.ticks_diff)
    host.time = host.mixer.time = host.mixer.shared.time = clock
    return model, module, host, target, board, wire, values


class VoicePitchTests(unittest.TestCase):
    def test_complete_HOST_six_melodies_leave_held_chord_and_other_pitch_indices_unchanged(self):
        model, module, host, target, board, wire, values = fixture()
        original_step = board.pitch_step; original_apply = target.apply
        active = []; commands = []; snapshots = []
        def apply(command):
            commands.append(command); original_apply(command)
        def step(voice, note, part):
            before = list(model.writes)
            gates = model.level(19), model.level(26)
            keys = tuple(model.fm_keys); levels = tuple(model.registers[8:11])
            status = bytes(target.window.data[0x16:0x1C])
            original_step(voice, note, part)
            self.assertEqual(len(model.writes)-len(before), 1)
            self.assertEqual((model.level(19), model.level(26)), gates)
            self.assertEqual(tuple(model.fm_keys), keys)
            self.assertEqual(tuple(model.registers[8:11]), levels)
            self.assertEqual(bytes(target.window.data[0x16:0x1C]), status)
            reg, value = model.writes[-1]
            if voice < 3:
                self.assertEqual(reg, (0xA4 if part == 0 else 0xA0)+voice)
            else:
                self.assertEqual(reg, 2*(voice-3)+(1 if part == 0 else 0))
            if part == 1 and target.mode:
                active.append((voice, note, target.mask))
                self.assertEqual(target.mask, (1 << voice) | (56 if voice < 3 else 7))
                self.assertEqual((keys, levels),
                    (tuple(bool(target.mask & (1 << i)) for i in range(3)),
                     tuple(7 if target.mask & (1 << (i+3)) else 0 for i in range(3))))
                for other in range(6):
                    if other == voice:
                        continue
                    index = status[other]
                    if other < 3:
                        self.assertEqual((model.registers[0xA4+other], model.registers[0xA0+other]),
                                         module.control.live.PITCHES[index][1:])
                    else:
                        period = model.registers[2*(other-3)] | model.registers[2*(other-3)+1] << 8
                        self.assertEqual(period, module.SSG_PERIODS[index])
                snapshots.append(bytes(target.window.data[0x16:0x1C]))
        board.pitch_step = step; target.apply = apply
        try:
            with redirect_stdout(io.StringIO()) as output:
                host.check_live(wire)
            wire.sleep_ms(30)
            self.assertEqual(active, [(v, n, (1 << v) | (56 if v < 3 else 7)) for v in range(6) for n in host.MELODY[1:]])
            self.assertEqual((target.pitch_updates, target.pitch_writes, target.pitch_cancelled), (90, 180, 0))
            self.assertEqual((target.jobs, target.writes, target.expirations), (17, 60, 1))
            self.assertEqual((target.pitch_command, target.pitch_step, target.job, target.applied), (-1, 2, -1, 0))
            self.assertEqual(bytes(target.window.data[0x16:0x1C]), bytes(host.INITIAL))
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)', output.getvalue())[1])
            self.assertEqual(final, len(commands) & 255)
            self.assertEqual(final, 201)
            self.assertEqual(final, target.window.data[0x10])
            self.assertTrue(target.window.finished)
            self.assertEqual(output.getvalue().count('NOTE '), 54)
            self.assertIn('HOST PASS:', output.getvalue())
            self.assertLess(model.us/1000, 240000)
            # Each initial C was configured muted; first live pitch is D.
            self.assertEqual([n for v, n, mask in active[::8]], [1]*6)
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_pair_is_one_register_per_idle_poll_and_single_ACK_after_second(self):
        for voice in range(6):
            model, module, host, target, board, wire, values = fixture()
            try:
                target.live_started = True
                target.apply(0x80+voice*5+4)
                self.assertEqual(target.window.data[0x15], 1)
                self.assertEqual(target.window.data[0x10], 0)
                before = len(model.writes)
                target.poll()
                self.assertEqual(len(model.writes)-before, 1)
                self.assertEqual(target.window.data[0x10], 0)
                transport, regs = values[-3], values[-2]
                regs.values[transport.IC_STATUS] = 0x40
                target.poll()
                self.assertEqual(len(model.writes)-before, 1)
                regs.values[transport.IC_STATUS] = 0
                target.poll()
                self.assertEqual(len(model.writes)-before, 2)
                self.assertEqual(bytes(target.window.data[0x10:0x16]), bytes((1, 0x80+voice*5+4, 0, 0, 0, 0)))
                self.assertEqual(target.window.data[0x16+voice], 4)
            finally:
                board.close(); target.close()

    def test_lease_cancels_half_pair_before_split_source_cleanup_without_success_ACK(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            target.live_started = True; target.apply(127); wire.sleep_ms(250)
            old_ack = target.window.data[0x10]
            target.apply(0x81); target.poll()
            self.assertEqual(target.pitch_step, 1)
            model.us += 1100000
            target.poll()
            self.assertEqual((target.pitch_command, target.pitch_cancelled), (-1, 1))
            self.assertEqual((target.mode, model.level(19), model.level(26)), (0, 0, 0))
            for unused in range(8):
                target.poll()
            self.assertEqual(target.window.data[0x10], old_ack)
            self.assertEqual((target.applied, target.window.data[0x13]), (0, 1))
            self.assertEqual(target.window.data[0x16], 0)
            with self.assertRaisesRegex(RuntimeError, 'non-expired'):
                target.apply(0x81)
        finally:
            board.close(); target.close()

    def test_policy_prestart_pending_bad_inputs_and_second_register_fault(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            before = len(model.writes)
            for args in ((-1, 0, 0), (6, 0, 0), (True, 0, 0), (0, -1, 0), (0, 5, 0), (0, True, 0), (0, 0, 2), (0, 0, True)):
                with self.assertRaises(ValueError):
                    board.pitch_step(*args)
            self.assertEqual(len(model.writes), before)
            for command in (-1, True, 0x9E, 255):
                with self.assertRaises(ValueError):
                    target.apply(command)
            with self.assertRaisesRegex(RuntimeError, 'requires START'):
                target.apply(0x80)
            target.live_started = True; target.apply(127)
            with self.assertRaisesRegex(RuntimeError, 'Voice update pending'):
                target.apply(0x80)
            wire.sleep_ms(250)
            target.apply(0x81)
            for command in (0, 6, 7, 127, 0x82):
                with self.assertRaisesRegex(RuntimeError, 'Pitch update pending'):
                    target.apply(command)
            target.poll()
            ack = target.window.data[0x10]
            with patch.object(board, 'pitch_step', side_effect=RuntimeError('injected second register fault')):
                with self.assertRaisesRegex(RuntimeError, 'second register fault'):
                    target.poll()
            self.assertEqual((target.window.data[0x10], target.window.data[0x16], target.window.data[0x15]), (ack, 0, 1))
        finally:
            board.close(); target.close()
        model.assert_stopped()

    def test_HOST_rejects_wrong_signature_corrupt_pitch_and_transfer_error_without_resend(self):
        for fault in ('signature', 'pitch', 'transfer'):
            model, module, host, target, board, wire, values = fixture()
            attempts = []; original = wire.writeto
            def write(address, data, stop=True):
                if fault == 'transfer' and data == b'\x20\x81':
                    attempts.append(data); raise OSError('injected note failure')
                return original(address, data, stop)
            wire.writeto = write
            try:
                if fault == 'signature':
                    target.window.data[:8] = b'RCSIX01!'
                if fault == 'pitch':
                    target.window.data[0x1B] = 0
                with redirect_stdout(io.StringIO()) as output:
                    with self.assertRaises(OSError if fault == 'transfer' else RuntimeError):
                        host.check_live(wire)
                self.assertNotIn('HOST PASS:', output.getvalue())
                self.assertEqual(attempts, [b'\x20\x81'] if fault == 'transfer' else [])
                wire.sleep_ms(1500)
                self.assertEqual(target.applied, 0)
            finally:
                board.close(); target.close()

    def test_split_pitch_jobs_preserve_native_guard_with_artificial_register_and_I2C_costs(self):
        for fault in (None, 'slow', MemoryError, KeyboardInterrupt):
            model = PolyModel(); module, host, values = load(model)
            staged, oldhost, startup, startup_host, control, mixer, live, machine, transport, regs, guard = values
            def listen(endpoint):
                endpoint.window.finished = True
            prepare = module.PitchTarget.prepare; step = module.PitchBus.pitch_step; poll = control.ControlTarget.poll
            def init(endpoint):
                prepare(endpoint)
                commands = (8, 128, 0x79, 129, 130, 131, 132, 131, 0, 145, 0x0F+0x40, 146, 147, 0, 127, 7)
                # Leave the final full chord without KEEP long enough to expire.
                regs.events = deque(e for c in commands for e in command_events(c, 130 if c == 127 else 40))
            def write(bus, voice, note, part):
                if model.stream and model.stream.running:
                    model.us += 50000 if fault == 'slow' else 4000
                    if fault in (MemoryError, KeyboardInterrupt):
                        raise fault('injected pitch write failure')
                step(bus, voice, note, part)
            def service(endpoint):
                if model.stream and model.stream.running:
                    model.us += 4000
                poll(endpoint)
            with patch.object(startup, 'listen', listen), patch.object(live, 'Stream', lambda: ClockedPolyStream(model, guard)), patch.object(module.PitchTarget, 'prepare', init), patch.object(module.PitchBus, 'pitch_step', write), patch.object(control.ControlTarget, 'poll', service), redirect_stdout(io.StringIO()) as output:
                if fault is None:
                    module.run()
                else:
                    with self.assertRaises(RuntimeError if fault == 'slow' else fault):
                        module.run()
            self.assertIn('SAFE:', output.getvalue())
            self.assertEqual('DONE:' in output.getvalue(), fault is None)
            if fault is None:
                self.assertEqual(model.stream.deadline_misses, 0)
                self.assertIn('cancelled=0', output.getvalue())
            self.assertTrue(model.stream.closed and model.audio.closed)
            model.assert_stopped()

    def test_note_bytes_frequency_bounds_and_full_HOST_across_ticks_wrap(self):
        model, module, host, target, board, wire, values = fixture()
        try:
            for note in range(5):
                name, high, low = module.control.live.PITCHES[note]
                frequency = 4000000/72 * (((high & 7) << 8) | low) * 2**((high >> 3) & 7) / 2**21
                ideal = 261.625565 * 2**((0, 2, 4, 5, 7)[note]/12)
                self.assertLess(abs(1200*math.log2(frequency/ideal)), 8)
                self.assertLess(abs(1200*math.log2((62500/module.SSG_PERIODS[note])/(ideal/2))), 8)
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()):
                host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
        finally:
            board.close(); target.close()

    def test_import_is_silent_no_pin_or_register_access_and_old_wait_rejected(self):
        model = PolyModel()
        with redirect_stdout(io.StringIO()) as output:
            module, host, values = load(model)
        self.assertEqual(output.getvalue(), '')
        self.assertEqual(model.pins, {})
        self.assertEqual(values[-2].accesses, [])
        with patch.object(host.mixer.Remote, 'ack_wait_ms', 10), patch.object(host.six.staged.startup, 'check') as startup:
            with self.assertRaisesRegex(RuntimeError, 'v1.3 FM HOST'):
                host.check(None)
            startup.assert_not_called()


if __name__ == '__main__':
    unittest.main()
