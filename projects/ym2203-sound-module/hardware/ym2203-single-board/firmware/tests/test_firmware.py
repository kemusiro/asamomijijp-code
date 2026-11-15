# SPDX-License-Identifier: MIT
"""Protocol and host integration with independent clock/I2C/register model."""
import binascii
from collections import deque
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


def load(name,path):
    spec = importlib.util.spec_from_file_location(name,path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


fw = load('firmware_model',ROOT/'src/ym2203_fw.py')
host = load('firmware_host',ROOT/'host/ym2203_revc.py')


from unittest.mock import patch
import sys
with patch.dict(sys.modules,{'ym2203_fw':fw,'ym2203_revc':host}):
    fixture = load('micro_fixture',ROOT/'tests/micro_fixture.py')
Clock,Pin,Board,Wire = fixture.Clock,fixture.Pin,fixture.Board,fixture.Wire


def frame(seq,op,payload=b''):
    data = bytearray(16); data[:4] = bytes((1,seq,op,len(payload)))
    data[4:4+len(payload)] = payload
    crc = binascii.crc_hqx(data[:14],0); data[14:] = crc.to_bytes(2,'little')
    return data


def harness():
    clock = Clock(); board = Board(clock); engine = fw.Engine(board,clock)
    clock.service = lambda idle: engine.poll(idle)
    return clock,board,engine


def command(engine,op,payload=b''):
    data = frame((engine.seq+1)&255,op,payload); engine.accept(data); return data


def event(delay,r,v): return bytes((delay & 255,delay >> 8,r,v))


class FirmwareTests(unittest.TestCase):
    def test_crc_known_vector_and_independent_host_reference(self):
        self.assertEqual(host.crc16(b'123456789'),0x31C3)
        for seq in range(256):
            packet = frame(seq,fw.PUSH,event(500,0xA4,0x22))
            self.assertEqual(fw.crc16(packet),binascii.crc_hqx(packet[:14],0))
            self.assertEqual(host.crc16(packet[:14]),fw.crc16(packet))

    def test_window_requires_complete_frame_explicit_commit_and_latches_status(self):
        clock,board,engine = harness(); window = fw.Window(engine)
        packet = frame(1,fw.GATES,b'\x03')
        window.receive(0x40,True)
        for value in packet[:15]: window.receive(value)
        window.receive(0x50,True); window.receive(0xA5)
        self.assertFalse(window.pending); self.assertTrue(window.bad_frame)
        window.receive(0x40,True)
        for value in packet: window.receive(value)
        self.assertFalse(window.pending)
        window.receive(0x50,True); window.receive(0xA5)
        self.assertTrue(window.pending)
        snapshot = bytes(window.frame)
        window.receive(0x40,True); window.receive(99)
        self.assertEqual(bytes(window.frame),snapshot)
        window.receive(0x10,True); expected = bytes(engine.status)
        command(engine,fw.GATES,b'\x03')
        self.assertEqual(bytes(window.next_byte() for i in range(4)),expected)

    def test_bad_crc_version_padding_sequence_and_registers_have_no_side_effects(self):
        clock,board,engine = harness()
        packet = frame(1,fw.GATES,b'\x03'); packet[14] ^= 1
        engine.accept(packet); self.assertEqual(engine.result,fw.CRC_ERROR)
        self.assertEqual((engine.seq,engine.gates),(0,0))
        packet = frame(1,fw.GATES,b'\x03'); packet[0] = 2
        packet[14:] = binascii.crc_hqx(packet[:14],0).to_bytes(2,'little')
        engine.accept(packet); self.assertEqual(engine.result,fw.INVALID)
        packet = frame(2,fw.PING); packet[12] = 1
        packet[14:] = binascii.crc_hqx(packet[:14],0).to_bytes(2,'little')
        engine.accept(packet); self.assertEqual(engine.result,fw.INVALID)
        engine.accept(frame(9,fw.PING)); self.assertEqual(engine.result,fw.SEQUENCE)
        for r,v in ((0x2D,0),(0x0E,0),(0x27,0x80),(7,0xC0),(0x33,0),(0xA8,0),(0x28,3)):
            command(engine,fw.WRITE,bytes((r,v))); self.assertEqual(engine.result,fw.INVALID)
        self.assertEqual(board.calls,[]); self.assertEqual(engine.gates,0)

    def test_duplicate_frame_is_idempotent_but_does_not_renew_lease(self):
        clock,board,engine = harness()
        packet = command(engine,fw.PUSH,event(500,0xA0,1))
        engine.accept(packet); self.assertEqual(engine.queue.count,1)
        other = frame(engine.seq,fw.STOP); engine.accept(other)
        self.assertEqual(engine.result,fw.SEQUENCE)
        engine.accept(packet); self.assertEqual(engine.result,fw.OK)
        gate = command(engine,fw.GATES,b'\x03')
        clock.sleep_ms(900); engine.accept(gate); clock.sleep_ms(200)
        self.assertTrue(engine.expired); self.assertEqual(engine.gates,0)
        engine.accept(gate); self.assertEqual(engine.gates,0)

    def test_late_keep_cannot_revive_a_lease_between_poll_calls(self):
        clock,board,engine = harness(); command(engine,fw.GATES,b'\x03')
        clock.us += 1001000; command(engine,fw.KEEP)
        self.assertEqual(engine.result,fw.LEASE_ERROR); self.assertTrue(engine.expired)
        self.assertEqual((board.line_allow.level,board.dac_allow.level),(0,0))
        command(engine,fw.STOP); clock.next_tick = clock.us+11250; clock.sleep_ms(100)
        self.assertFalse(engine.expired); self.assertEqual(engine.result,fw.OK)

    def test_batch_validation_and_full_ring_are_atomic(self):
        clock,board,engine = harness()
        command(engine,fw.PUSH,event(1,0xA0,1)+event(1,0x2D,0))
        self.assertEqual((engine.queue.count,engine.result),(0,fw.INVALID))
        for i in range(64): command(engine,fw.PUSH,event(0,0xA0,1)+event(0,0xA0,2))
        self.assertEqual(engine.queue.count,128)
        command(engine,fw.PUSH,event(1,0xA0,3)); self.assertEqual(engine.result,fw.FULL)
        self.assertEqual(engine.queue.count,128)
        command(engine,fw.WRITE,b'\xA0\x01\x2D\x00')
        self.assertEqual(engine.result,fw.INVALID); self.assertEqual(board.calls,[])

    def test_ordered_writes_one_per_poll_and_explicit_STOP_preempts_them(self):
        clock,board,engine = harness()
        command(engine,fw.WRITE,b'\xA0\x01\xA1\x02\xA2\x03')
        engine.poll(); self.assertEqual([x[1:] for x in board.calls],[(0xA0,1)])
        command(engine,fw.STOP); self.assertEqual(engine.gates,0)
        clock.sleep_ms(100)
        self.assertNotIn((0xA1,2),[x[1:] for x in board.calls])
        self.assertEqual([x[1:] for x in board.calls][-6:],list(zip(fw.OFF_REG,fw.OFF_VAL)))

    def test_lease_cleanup_while_muted_and_explicit_recovery(self):
        for gates in (0,1,2,3):
            clock,board,engine = harness(); command(engine,fw.GATES,bytes((gates,)))
            command(engine,fw.WRITE,b'\x28\x10\x08\x07'); clock.sleep_ms(80)
            clock.sleep_ms(1100)
            self.assertEqual(engine.gates,0); self.assertTrue(engine.expired)
            self.assertEqual(board.regs[8:11],b'\0\0\0')
            self.assertEqual(board.regs[0x28],2)
            command(engine,fw.GATES,b'\x03'); self.assertEqual(engine.result,fw.LEASE_ERROR)
            command(engine,fw.STOP); clock.sleep_ms(100)
            command(engine,fw.GATES,b'\x03'); self.assertEqual(engine.gates,3)

    def test_sealed_queue_absolute_times_normal_end_and_residual_sound_cleanup(self):
        clock,board,engine = harness()
        command(engine,fw.PUSH,event(0,0x28,0x10)+event(500,0x28,0))
        command(engine,fw.SEAL); command(engine,fw.PLAY); clock.sleep_ms(160)
        start = next(x[0] for x in board.calls if x[1:] == (0x28,0x10))
        for unused in range(4): command(engine,fw.KEEP); clock.sleep_ms(200)
        off = next(x[0] for x in board.calls if x[1:] == (0x28,0) and x[0] > start)
        self.assertTrue(500000 <= off-start <= 600000)
        self.assertEqual((engine.active,engine.running,engine.gates),(False,False,0))
        self.assertEqual(board.regs[8:11],b'\0\0\0')

    def test_unsealed_queue_can_refill_after_empty_without_restart(self):
        clock,board,engine = harness()
        command(engine,fw.PUSH,event(0,0x28,0x10)); command(engine,fw.PLAY)
        clock.sleep_ms(200); self.assertEqual(engine.queue.count,0); self.assertTrue(engine.running)
        command(engine,fw.PUSH,event(500,0x28,0)); command(engine,fw.SEAL)
        command(engine,fw.KEEP); clock.sleep_ms(900)
        self.assertFalse(engine.failed); self.assertEqual(engine.gates,0)

    def test_late_queue_or_nonblocking_BUSY_timeout_mutes_and_faults(self):
        clock,board,engine = harness(); command(engine,fw.PUSH,event(0,0x28,0x10)); command(engine,fw.PLAY)
        clock.sleep_ms(160); command(engine,fw.PUSH,event(0,0xA0,1))
        clock.us += 200000; engine.poll(); self.assertTrue(engine.failed); self.assertEqual(engine.gates,0)
        clock,board,engine = harness(); board.blocked = True
        command(engine,fw.WRITE,b'\xA0\x01'); clock.sleep_ms(150)
        self.assertTrue(engine.failed); self.assertEqual(engine.result,fw.IO_ERROR)

    def test_counter_wrap_and_modular_queue_timing_over_24h_of_virtual_timeline(self):
        clock,board,engine = harness()
        clock.us = ((1 << 30)-100)*1000; clock.next_tick = clock.us+11250
        command(engine,fw.PUSH,event(0,0xA0,1)+event(500,0xA0,2)); command(engine,fw.PLAY)
        clock.sleep_ms(160); command(engine,fw.KEEP); clock.sleep_ms(600)
        self.assertEqual([x[2] for x in board.calls if x[1] == 0xA0],[1,2])
        # Daily timeline checkpoints exercise wrap arithmetic without claiming
        # a24h real-time audio/USB endurance run.
        for hour in range(25):
            clock.us = hour*3600000000; clock.next_tick = clock.us+11250
            engine.active = False; engine.job = fw.IDLE; engine.queue.clear(); engine.running = False
            engine.expired = engine.failed = False
            command(engine,fw.GATES,b'\x03'); clock.sleep_ms(500); command(engine,fw.KEEP)
            self.assertFalse(engine.expired)

    def test_driver_real_frames_stream_over_ring_capacity_and_sequence_wrap(self):
        wire = Wire(); client = wire.client(); client.pure_fm(); client.ssg_bass()
        def events():
            for i in range(300):
                yield 200,0xA0,i & 255
        client.stream(events())
        actual = [v for t,r,v in wire.board.calls if r == 0xA0]
        self.assertEqual(actual,list(range(256))+list(range(44)))
        self.assertFalse(wire.engine.active); self.assertEqual(wire.engine.queue.count,0)
        self.assertEqual(wire.engine.gates,0); self.assertEqual(wire.engine.expirations,0)
        self.assertFalse(wire.engine.failed)
        self.assertGreater(sum(d.startswith(b'\x40') for d in wire.transfers),150)
        seqs = [d[2] for d in wire.transfers if d.startswith(b'\x40')]
        self.assertIn((255,0),list(zip(seqs,seqs[1:])))

    def test_host_demo_runs_against_actual_engine_and_all_sound_stops(self):
        wire = Wire(); client = wire.client(); client.pure_fm(); client.ssg_bass()
        import sys,types
        from unittest.mock import patch
        with patch.dict(sys.modules,{'machine':types.SimpleNamespace(Pin=object,I2C=object),'ym2203_revc':host}):
            demo = load('firmware_demo',ROOT/'host/example.py')
        client.stream(demo.events(2))
        self.assertFalse(wire.engine.failed)
        self.assertEqual(wire.engine.gates,0); self.assertEqual(wire.board.regs[8:11],b'\0\0\0')

    def test_demo_with_I2C_stretch_and_YM_write_cost_preserves_due_events(self):
        # Wire's original nominal-byte-only timing hid this starvation bug.
        # These are modelled costs,not measured physical timing guarantees.
        import sys,types
        from unittest.mock import patch
        with patch.dict(sys.modules,{'machine':types.SimpleNamespace(Pin=object,I2C=object),'ym2203_revc':host}):
            demo = load('firmware_demo_stretched',ROOT/'host/example.py')
        for stretch_us in (5000,10000,20000,30000):
            with self.subTest(stretch_us=stretch_us):
                class StretchedWire(Wire):
                    def service(self,idle):
                        before = len(self.board.calls)
                        super().service(idle)
                        # Account for the split register write's CPU work.
                        if len(self.board.calls) != before: self.clock.us += 4400
                    def writeto(self,address,data):
                        self.clock.advance(stretch_us,False)
                        return super().writeto(address,data)
                    def readfrom(self,address,count):
                        self.clock.advance(stretch_us,False)
                        return super().readfrom(address,count)
                wire = StretchedWire();client = wire.client()
                client.pure_fm();client.ssg_bass()
                expected = list(demo.events(2))
                offset = len(wire.board.calls)
                client.stream(iter(expected))
                applied = [(reg,value) for unused,reg,value in wire.board.calls[offset:]]
                # STOP before streaming and six-source cleanup afterwards are
                # separate from the event log; compare the exact middle score.
                self.assertEqual(applied[6:6+len(expected)],[(r,v) for d,r,v in expected])
                self.assertEqual(wire.engine.executed,len(expected))
                self.assertLessEqual(wire.engine.max_late,fw.LATE_MS)
                self.assertFalse(wire.engine.failed)
                self.assertEqual((wire.engine.expirations,wire.engine.gates),(0,0))

    def test_committed_queue_progresses_during_external_I2C_without_extra_write_budget(self):
        clock,board,engine = harness()
        for i in range(6): command(engine,fw.PUSH,event(0,0xA0,i))
        command(engine,fw.PLAY);clock.sleep_ms(160)
        # The PLAY handshake has completed;part of the initial group remains.
        # Keep the external bus active while the already committed group drains.
        offset = len(board.calls)
        self.assertLess(offset,6)
        for unused in range(6):
            clock.us += 11250
            before = len(board.calls)
            engine.poll(False)
            self.assertLessEqual(len(board.calls)-before,1)
        self.assertEqual([v for t,r,v in board.calls[offset:]],list(range(offset,6)))
        self.assertEqual(engine.queue.count,0)
        self.assertFalse(engine.failed)

    def test_busy_external_I2C_still_honors_STOP_lease_and_genuine_lateness(self):
        clock,board,engine = harness()
        command(engine,fw.GATES,b'\x03')
        command(engine,fw.WRITE,b'\xA0\x01\xA1\x02\xA2\x03')
        engine.poll(False)
        command(engine,fw.STOP)
        self.assertEqual(engine.gates,0)
        for unused in range(6): engine.poll(False)
        self.assertEqual(engine.result,fw.OK)
        self.assertNotIn((0xA1,2),[x[1:] for x in board.calls])
        self.assertEqual([x[1:] for x in board.calls][-6:],list(zip(fw.OFF_REG,fw.OFF_VAL)))
        clock,board,engine = harness();command(engine,fw.GATES,b'\x03')
        clock.us += 1001000;engine.poll(False)
        self.assertTrue(engine.expired);self.assertEqual(engine.gates,0)
        clock,board,engine = harness()
        command(engine,fw.PUSH,event(0,0x28,0x10));command(engine,fw.PLAY)
        clock.sleep_ms(160);command(engine,fw.PUSH,event(0,0xA0,1))
        clock.us += 200000;engine.poll(False)
        self.assertTrue(engine.failed);self.assertEqual(engine.result,fw.LATE)
        self.assertEqual(engine.gates,0)

    def test_driver_does_not_retry_failed_write_and_explicit_stop_resynchronizes(self):
        wire = Wire(); client = wire.client(); failures = []
        def fail(data):
            if data.startswith(b'\x40'):
                failures.append(bytes(data)); return True
        wire.fail = fail
        with self.assertRaises(OSError): client.gates()
        self.assertEqual(len(failures),1)
        wire.fail = None; client.stop(); self.assertEqual(wire.engine.gates,0)

    def test_wrong_identity_rejected_without_command_or_audio(self):
        wire = Wire(); wire.window.data[0] = 0
        with self.assertRaises(host.ProtocolError): wire.client()
        self.assertFalse(any(d.startswith(b'\x40') for d in wire.transfers))
        self.assertEqual(wire.engine.gates,0)


if __name__ == '__main__': unittest.main()
