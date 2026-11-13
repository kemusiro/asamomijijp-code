# SPDX-License-Identifier: MIT
"""Melody rests preserve accompaniment and resume using one register per poll."""
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

from test_rev_c_i2c_queue_mute import load as load_muted
from test_rev_c_i2c_fm import command_events
from test_rev_c_i2c_fm_scheduling import SampledLink
from test_rev_c_i2c_six import ClockedPolyStream
from test_rev_c_six_voice_check import PolyModel

HERE = Path(__file__).resolve().parent


def load(model):
    muted_target, muted_host, values = load_muted(model)
    def source(name, modules):
        spec = importlib.util.spec_from_file_location(name,HERE/(name+'.py'))
        module = importlib.util.module_from_spec(spec)
        with patch.dict(sys.modules,modules): spec.loader.exec_module(module)
        return module
    target = source('rev_c_i2c_queue_rest_target',{'rev_c_i2c_queue_mute_target':muted_target})
    host = source('rev_c_i2c_queue_rest_host',{'rev_c_i2c_queue_mute_host':muted_host})
    target.gc = target.pitch.gc
    return target,host,values


def fixture():
    model = PolyModel(); module,host,values = load(model)
    board = module.pitch.PitchBus(); board.start(); board.prepare(); board.configure_three(); board.bass()
    for r in (8,9,10): board.checked(r,0)
    model.stream = types.SimpleNamespace(starts=2)
    target = module.RestQueueTarget(board); target.prepare(); target._enable(1)
    wire = SampledLink(model,target,values[-2],values[-3])
    clock = types.SimpleNamespace(sleep_ms=wire.sleep_ms,ticks_ms=model.ticks_ms,ticks_diff=model.ticks_diff)
    host.time = host.muted.time = host.muted.accomp.time = host.queue.time = host.mixer.time = host.mixer.shared.time = clock
    return model,module,host,target,board,wire,values


def ready(host,wire):
    with redirect_stdout(io.StringIO()):
        remote = host.mixer.shared.preflight(wire,signature=host.SIGNATURE,remote_factory=host.queue.Remote)
        remote.command(8,0); host.upload(wire,remote)
    return remote


def reach_rest(host,remote,target,wire):
    remote.command(host.queue.PLAY_FM,None)
    for unused in range(20):
        wire.sleep_ms(100); remote.command(6,None)
        if target.next_note == 3: return
    raise AssertionError('REST not reached')


class QueuedRestTests(unittest.TestCase):
    def test_full_HOST_all_slots_actual_keys_pitches_masks_companions_and_write_budget(self):
        model,module,host,target,board,wire,values = fixture()
        record = target.record_note; poll = target.poll; apply = target.apply; commands = []
        def command(c): commands.append(c); apply(c)
        def one_poll():
            before = len(model.writes); poll(); self.assertLessEqual(len(model.writes)-before,1)
        def slot(elapsed):
            record(elapsed)
            n = target.next_note-1; score = host.SCORE; rest = score[n] == module.REST
            mask = target.companions | (0 if rest else 1 << target.voice)
            self.assertEqual((target.applied,target.mask,target.window.data[0x14]),(mask,mask,mask))
            self.assertEqual((target.gates(),model.level(19),model.level(26)),(3,1,1))
            self.assertEqual(model.fm_keys,[bool(mask & (1 << i)) for i in range(3)])
            self.assertEqual(model.registers[8:11],[7 if mask & (1 << (i+3)) else 0 for i in range(3)])
            last = next(score[i] for i in range(n,-1,-1) if score[i] != module.REST)
            for v in range(6):
                index = last if v == target.voice else module.pitch.INITIAL[v]
                if v < 3: self.assertEqual((model.registers[0xA4+v],model.registers[0xA0+v]),module.control.live.PITCHES[index][1:])
                else: self.assertEqual(model.registers[2*(v-3)] | model.registers[2*(v-3)+1] << 8,module.pitch.SSG_PERIODS[index])
        target.record_note = slot; target.poll = one_poll; target.apply = command
        try:
            with redirect_stdout(io.StringIO()) as output: host.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
            self.assertEqual((target.runs,target.completed,target.aborted,target.expirations),(3,3,0,0))
            self.assertEqual((target.events,target.note_writes,target.partial_cancels),(27,36,0))
            self.assertEqual((target.tone_slots,target.rest_slots,target.rest_key_offs,target.resume_key_ons,target.pair_step),(18,9,9,9,0))
            self.assertEqual((target.jobs,target.writes,target.applied),(5,42,0))
            self.assertEqual(list(target.run_masks),[57,15,57]); self.assertEqual(list(target.played_score),list(host.SCORE)*3)
            self.assertEqual(list(target.gate_notes),[3]*27)
            for run,full,rest in ((0,57,56),(1,15,7),(2,57,56)):
                self.assertEqual(list(target.slot_masks[run*9:run*9+9]),[rest if n == 5 else full for n in host.SCORE])
                for n in range(9): self.assertTrue(500*n <= target.times[run*9+n] <= 500*n+100)
            self.assertEqual(commands.count(host.APPEND_REST),3); self.assertEqual(commands.count(host.queue.CLEAR),1)
            self.assertEqual(commands.count(8),1)
            final = int(re.search(r'EXPECTED TARGET FINAL ACK: (\d+)',output.getvalue())[1])
            self.assertEqual(final,len(commands)&255); self.assertIn('HOST PASS:',output.getvalue())
        finally: board.close(); target.close()
        model.assert_stopped()

    def test_STOP_or_lease_during_rest_cleans_companions_and_prevents_later_resume(self):
        for stopped in (True,False):
            model,module,host,target,board,wire,values = fixture()
            try:
                remote = ready(host,wire); reach_rest(host,remote,target,wire)
                self.assertEqual(target.applied,56)
                if stopped: remote.command(0,0)
                wire.sleep_ms(1600)
                self.assertEqual((target.state,target.applied,target.gates()),(5,0,0))
                self.assertEqual(target.expirations,int(not stopped))
                self.assertFalse(any(model.fm_keys)); self.assertEqual(model.registers[8:11],[0,0,0])
                events = target.events; wire.sleep_ms(4000); self.assertEqual(target.events,events)
            finally: board.close(); target.close()

    def test_cancel_pending_pitch_or_keyon_during_rest_resume(self):
        for step in (1,2):
            for stopped in (True,False):
                model,module,host,target,board,wire,values = fixture()
                try:
                    remote = ready(host,wire); reach_rest(host,remote,target,wire)
                    model.us = target.epoch*1000+1500000; wire.next_tick = model.us+11250
                    values[-2].values[module.control.link.IC_STATUS] = 0
                    for unused in range(step): target.poll()
                    self.assertEqual((target.pair_step,target.applied,target.resume_key_ons),(step,56,0))
                    if stopped: target.apply(0)
                    else:
                        model.us = (target.last_keep+1001)*1000; target.poll()
                    wire.next_tick = model.us+11250; wire.sleep_ms(300)
                    self.assertEqual((target.pair_step,target.applied,target.resume_key_ons,target.partial_cancels),(0,0,0,1))
                    self.assertEqual(target.state,5); self.assertFalse(any(model.fm_keys))
                finally: board.close(); target.close()

    def test_rest_upload_boundaries_and_first_last_rest_rejected(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            remote = ready(host,wire)
            with self.assertRaises(ValueError): target.apply(host.APPEND_REST)
            target.score[0] = module.REST
            with self.assertRaisesRegex(ValueError,'first and last'): target.apply(host.queue.PLAY_FM)
            target.score[0] = 0; target.score[-1] = module.REST
            with self.assertRaisesRegex(ValueError,'first and last'): target.apply(host.queue.PLAY_FM)
            target.score[-1] = 0; remote.command(host.queue.PLAY_FM,None)
            with self.assertRaisesRegex(RuntimeError,'fully stopped'): target.apply(host.APPEND_REST)
        finally: board.close(); target.close()

    def test_consecutive_rests_do_not_keyon_between_them(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            with patch.object(host,'SCORE',(0,5,5,2,0,5,1,2,0)):
                remote = ready(host,wire); remote.command(host.queue.PLAY_FM,None)
                with redirect_stdout(io.StringIO()): host.wait_run(wire,remote,0,57,1)
            self.assertEqual((target.rest_slots,target.rest_key_offs,target.resume_key_ons),(3,3,2))
            self.assertEqual((target.completed,target.writes),(1,13))
            self.assertEqual(list(target.slot_masks[:9]),[57,56,56,57,57,56,57,57,57])
        finally: board.close(); target.close()

    def test_overdue_resume_closes_outputs_without_catchup(self):
        model,module,host,target,board,wire,values = fixture()
        try:
            remote = ready(host,wire); reach_rest(host,remote,target,wire)
            model.us = target.epoch*1000+1650000; wire.next_tick = model.us+11250
            with self.assertRaisesRegex(RuntimeError,'late by more'): target.poll()
            self.assertEqual((target.gates(),target.state,target.resume_key_ons),(0,5,0))
            wire.sleep_ms(300); self.assertEqual(target.applied,0)
        finally: board.close(); target.close()

    def test_transfer_exception_propagates_and_lease_cleans_rest_or_tone(self):
        for fault in (OSError,RuntimeError,MemoryError,KeyboardInterrupt):
            model,module,host,target,board,wire,values = fixture(); write = wire.writeto; attempts = []
            def writeto(address,data,stop=True):
                if data == b'\x20\x06' and target.active():
                    attempts.append(data); raise fault('injected rest KEEP failure')
                return write(address,data,stop)
            wire.writeto = writeto
            try:
                with redirect_stdout(io.StringIO()) as output, self.assertRaises(fault): host.check_live(wire)
                self.assertEqual(attempts,[b'\x20\x06']); self.assertNotIn('HOST PASS:',output.getvalue())
                wire.sleep_ms(1600); self.assertEqual((target.gates(),target.applied),(0,0))
            finally: board.close(); target.close()

    def test_native_deadline_guard_and_SAFE_for_normal_slow_pitch_or_key_exception(self):
        for fault in (None,'slow','key'):
            model = PolyModel(); module,host,values = load(model)
            staged,oldhost,startup,startup_host,control,mixer,live,machine,transport,regs,guard = values
            prepare = module.RestQueueTarget.prepare; pitch_step = module.pitch.PitchBus.pitch_step; voice = module.pitch.PitchBus.voice
            def listen(endpoint): endpoint.window.finished = True
            def init(endpoint):
                prepare(endpoint)
                commands = ((8,40),(host.queue.CLEAR,40))+tuple((host.APPEND_REST if n == 5 else host.queue.APPEND+n,40) for n in host.SCORE)
                commands += ((host.queue.PLAY_FM,0),)+((6,40),)*14+((0,40),(7,0))
                regs.events = deque(e for c,wait in commands for e in command_events(c,wait))
            def write(bus,v,n,part):
                if model.stream and model.stream.running: model.us += 50000 if fault == 'slow' else 2300
                pitch_step(bus,v,n,part)
            def key(bus,v,enabled):
                if model.stream and model.stream.running:
                    if fault == 'key': raise MemoryError('injected key failure')
                    model.us += 2300
                voice(bus,v,enabled)
            with patch.object(startup,'listen',listen), patch.object(live,'Stream',lambda:ClockedPolyStream(model,guard)), patch.object(module.RestQueueTarget,'prepare',init), patch.object(module.pitch.PitchBus,'pitch_step',write), patch.object(module.pitch.PitchBus,'voice',key), redirect_stdout(io.StringIO()) as output:
                if fault:
                    with self.assertRaises(RuntimeError if fault == 'slow' else MemoryError): module.run()
                else: module.run()
            self.assertIn('SAFE:',output.getvalue()); self.assertEqual('DONE:' in output.getvalue(),fault is None)
            if fault is None:
                self.assertEqual(model.stream.deadline_misses,0)
                self.assertIn('tones=6 rests=3 rest_key_offs=3 resume_key_ons=3',output.getvalue())
            model.assert_stopped()

    def test_ticks_wrap_silent_import_wrong_signature_and_old_ACK_rejection(self):
        model = PolyModel()
        with redirect_stdout(io.StringIO()) as output: load(model)
        self.assertEqual(output.getvalue(),''); self.assertEqual(model.pins,{})
        model,module,host,target,board,wire,values = fixture()
        try:
            with patch.object(host.mixer.Remote,'ack_wait_ms',10), patch.object(host.queue.pitch.six.staged.startup,'check') as startup:
                with self.assertRaisesRegex(RuntimeError,'v1.3 FM HOST'): host.check(wire)
                startup.assert_not_called()
            target.window.data[:8] = b'RCQMT01!'
            with redirect_stdout(io.StringIO()), self.assertRaisesRegex(RuntimeError,'signature mismatch'): host.check_live(wire)
            self.assertEqual(wire.command_writes,0); target.window.data[:8] = host.SIGNATURE
            model.us = ((1 << 30)-1000)*1000; wire.next_tick = model.us+11250
            with redirect_stdout(io.StringIO()): host.check_live(wire)
            wire.sleep_ms(30); self.assertTrue(target.window.finished)
        finally: board.close(); target.close()


if __name__ == '__main__': unittest.main()
