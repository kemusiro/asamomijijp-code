# SPDX-License-Identifier: MIT
"""Actual RTL + unchanged RevCStream, with explicit model time and YM writer."""
import binascii
import ctypes as C
import importlib.util
import os
from pathlib import Path
import random
import struct
import tempfile
import unittest

PROJECT = Path(os.environ.get('F1_PROJECT', Path(__file__).resolve().parents[2]))


def packet(op, seq, payload=b''):
    data = struct.pack('<2sBBIH2x', b'Y2', 2, op, seq, len(payload)) + payload
    return data + struct.pack('<I', binascii.crc32(data) & 0xffffffff)


def score(n=12, step=10, period=None):
    period = period or n * step + 200
    records = b''.join(struct.pack('<IBB', i * step, 0, i & 255) for i in range(n))
    return struct.pack('<4sIII', b'WYM1', n, period, 4000000) + records


class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = C.CDLL(os.environ['F1_SESSION_LIB'])
        cls.r.rtl_command.argtypes = cls.r.rtl_send.argtypes = [C.c_void_p, C.c_uint]
        cls.r.rtl_status.argtypes = [C.c_void_p]
        cls.r.rtl_clock.argtypes = cls.r.rtl_advance.argtypes = [C.c_uint64]
        cls.r.rtl_now.restype = C.c_uint64
        cls.r.rtl_trace.restype = C.c_void_p
        cls.c = C.CDLL(os.environ['F1_C_ORACLE_LIB'])
        cls.c.model_command.argtypes = [C.c_void_p, C.c_uint]
        cls.c.model_status.argtypes = [C.c_void_p]
        cls.c.model_advance.argtypes = cls.c.model_clock.argtypes = [C.c_uint64]
        cls.c.model_trace.restype = C.c_void_p
        spec = importlib.util.spec_from_file_location('f1_unchanged_host', PROJECT / 'firmware-c/host/lib/ym2203_revc_stream.py')
        cls.host = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.host)

    @classmethod
    def tearDownClass(cls):
        cls.r.rtl_destroy()

    def setUp(self):
        self.r.rtl_init(50)
        self.c.model_init(50)

    def status(self):
        out = C.create_string_buffer(64)
        self.assertEqual(self.r.rtl_status(out), 0)
        data = out.raw
        self.assertEqual(data[:9], b'YM22S002\x02')
        self.assertEqual(binascii.crc32(data[:60]) & 0xffffffff, struct.unpack_from('<I', data, 60)[0])
        self.assertEqual(sum(struct.unpack_from('<HH', data, 36)), 1024)
        return data

    def c_status(self):
        out = C.create_string_buffer(64)
        self.c.model_status(out)
        return out.raw

    def command(self, op, seq, payload=b'', compare=False):
        raw = packet(op, seq, payload)
        self.assertEqual(self.r.rtl_command(raw, len(raw)), 0)
        if compare:
            self.c.model_command(raw, len(raw))
        data = self.status()
        if compare:
            other = self.c_status()
            # Timing maxima/generation are implementation-dependent. All wire
            # state/ACK/counts/CRC/elapsed and stop reasons must agree.
            self.assertEqual(data[:48], other[:48])
            self.assertEqual(data[52:56], other[52:56])
        return data

    def begin(self, data, seq=0, compare=False):
        return self.command(2, seq, data[:16] + struct.pack('<I', binascii.crc32(data) & 0xffffffff), compare)

    def load(self, data, compare=False):
        self.assertEqual(self.begin(data, compare=compare)[10], 0)
        seq = 1
        for start in range(16, len(data), 192):
            self.assertEqual(self.command(3, seq, data[start:start+192], compare)[10], 0)
            seq += 1
        return seq

    def advance(self, us, both=False):
        self.r.rtl_advance(us)
        if both:
            self.c.model_advance(us)

    def trace(self):
        return C.string_at(self.r.rtl_trace(), 2 * self.r.rtl_trace_count())

    def test_initial_status_snapshot_is_pinned(self):
        first = self.status()
        self.advance(4000000)
        self.assertEqual(bytes(self.r.rtl_status_byte(i) for i in range(64)), first)
        self.assertEqual(self.r.rtl_status_byte(64), 255)
        self.assertEqual(self.r.rtl_status_byte(255), 255)
        self.assertNotEqual(first[56:60], self.status()[56:60])

    def test_complete_score_matches_c_state_crc_and_order(self):
        data = score(40)
        seq = self.load(data, True)
        self.command(4, seq, compare=True)
        self.command(6, seq+1, compare=True)
        self.advance(900000, True)
        actual, expected = self.status(), self.c_status()
        self.assertEqual(actual[:48], expected[:48])
        self.assertEqual(actual[9], 3)
        self.assertEqual(self.trace(), C.string_at(self.c.model_trace(), 2*self.c.model_trace_count()))
        self.assertEqual(self.trace(), b''.join(data[i+4:i+6] for i in range(16,len(data),6)))
        self.assertEqual(self.r.rtl_gate(), 0)

    def test_every_command_shape_sequence_and_crc_precedence(self):
        cases = [(0,b'x'),(1,b'x'),(2,b''),(3,b''),(3,b'1'),(4,b''),(5,b''),(6,b''),(255,b'')]
        for op, payload in cases:
            with self.subTest(op=op,payload=payload):
                self.command(op, 0, payload, True)
        good = packet(0, 0)
        for raw in [good[:-1], good+b'0', good[:10]+b'x'+good[11:], good[:-1]+bytes([good[-1]^1]), bytes(209)]:
            self.assertEqual(self.r.rtl_command(raw,len(raw)),0)
            self.c.model_command(raw,len(raw))
            self.assertEqual(self.status()[:48],self.c_status()[:48])
        self.command(0,123,compare=True)
        self.command(1,0xfffffffe,compare=True)
        self.command(0,0xffffffff,compare=True)
        self.command(0,0,compare=True)
        self.assertEqual(struct.unpack_from('<I',self.status(),16)[0],1)

    def test_begin_validation_and_refused_preparation(self):
        for count,period,clock in [(0,10,4000000),(131072,10,4000000),(1,0,4000000),(1,10,3579545)]:
            payload = struct.pack('<4sIIII',b'WYM1',count,period,clock,0)
            self.assertEqual(self.command(2,0,payload,True)[10],6)
        self.assertEqual(self.command(2,0,b'bad!'+bytes(16),True)[10],2)
        self.r.rtl_controls(1,1,0,1,0,1)
        self.assertEqual(self.begin(score())[10],4)
        self.assertEqual(self.r.rtl_prepare_count(),0)
        self.r.rtl_controls(1,0,0,1,4,1)
        self.assertEqual(self.begin(score())[10],4)
        self.r.rtl_controls(1,0,0,1,12,1)
        s=self.begin(score())
        self.assertEqual(s[9:11],bytes([5,12]));self.assertEqual(s[44],12)
        self.assertEqual(struct.unpack_from('<I',s,16)[0],0)
        self.command(1,0)
        self.r.rtl_controls(1,0,0,1,0,1)
        self.assertEqual(self.begin(score(),1)[10],0)

    def test_atomic_invalid_batch_and_register_masks(self):
        self.begin(score(1024,step=1))
        cases=[[(1,0,5),(0,0,6)],[(0,0,5),(2000,0,6)],[(0,0,5),(1,0x2d,0)],
               [(0,1,16)],[(0,6,32)],[(0,7,64)],[(0,8,32)],[(0,0x28,3)],
               [(0,0x28,4)],[(0,0x33,0)],[(0,0x50,32)],[(0,0x60,32)],
               [(0,0x70,32)],[(0,0x90,16)],[(0,0xa4,64)],[(0,0xb0,64)]]
        for events in cases:
            p=b''.join(struct.pack('<IBB',*e) for e in events)
            s=self.command(3,1,p)
            self.assertEqual(s[10],6)
            self.assertEqual(s[20:28],bytes(8));self.assertEqual(self.r.rtl_queued(),0)
        good=[(0,0,255),(1,1,15),(2,6,31),(3,7,63),(4,8,31),(5,0x24,255),
              (6,0x25,3),(7,0x26,255),(8,0x27,63),(9,0x28,0xf2),(10,0x50,223),
              (11,0x60,159),(12,0x80,255),(13,0x9e,15),(14,0xa0,255),(15,0xa6,63),(16,0xb2,63)]
        s=self.command(3,1,b''.join(struct.pack('<IBB',*e) for e in good))
        self.assertEqual(s[10],0);self.assertEqual(self.r.rtl_queued(),len(good))

    def test_queue_full_rejection_keeps_batch_atomic(self):
        data=score(1100,step=1)
        self.begin(data)
        for i in range(32):self.assertEqual(self.command(3,i+1,data[16+i*192:16+(i+1)*192])[10],0)
        before=self.status()
        self.assertEqual(self.command(3,33,data[6160:6166])[10],5)
        after=self.status()
        self.assertEqual(after[20:40],before[20:40]);self.assertEqual(after[52:56],before[52:56])
        self.assertEqual(self.command(4,33)[10],0)
        self.advance(350000)
        self.assertLess(self.r.rtl_queued(),1024)
        self.assertEqual(self.command(3,34,data[6160:6352])[10],0)

    def test_duplicate_push_play_keep_and_begin_do_not_reexecute_or_extend_lease(self):
        data=score(2,step=100)
        self.begin(data);self.begin(data)
        self.assertEqual(self.r.rtl_prepare_count(),1)
        self.command(3,1,data[16:]);self.command(3,1,data[16:])
        self.assertEqual(self.r.rtl_queued(),2)
        self.command(4,2);self.advance(300000)
        self.command(4,2)
        self.advance(100000)
        self.assertEqual(self.r.rtl_trace_count(),2)
        self.command(5,3);self.advance(999980)
        self.command(5,3)
        self.advance(20)
        s=self.status();self.assertEqual(s[9],5);self.assertEqual(s[44],8)
        self.assertEqual(self.r.rtl_gate(),0)

    def test_same_sequence_different_bytes_is_rejected_even_for_stop(self):
        self.command(0,0,compare=True)
        self.assertEqual(self.command(1,0,compare=True)[10],3)
        self.assertEqual(self.command(1,5,compare=True)[10],0)

    def test_stop_clears_queue_progress_freezes_and_requires_begin(self):
        data=score(20,step=50)
        seq=self.load(data);self.command(4,seq)
        self.advance(450000)
        before=self.r.rtl_trace_count();self.assertGreater(before,0)
        self.command(1,seq+1);self.advance(4000000)
        self.assertEqual(self.r.rtl_trace_count(),before);self.assertEqual(self.r.rtl_queued(),0)
        self.assertEqual(self.command(4,seq+2)[10],4)
        self.assertEqual(self.command(5,seq+2)[10],4)
        self.assertEqual(self.r.rtl_gate(),0)

    def test_lease_exact_deadline_precedes_keep_and_read_does_not_renew(self):
        self.begin(score(),compare=True)
        self.advance(999980,True);self.status()
        self.advance(20,True)
        self.assertEqual(self.command(5,1,compare=True)[10],4)
        self.assertEqual(self.status()[44],8)
        self.command(1,1,compare=True)
        self.begin(score(),2,True)

    def test_queue_starvation_and_seal_integrity_stop_without_skipping(self):
        data=score(600,step=1)
        self.begin(data)
        for i in range(16):self.command(3,i+1,data[16+i*192:16+(i+1)*192])
        self.command(4,17);self.advance(900000)
        self.assertEqual(self.status()[44],9)
        self.assertEqual(self.r.rtl_trace_count(),512)
        self.command(1,18)
        self.begin(score(1),19)
        self.command(3,20,struct.pack('<IBB',0,0,99))
        s=self.command(6,21)
        self.assertEqual(s[9:11],bytes([5,11]));self.assertEqual(s[44],11)
        self.assertEqual(self.r.rtl_queued(),0)

    def test_busy_late_and_writer_fault_stop_without_consuming_event(self):
        seq=self.load(score(1));self.command(4,seq)
        self.r.rtl_clock(350001);self.r.rtl_cycles(4)
        self.assertEqual(self.status()[44],10);self.assertEqual(self.r.rtl_trace_count(),0)
        self.setUp();seq=self.load(score(1));self.command(4,seq)
        self.r.rtl_controls(1,0,1,1,0,1);self.advance(250000)
        self.assertEqual(self.status()[44],7);self.assertEqual(self.r.rtl_trace_count(),0)

    def test_late_boundary_is_checked_at_current_time_before_writer_acceptance(self):
        # First event blocks the writer until 1us beyond event2's 100ms limit.
        # A cached relative "now" would incorrectly accept event2 on that edge.
        self.r.rtl_init(101001)
        seq=self.load(score(2,step=1));self.command(4,seq);self.command(6,seq+1)
        self.r.rtl_clock(250000);self.r.rtl_cycles(20)
        self.assertEqual(self.r.rtl_trace_count(),1)
        self.r.rtl_clock(350999);self.r.rtl_cycles(8)
        self.assertEqual(self.r.rtl_trace_count(),1)
        self.r.rtl_clock(351001);self.r.rtl_cycles(1)
        self.assertEqual(self.r.rtl_trace_count(),1)
        self.assertEqual(self.status()[44],10)
        self.assertEqual(self.r.rtl_gate(),0)

    def test_unsealed_full_received_waits_for_seal_and_period(self):
        seq=self.load(score(1,period=500));self.command(4,seq)
        self.advance(800000)
        self.assertEqual(self.status()[9],2)
        self.command(6,seq+1);self.r.rtl_cycles(8)
        self.assertEqual(self.status()[9],3);self.assertEqual(self.r.rtl_gate(),0)

    def test_interrupted_staged_batch_never_publishes_and_cache_survives(self):
        data=score(32)
        self.begin(data)
        raw=packet(3,1,data[16:])
        self.assertEqual(self.r.rtl_send(raw,len(raw)),0)
        self.r.rtl_cycles(260)
        self.r.rtl_clock(1000000);self.r.rtl_cycles(8)
        s=self.status()
        self.assertEqual(s[9],5);self.assertEqual(self.r.rtl_queued(),0)
        self.assertEqual(struct.unpack_from('<I',s,20)[0],0)
        self.assertEqual(struct.unpack_from('<I',s,16)[0],1)
        self.assertEqual(self.begin(data)[10],0) # prior successful BEGIN is still cached
        self.assertEqual(self.status()[9],5);self.assertEqual(self.r.rtl_prepare_count(),1)

    def test_global_stop_audio_failure_transport_abort_and_overflow(self):
        for action in ['global','audio','transport','abort']:
            with self.subTest(action=action):
                self.r.rtl_init(50);seq=self.load(score());self.command(4,seq)
                if action=='global':self.r.rtl_global_stop()
                elif action=='audio':self.r.rtl_controls(0,0,0,1,0,1);self.r.rtl_cycles(8)
                elif action=='transport':self.r.rtl_transport_error()
                else:self.r.rtl_abort();self.assertEqual(self.r.rtl_finish(),0)
                self.r.rtl_cycles(8)
                self.assertEqual(self.r.rtl_gate(),0);self.assertEqual(self.r.rtl_queued(),0)
                self.assertEqual(self.status()[44],{'global':0,'audio':12,'transport':7,'abort':7}[action])

    def test_global_stop_discards_partially_validated_batch_before_ack(self):
        data=score(32);self.begin(data)
        raw=packet(3,1,data[16:]);self.assertEqual(self.r.rtl_send(raw,len(raw)),0)
        self.r.rtl_cycles(120);self.r.rtl_global_stop();self.r.rtl_cycles(8)
        s=self.status();self.assertEqual(s[9],4);self.assertEqual(self.r.rtl_queued(),0)
        self.assertEqual(struct.unpack_from('<I',s,20)[0],0)
        self.assertEqual(struct.unpack_from('<I',s,16)[0],1)
        self.assertEqual(self.begin(data,1)[10],0)
        self.assertEqual(self.command(3,2,data[16:])[10],0)
        self.assertEqual(self.r.rtl_queued(),32)

    def test_prepare_and_silence_deadlines_are_bounded(self):
        self.r.rtl_controls(1,0,0,0,0,1)
        data=score();raw=packet(2,0,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.assertEqual(self.r.rtl_send(raw,len(raw)),0);self.r.rtl_cycles(100)
        self.r.rtl_clock(100000);self.r.rtl_cycles(8)
        self.assertEqual(self.status()[44],12)
        self.r.rtl_init(50);self.r.rtl_controls(1,0,0,1,0,0)
        raw=packet(1,0);self.assertEqual(self.r.rtl_send(raw,len(raw)),0);self.r.rtl_cycles(50)
        self.assertEqual(self.r.rtl_gate(),0)
        self.r.rtl_clock(100000);self.r.rtl_cycles(8)
        self.assertEqual(self.status()[44],7)

    def test_prepare_can_temporarily_drop_audio_health_until_reprime(self):
        self.r.rtl_controls(1,0,0,0,0,1)
        data=score();raw=packet(2,0,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.assertEqual(self.r.rtl_send(raw,len(raw)),0);self.r.rtl_cycles(100)
        self.r.rtl_controls(0,0,0,0,0,1)
        self.advance(10000)
        self.r.rtl_controls(1,0,0,1,0,1)
        self.assertEqual(self.r.rtl_finish(),0)
        s=self.status();self.assertEqual(s[9],1);self.assertEqual(s[10],0);self.assertEqual(s[44],0)

    def test_64bit_time_crosses_uint32_microseconds_and_snapshot_division(self):
        start=0xffffff00
        self.r.rtl_clock(start);self.c.model_clock(start)
        data=score(2);seq=self.load(data,True);self.command(4,seq,compare=True);self.command(6,seq+1,compare=True)
        self.advance(900000,True)
        self.assertEqual(self.status()[:48],self.c_status()[:48])
        self.command(1,seq+2,compare=True)
        target=(1<<32)*1000+123456789
        self.r.rtl_clock(target);self.c.model_clock(target)
        self.assertEqual(self.status()[40:44],self.c_status()[40:44])

    def run_host(self,data,hide_ack=False,stall=0):
        r,host=self.r,self.host
        trace_start=2*r.rtl_trace_count()
        class Clock:
            @staticmethod
            def ticks_ms():return (r.rtl_now()//1000)&((1<<30)-1)
            @staticmethod
            def ticks_diff(a,b):return ((a-b+(1<<29))&((1<<30)-1))-(1<<29)
            @staticmethod
            def sleep_ms(ms):r.rtl_advance(ms*1000)
        class Bus:
            reads=0
            hidden=None
            hidden_until=0
            did_hide=False
            def writeto(self,address,p):
                self.assert_address(address)
                prior=C.create_string_buffer(64);assert r.rtl_status(prior)==0
                r.rtl_advance((len(p)+1)*9*1000000//100000)
                assert r.rtl_command(bytes(p),len(p))==0
                if hide_ack and p[3]==3 and not self.did_hide:
                    self.hidden=prior.raw;self.hidden_until=r.rtl_now()+550000;self.did_hide=True
                return len(p)
            @staticmethod
            def assert_address(address):assert address==0x42
            def readfrom(self,address,n):
                self.assert_address(address);assert n==64
                out=C.create_string_buffer(64);assert r.rtl_status(out)==0
                r.rtl_advance((n+1)*9*1000000//100000);self.reads+=1
                if stall and self.reads==100:r.rtl_advance(stall)
                return self.hidden if self.hidden is not None and r.rtl_now()<self.hidden_until else out.raw
        previous=host.time;host.time=Clock
        try:
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'original-synthetic.bin';path.write_bytes(data)
                player=host.RevCStream(Bus());result=player.play_file(str(path))
            self.assertEqual(result['executed'],(len(data)-16)//6)
            self.assertEqual(result['state'],3)
            self.assertEqual(self.trace()[trace_start:],b''.join(data[i+4:i+6] for i in range(16,len(data),6)))
            self.assertEqual(self.r.rtl_gate(),0)
            return result,player
        finally:host.time=previous

    def test_unchanged_host_play_file_refills_and_wraps_fifo(self):
        self.run_host(score(4096,step=2))

    def test_unchanged_host_identical_retry_does_not_duplicate_events(self):
        _,player=self.run_host(score(1100,step=5),hide_ack=True)
        self.assertGreaterEqual(player.retries,1)

    def test_unchanged_host_disconnect_lease_cleanup_and_explicit_restart(self):
        with self.assertRaises(self.host.ProtocolError):self.run_host(score(1100,step=5),stall=1800000)
        self.assertEqual(self.r.rtl_gate(),0)
        self.assertEqual(self.r.rtl_queued(),0)
        self.run_host(score(9,step=100))

    def test_random_rejected_batches_match_c_without_partial_publication(self):
        rng=random.Random(2203)
        data=score(1024,step=1);self.begin(data,compare=True)
        for _ in range(160):
            entries=[(rng.randrange(3000),rng.randrange(256),rng.randrange(256)) for _ in range(rng.randrange(1,8))]
            payload=b''.join(struct.pack('<IBB',*e) for e in entries)
            s=self.status();seq=struct.unpack_from('<I',s,16)[0]
            self.command(3,seq,payload,True)

    @unittest.skipUnless(os.environ.get('F1_PRIVATE_SCORE'),'private score not requested')
    def test_private_score_with_unchanged_host(self):
        data=Path(os.environ['F1_PRIVATE_SCORE']).read_bytes()
        result,player=self.run_host(data)
        self.assertEqual(result['crc32'],binascii.crc32(data)&0xffffffff)
        self.assertEqual(player.retries,0)


if __name__=='__main__':unittest.main()
