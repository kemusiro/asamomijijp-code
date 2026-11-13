# SPDX-License-Identifier: MIT
"""A gate-only mute must leave the independent queue clock and sources running."""
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

from test_rev_c_i2c_queue_accomp import load as load_accomp
from test_rev_c_i2c_fm import command_events
from test_rev_c_i2c_fm_scheduling import SampledLink
from test_rev_c_i2c_six import ClockedPolyStream
from test_rev_c_six_voice_check import PolyModel

HERE = Path(__file__).resolve().parent


def load(model):
    accomp_target, accomp_host, values = load_accomp(model)
    def source(name, modules):
        spec = importlib.util.spec_from_file_location(name, HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules, modules): spec.loader.exec_module(module)
        return module
    target = source('rev_c_i2c_queue_mute_target', {'rev_c_i2c_queue_accomp_target':accomp_target})
    host = source('rev_c_i2c_queue_mute_host', {'rev_c_i2c_queue_accomp_host':accomp_host})
    target.gc = target.pitch.gc
    return target, host, values


def fixture():
    model = PolyModel(); module, host, values = load(model)
    board = module.pitch.PitchBus(); board.start(); board.prepare(); board.configure_three(); board.bass()
    for register in (8,9,10): board.checked(register,0)
    model.stream = types.SimpleNamespace(starts=2)
    target = module.MutedQueueTarget(board); target.prepare(); target._enable(1)
    wire = SampledLink(model,target,values[-2],values[-3])
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    host.time = host.accomp.time = host.queue.time = host.mixer.time = host.mixer.shared.time = clock
    return model,module,host,target,board,wire,values


def ready(host,wire):
    with redirect_stdout(io.StringIO()):
        remote = host.mixer.shared.preflight(wire,signature=host.SIGNATURE,remote_factory=host.queue.Remote)
        remote.command(8,0); host.queue.upload(wire,remote)
    return remote


class QueuedMuteTests(unittest.TestCase):
    def test_full_HOST_continuous_clock_held_sources_muted_notes_and_resume_without_replay(self):
        model,module,host,target,board,wire,values = fixture()
        record = target.record_note; apply = target.apply; poll = target.poll; commands = []
        def note(elapsed):
            record(elapsed)
            mask = 57 if target.voice == 0 else 15
            self.assertEqual((target.mask,target.applied),(mask,mask))
            self.assertEqual(target.gates(),model.level(26) | (model.level(19) << 1))
            self.assertEqual(model.fm_keys,[bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11],[7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            for v in range(6):
                index = target.score[target.next_note-1] if v == target.voice else module.pitch.INITIAL[v]
                if v < 3: self.assertEqual((model.registers[0xA4+v],model.registers[0xA0+v]),module.control.live.PITCHES[index][1:])
                else: self.assertEqual(model.registers[2*(v-3)] | model.registers[2*(v-3)+1] << 8,module.pitch.SSG_PERIODS[index])
        def command(value):
            commands.append(value)
            snapshot = (target.epoch,target.events,target.next_note,target.applied,len(model.writes))
            apply(value)
            if value in (3,4,5):
                self.assertEqual((target.epoch,target.events,target.next_note,target.applied,len(model.writes)),snapshot)
                self.assertEqual(target.mode,1)
                self.assertEqual(target.gates(),model.level(26) | (model.level(19) << 1))
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before,1)
        target.record_note = note; target.apply = command; target.poll = one_poll
        try:
            with redirect_stdout(io.StringIO()) as output: host.check_live(wire)
            wire.sleep_ms(30)
            self.assertTrue(target.window.finished)
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations),(3,2,1,1))
            self.assertEqual((target.gate_commands,target.dac_mutes,target.line_mutes,target.restores,target.gates()),(4,1,1,2,0))
            self.assertEqual((target.jobs,target.writes,target.applied),(6,24,0))
            self.assertEqual((target.events,target.note_writes,target.partial_cancels),(20,40,0))
            self.assertEqual(list(target.run_masks),[57,15,15])
            for run,muted in ((0,2),(1,1)):
                trace = list(target.gate_notes[run*9:run*9+9])
                self.assertEqual(trace[0],3); self.assertEqual(trace[-1],3)
                self.assertGreaterEqual(trace.count(muted),2)
                self.assertTrue(all(v in (3,muted) for v in trace))
                for n in range(9): self.assertTrue(n*500 <= target.times[run*9+n] <= n*500+100)
            self.assertEqual(commands.count(host.queue.PLAY_FM),1); self.assertEqual(commands.count(host.queue.PLAY_SSG),2)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,len(commands)&255); self.assertIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_STOP_and_lease_while_DAC_or_LINE_muted_cancel_all_sources(self):
        for mute in (4,5):
            for stop in (True,False):
                model,module,host,target,board,wire,values = fixture()
                try:
                    remote = ready(host,wire); remote.command(host.queue.PLAY_FM,None)
                    wire.sleep_ms(300); remote.command(mute,1)
                    event = target.events
                    if stop: remote.command(0,0)
                    wire.sleep_ms(1600)
                    self.assertEqual((target.applied,target.gates(),target.state),(0,0,5))
                    self.assertEqual(target.expirations,int(not stop))
                    self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                    if stop: self.assertEqual(target.events,event)
                    else: self.assertGreater(target.events,event)
                    saved = target.events; wire.sleep_ms(1500); self.assertEqual(target.events,saved)
                finally: board.close(); target.close()

    def test_gate_commands_rejected_before_PLAY_during_ARM_and_after_DONE_without_side_effects(self):
        model,module,host,target,board,wire,values = fixture()
        def rejected():
            for command in (3,4,5):
                before = (target.gates(),target.window.data[0x10],target.gate_commands,len(model.writes))
                with self.assertRaisesRegex(RuntimeError,'requires active'): target.apply(command)
                self.assertEqual((target.gates(),target.window.data[0x10],target.gate_commands,len(model.writes)),before)
        try:
            rejected(); remote = ready(host,wire); remote.command(host.queue.PLAY_FM,None)
            self.assertEqual(target.state,1); rejected()
            with redirect_stdout(io.StringIO()): host.wait_run(wire,remote,0,57,4)
            self.assertEqual(target.state,4); rejected()
        finally: board.close(); target.close()

    def test_corrupt_gate_readback_fails_without_replay_and_lease_stops_all_voices(self):
        model,module,host,target,board,wire,values = fixture(); read = wire.readfrom
        def readfrom(address,count):
            data = read(address,count)
            return b'\x00' if count == 1 and target.window.pointer == 0x2A and target.mode else data
        wire.readfrom = readfrom
        try:
            with redirect_stdout(io.StringIO()) as output, self.assertRaisesRegex(RuntimeError,'gate readback'): host.check_live(wire)
            self.assertEqual(target.runs,1); self.assertNotIn('HOST PASS:',output.getvalue())
            wire.sleep_ms(1600); self.assertEqual((target.gates(),target.applied),(0,0))
            self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
        finally: board.close(); target.close()

    def test_mute_transfer_exceptions_not_retried_and_leased_cleanup(self):
        for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values = fixture(); write = wire.writeto; attempts = []
            def writeto(address,data,stop=True):
                if data == b'\x20\x04': attempts.append(data); raise fault('injected mute failure')
                return write(address,data,stop)
            wire.writeto = writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): host.check_live(wire)
                self.assertEqual(attempts,[b'\x20\x04']); self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1600); self.assertEqual((target.gates(),target.applied),(0,0))
            finally: board.close(); target.close()

    def test_ticks_wrap_old_wait_wrong_signature_and_silent_import(self):
        model = PolyModel()
        with redirect_stdout(io.StringIO()) as output: load(model)
        self.assertEqual(output.getvalue(),''); self.assertEqual(model.pins,{})
        model,module,host,target,board,wire,values = fixture()
        try:
            with patch.object(host.mixer.Remote,'ack_wait_ms',10), patch.object(host.queue.pitch.six.staged.startup,'check') as startup:
                with self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'): host.check(wire)
                startup.assert_not_called()
            target.window.data[:8] = b'RCQAC01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'signature mismatch'): host.check_live(wire)
            self.assertEqual(wire.command_writes,0); target.window.data[:8] = host.SIGNATURE
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
        finally: board.close(); target.close()

    def test_native_deadline_guard_and_cleanup_with_gate_command_during_stream(self):
        for slow in (False,True):
            model = PolyModel(); module,host,values = load(model)
            staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
            def listen(endpoint): endpoint.window.finished = True
            prepare = module.MutedQueueTarget.prepare; step = module.pitch.PitchBus.pitch_step
            def init(endpoint):
                prepare(endpoint)
                commands = ((8,40),(host.queue.CLEAR,40)) + tuple((0xA0+n,40) for n in host.queue.pitch.MELODY)
                commands += ((host.queue.PLAY_FM,40),(4,20),(3,20),(5,20),(3,20),(0,40),(7,0))
                regs.events = deque(e for c,wait in commands for e in command_events(c,wait))
            def write(bus,v,n,part):
                if model.stream and model.stream.running: model.us += 50000 if slow else 2300
                step(bus,v,n,part)
            with patch.object(startup,'listen',listen), patch.object(live,'Stream',lambda:ClockedPolyStream(model,guard)), patch.object(module.MutedQueueTarget,'prepare',init), patch.object(module.pitch.PitchBus,'pitch_step',write), redirect_stdout(io.StringIO()) as output:
                if slow:
                    with self.assertRaisesRegex(RuntimeError,'deadline'): module.run()
                else: module.run()
            self.assertIn('SAFE:',output.getvalue()); self.assertEqual('DONE:' in output.getvalue(),not slow)
            if not slow: self.assertEqual(model.stream.deadline_misses,0); self.assertIn('commands=4 dac_mutes=1 line_mutes=1 restores=2 gates=0',output.getvalue())
            model.assert_stopped()


if __name__ == '__main__': unittest.main()
