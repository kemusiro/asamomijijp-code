# SPDX-License-Identifier: MIT
"""Real C protocol/scheduler + actual host library with modelled bus and time."""
import binascii
import ctypes as C
import importlib.util
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]

def packet(op,seq,payload=b''):
    data=struct.pack('<2sBBIH2x',b'Y2',2,op,seq,len(payload))+payload
    return data+struct.pack('<I',binascii.crc32(data)&0xffffffff)

def score(n=12):
    return struct.pack('<4sIII',b'WYM1',n,n*100+200,4000000)+b''.join(struct.pack('<IBB',i*100,0,i&255) for i in range(n))

class StreamTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='revc-stream-');lib=Path(cls.temp.name)/'stream.so'
        subprocess.run([shutil.which('cc'),'-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(ROOT/'src'),str(ROOT/'src/wym1.c'),str(ROOT/'src/stream.c'),str(ROOT/'src/transport.c'),str(ROOT/'tests/stream_bridge.c'),'-o',str(lib)],check=True)
        cls.c=C.CDLL(str(lib));cls.c.model_advance.argtypes=[C.c_uint64];cls.c.model_clock.argtypes=[C.c_uint64];cls.c.model_now.restype=C.c_uint64
        cls.c.model_command.argtypes=[C.c_void_p,C.c_uint];cls.c.model_status.argtypes=[C.c_void_p];cls.c.model_trace.restype=C.c_void_p
        spec=importlib.util.spec_from_file_location('ym2203_revc_stream',ROOT/'host/lib/ym2203_revc_stream.py');cls.host=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.host)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def setUp(self):self.c.model_init(50)
    def status(self):
        out=C.create_string_buffer(64);self.c.model_status(out);return out.raw
    def command(self,op,seq,payload=b''):
        data=packet(op,seq,payload);self.c.model_command(data,len(data));return self.status()
    def begin(self,data):return self.command(2,0,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
    def test_prepare_distinguishes_busy_from_audio_failure_without_accepting_BEGIN(self):
        data=score();self.command(1,0)
        self.c.model_prepare_result(4)
        s=self.command(2,1,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.assertEqual((s[9],s[10]),(4,4));self.assertEqual(struct.unpack_from('<I',s,16)[0],1)
        self.c.model_prepare_result(12)
        s=self.command(2,1,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.assertEqual((s[9],s[10]),(5,12));self.assertEqual(struct.unpack_from('<H',s,44)[0],12)
        self.assertEqual(struct.unpack_from('<I',s,20)[0],0)
        self.command(1,1);self.c.model_prepare_result(0)
        self.assertEqual(self.command(2,2,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))[9],1)
    def test_bad_crc_sequence_and_atomic_invalid_batch(self):
        data=score();self.assertEqual(self.begin(data)[9],1)
        bad=bytearray(packet(3,1,data[16:22]));bad[-1]^=1;self.c.model_command(bytes(bad),len(bad));self.assertEqual(self.status()[10],1)
        self.assertEqual(self.command(3,2,data[16:22])[10],3)
        invalid=data[16:22]+struct.pack('<IBB',20,0xff,0)
        s=self.command(3,1,invalid);self.assertEqual(s[10],6);self.assertEqual(struct.unpack_from('<I',s,20)[0],0)
        self.assertEqual(self.command(3,1,data[16:22])[10],0)
    def test_duplicate_does_not_append_or_extend_lease(self):
        data=score();self.begin(data);self.command(3,1,data[16:22]);self.c.model_advance(600000)
        self.command(3,1,data[16:22]);self.assertEqual(struct.unpack_from('<I',self.status(),20)[0],1)
        self.c.model_advance(400001);s=self.status();self.assertEqual(s[9],5);self.assertEqual(struct.unpack_from('<H',s,44)[0],8)
        self.command(5,2);self.assertEqual(self.status()[9],5)
        self.command(1,2);self.assertEqual(self.status()[9],4)
    def test_full_queue_and_partial_batch_never_mutate(self):
        data=score(1100);self.begin(data)
        for i in range(32):self.assertEqual(self.command(3,i+1,data[16+192*i:16+192*(i+1)])[10],0)
        s=self.command(3,33,data[16:22]);self.assertEqual(s[10],5);self.assertEqual(struct.unpack_from('<I',s,20)[0],1024)
        self.assertEqual(struct.unpack_from('<HH',s,36),(1024,0))
    def test_stop_cancels_tail_and_explicit_begin_is_required(self):
        data=score();self.begin(data);self.command(3,1,data[16:]);self.command(4,2);self.c.model_advance(450000)
        before=self.c.model_trace_count();self.assertGreater(before,0)
        self.command(1,3);self.c.model_advance(4000000);self.assertEqual(self.c.model_trace_count(),before)
        self.assertEqual(self.command(4,4)[10],4)
    def test_unsealed_queue_starvation_mutes_instead_of_slowing_score(self):
        data=score(600);self.begin(data)
        for i in range(16):self.command(3,i+1,data[16+i*192:16+(i+1)*192])
        self.command(4,17)
        for i in range(300):
            self.c.model_advance(200000);s=self.status()
            if s[9]==5:break
            self.command(5,18+i)
        self.assertEqual(struct.unpack_from('<H',s,44)[0],9)
    def test_crc_seal_integrity_failure_and_u32_sequence_wrap(self):
        data=score(1);self.begin(data);changed=struct.pack('<IBB',0,0,99)
        self.command(3,1,changed);s=self.command(6,2);self.assertEqual(s[9:11],bytes([5,11]))
        self.c.model_init(50);self.c.model_sequence(C.c_uint32(0xffffffff))
        s=self.command(1,0xffffffff);self.assertEqual(struct.unpack_from('<I',s,16)[0],0)
        self.assertEqual(self.command(0,0)[10],0)
    def test_status_snapshot_crc_and_transport_boundaries(self):
        old=bytes(range(64));new=bytes(reversed(range(64)))
        self.c.model_transport_publish(old)
        first=[self.c.model_transport_read() for _ in range(10)]
        self.c.model_transport_publish(new);first += [self.c.model_transport_read() for _ in range(54)]
        self.assertEqual(bytes(first),old);self.assertEqual(self.c.model_transport_read(),255)
        self.c.model_transport_finish();self.assertEqual(self.c.model_transport_read(),63)
        self.c.model_transport_finish()
        out=C.create_string_buffer(208)
        for v in range(208):self.c.model_transport_byte(v)
        self.c.model_transport_finish();self.assertEqual(self.c.model_transport_pop(out),208);self.assertEqual(out.raw,bytes(range(208)))
        for v in range(209):self.c.model_transport_byte(v)
        self.c.model_transport_finish();self.assertEqual(self.c.model_transport_pop(out),-1)
        for i in range(5):self.c.model_transport_byte(i);self.c.model_transport_finish()
        self.assertEqual(self.c.model_transport_pop(out),-1)
        self.assertEqual([self.c.model_transport_pop(out) for _ in range(4)],[1]*4)
        self.assertEqual(self.c.model_transport_pop(out),0)
        s=self.status();self.assertEqual(binascii.crc32(s[:60])&0xffffffff,struct.unpack_from('<I',s,60)[0])
    def test_status_reads_do_not_renew_lease_and_timer_crosses_u32_us(self):
        self.c.model_clock(0xffff0000);self.begin(score())
        for i in range(11):self.status();self.c.model_advance(100000)
        self.assertEqual(self.status()[9],5)

    def test_play_requires_prefill_and_late_writes_are_not_skipped(self):
        data=score(600);self.begin(data);self.command(3,1,data[16:208]);self.assertEqual(self.command(4,2)[10],4)
        self.c.model_init(50);data=score(2);self.begin(data);self.command(3,1,data[16:]);self.command(4,2)
        self.c.model_clock(400001);self.c.model_advance(1);state=self.status()
        self.assertEqual(state[9],5);self.assertEqual(struct.unpack_from('<H',state,44)[0],10);self.assertEqual(self.c.model_trace_count(),0)
    def test_duplicate_play_does_not_restart_target_clock(self):
        data=score();self.begin(data);self.command(3,1,data[16:]);self.command(4,2);self.c.model_advance(300000)
        self.assertEqual(self.c.model_trace_count(),1)
        self.command(4,2);self.c.model_advance(100000);self.assertEqual(self.c.model_trace_count(),2)
    def test_legacy_identity_is_rejected_before_any_host_write(self):
        class Legacy:
            def readfrom(self,*args):return b'YM22F001'+bytes(56)
            def writeto(self,*args):raise AssertionError('Legacy device must not receive v2 writes')
        with self.assertRaises(self.host.ProtocolError):self.host.RevCStream(Legacy())
    def run_host(self,data,rate=100000,stall=0,hide_ack=False):
        c=self.c;host=self.host
        class Clock:
            @staticmethod
            def ticks_ms():return (c.model_now()//1000)&((1<<30)-1)
            @staticmethod
            def ticks_diff(a,b):return ((a-b+(1<<29))&((1<<30)-1))-(1<<29)
            @staticmethod
            def sleep_ms(ms):c.model_advance(ms*1000)
        class Bus:
            reads=0
            hidden=None
            hidden_until=0
            did_hide=False
            def writeto(self,address,p):
                assert address==0x42
                prior=C.create_string_buffer(64);c.model_status(prior)
                c.model_advance((len(p)+1)*9*1000000//rate)
                c.model_command(bytes(p),len(p))
                if hide_ack and p[3]==3 and not self.did_hide:
                    self.hidden=prior.raw;self.hidden_until=c.model_now()+550000;self.did_hide=True
                return len(p)
            def readfrom(self,address,n):
                assert n==64 and address==0x42
                out=C.create_string_buffer(64);c.model_status(out)
                c.model_advance((n+1)*9*1000000//rate);self.reads+=1
                if stall and self.reads==100:c.model_advance(stall)
                return self.hidden if self.hidden is not None and c.model_now()<self.hidden_until else out.raw
        previous=host.time;host.time=Clock
        path=Path(self.temp.name)/'score.bin';path.write_bytes(data)
        try:
            player=host.RevCStream(Bus());result=player.play_file(str(path))
            self.assertEqual(result['executed'],(len(data)-16)//6);self.assertEqual(result['state'],3)
            actual=C.string_at(c.model_trace(),2*c.model_trace_count())
            expected=b''.join(data[i+4:i+6] for i in range(16,len(data),6));self.assertEqual(actual,expected)
            return result,player.commands
        finally:host.time=previous
    def test_host_reports_BEGIN_audio_failure_and_preserves_target_diagnostics(self):
        self.c.model_prepare_result(12)
        with self.assertRaisesRegex(self.host.ProtocolError,'BEGIN rejected:code12 state5 error12'):
            self.run_host(score(19))
        self.assertEqual(self.status()[9],5)
    def test_actual_host_library_and_actual_C_core_complete_one_score(self):
        result,_=self.run_host(score(19));self.assertEqual(result['crc32'],binascii.crc32(score(19))&0xffffffff)
    def test_explicit_KEEP_after_DONE_still_raises_STATE(self):
        data=score(2);self.begin(data);self.command(3,1,data[16:]);self.command(4,2);self.command(6,3)
        self.c.model_advance(651000)
        owner=self
        class Bus:
            def readfrom(self,address,n):return owner.status()
            def writeto(self,address,p):owner.c.model_command(bytes(p),len(p));return len(p)
        class Clock:
            @staticmethod
            def ticks_ms():return owner.c.model_now()//1000
            @staticmethod
            def ticks_diff(a,b):return a-b
            @staticmethod
            def sleep_ms(ms):owner.c.model_advance(ms*1000)
        previous=self.host.time;self.host.time=Clock
        try:
            player=self.host.RevCStream(Bus())
            with self.assertRaisesRegex(self.host.ProtocolError,'KEEP rejected:code4 state3 error0'):
                player.command(5)
            self.assertEqual(player.seq,4)
            player.stop()
            self.assertEqual(player.seq,5)
        finally:self.host.time=previous
    def test_host_exception_cleans_up_instead_of_resuming_after_lease(self):
        with self.assertRaises(self.host.ProtocolError):self.run_host(score(600),stall=1800000)
        self.assertIn(self.status()[9],[4,5])
    def test_host_retries_only_identical_push_without_duplicate_events(self):
        result,commands=self.run_host(score(19),hide_ack=True)
        self.assertEqual(result['received'],19);self.assertGreater(commands,5)
    @unittest.skipUnless(os.getenv('REVC_TEST_SONG'),'private full-score model')
    def test_private_full_score_100kHz_keeps_original_bytes_and_timing(self):
        data=Path(os.environ['REVC_TEST_SONG']).read_bytes();result,commands=self.run_host(data)
        self.assertLess(result['max_late_us'],100000);self.assertEqual(result['total'],123137)
        print('I2C FULL SCORE MODEL:100kHz service50us events=%d commands=%d max_late_us=%d period_ms=%d CRC32=%08x;not electrical hardware'%(result['executed'],commands,result['max_late_us'],result['period_ms'],result['crc32']))
