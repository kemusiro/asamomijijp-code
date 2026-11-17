# SPDX-License-Identifier: MIT
"""SDA/SCL open-drain model, target RTL, packet queue and unchanged HOST driver."""
import binascii
import ctypes as C
import importlib.util
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

PROJECT=Path(os.environ.get('F1_PROJECT',Path(__file__).resolve().parents[2]))


def packet(op,seq,payload=b''):
    data=struct.pack('<2sBBIH2x',b'Y2',2,op,seq,len(payload))+payload
    return data+struct.pack('<I',binascii.crc32(data)&0xffffffff)


def score(n=9):
    return struct.pack('<4sIII',b'WYM1',n,n*100+200,4000000)+b''.join(struct.pack('<IBB',i*100,0,i) for i in range(n))


class WireTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=C.CDLL(os.environ['F1_I2C_LIB'])
        cls.r.wire_write.argtypes=cls.r.wire_read.argtypes=[C.c_uint,C.c_void_p,C.c_uint]
        cls.r.wire_advance.argtypes=[C.c_uint64];cls.r.wire_now.restype=C.c_uint64
        cls.r.wire_trace.restype=C.c_void_p
        spec=importlib.util.spec_from_file_location('f1_wire_host',PROJECT/'firmware-c/host/lib/ym2203_revc_stream.py')
        cls.host=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.host)
        previous=sys.modules.get('ym2203_revc_stream')
        sys.modules['ym2203_revc_stream']=cls.host
        try:
            spec=importlib.util.spec_from_file_location('f1_wire_player',PROJECT/'firmware-c/host/lib/ym2203_revc_player.py')
            cls.player=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.player)
        finally:
            if previous is None:del sys.modules['ym2203_revc_stream']
            else:sys.modules['ym2203_revc_stream']=previous

    @classmethod
    def tearDownClass(cls):cls.r.wire_destroy()

    def setUp(self):self.r.wire_init()

    def write(self,data):self.assertEqual(self.r.wire_write(0x42,data,len(data)),len(data))

    def read(self,n=64):
        out=C.create_string_buffer(n)
        self.assertEqual(self.r.wire_read(0x42,out,n),n)
        return out.raw

    def status(self):
        data=self.read()
        self.assertEqual(data[:9],b'YM22S002\x02')
        self.assertEqual(struct.unpack_from('<I',data,60)[0],binascii.crc32(data[:60])&0xffffffff)
        return data

    def test_address_probe_wrong_address_and_filtered_glitch(self):
        self.assertEqual(self.r.wire_write(0x43,b'',0),-2)
        self.assertEqual(self.r.wire_write(0x42,b'',0),0)
        self.r.wire_glitch()
        self.assertEqual(self.status()[9:11],bytes(2))
        self.write(packet(0,0));self.assertEqual(struct.unpack_from('<I',self.status(),16)[0],1)

    def test_long_status_read_returns_ff_and_has_one_crc_snapshot(self):
        data=self.read(80)
        self.assertEqual(data[64:],bytes([255])*16)
        self.assertEqual(struct.unpack_from('<I',data,60)[0],binascii.crc32(data[:60])&0xffffffff)

    def test_shape_crc_and_maximum_packet_survive_actual_bit_transfer(self):
        for raw,result in [(packet(255,0,bytes(192)),2),(packet(0,0)[:-1]+b'\0',1),(b'bad',2)]:
            self.write(raw);self.assertEqual(self.status()[10],result)
        self.write(packet(0,0));self.assertEqual(self.status()[10],0)

    def test_oversized_transaction_fails_transport_without_truncating(self):
        self.write(bytes(209))
        s=self.status();self.assertEqual(s[9],5);self.assertEqual(s[44],7)
        self.assertEqual(self.r.wire_gate(),0)
        self.write(packet(1,0));self.assertEqual(self.status()[9],4)

    def test_four_pending_requests_then_overflow_stop_during_prepare(self):
        self.r.wire_controls(1,0,0,1)
        data=score();self.write(packet(2,0,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff)))
        for seq in range(1,6):self.write(packet(0,seq))
        s=self.status();self.assertEqual(s[9],5);self.assertEqual(s[44],7)
        self.assertEqual(self.r.wire_gate(),0)
        self.r.wire_controls(1,0,1,1)
        self.write(packet(1,0));self.assertEqual(self.status()[9],4)

    def test_wire_stop_lease_read_only_rebind_and_explicit_recovery(self):
        data=score()
        begin=data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff)
        for op,seq,payload in [(2,0,begin),(3,1,data[16:]),(4,2,b''),(6,3,b'')]:self.write(packet(op,seq,payload))
        self.r.wire_advance(500000)
        self.write(packet(1,4));self.assertEqual(self.status()[9],4)
        frozen=self.r.wire_trace_count();self.assertGreater(frozen,0)
        for _ in range(4):self.r.wire_advance(1000000);self.status()
        self.assertEqual(self.r.wire_trace_count(),frozen)
        for op,seq,payload in [(2,5,begin),(3,6,data[16:]),(4,7,b''),(6,8,b'')]:self.write(packet(op,seq,payload))
        self.r.wire_advance(1800000)
        s=self.status();self.assertEqual(s[9],5);self.assertEqual(s[44],8)
        frozen=self.r.wire_trace_count()
        for _ in range(4):self.r.wire_advance(1000000);self.assertEqual(self.status()[9],5)
        self.assertEqual(self.r.wire_trace_count(),frozen);self.assertEqual(self.r.wire_gate(),0)
        for op,seq,payload in [(1,9,b''),(2,10,begin),(3,11,data[16:]),(4,12,b''),(6,13,b'')]:self.write(packet(op,seq,payload))
        self.r.wire_advance(600000);self.write(packet(5,14));self.r.wire_advance(800000)
        self.assertEqual(self.status()[9],3);self.assertEqual(self.r.wire_trace_count(),frozen+9)
        self.assertEqual(self.r.wire_gate(),0)

    def run_player(self,mode='once'):
        r=self.r;interrupt=[mode=='interrupt']
        class Clock:
            @staticmethod
            def ticks_ms():return (r.wire_now()//1000)&((1<<30)-1)
            @staticmethod
            def ticks_diff(a,b):return ((a-b+(1<<29))&((1<<30)-1))-(1<<29)
            @staticmethod
            def sleep_ms(ms):
                if interrupt[0] and r.wire_gate() and r.wire_trace_count()>2:
                    interrupt[0]=False;raise KeyboardInterrupt()
                r.wire_advance(ms*1000)
        class Bus:
            def writeto(self,a,p):
                n=r.wire_write(a,bytes(p),len(p))
                if n<0:raise OSError('model I2C write failed')
                return n
            def readfrom(self,a,n):
                out=C.create_string_buffer(n)
                if r.wire_read(a,out,n)!=n:raise OSError('model I2C read failed')
                return out.raw
        old_host_time=self.host.time;old_player_time=self.player.time
        self.host.time=self.player.time=Clock
        logs=[]
        def write(text):
            logs.append(text)
            if mode=='repeat' and text.startswith('PLAY / cycle3'):raise KeyboardInterrupt()
        try:
            stream=self.host.RevCStream(Bus())
            with tempfile.TemporaryDirectory() as tmp:
                path=Path(tmp)/'original.bin';path.write_bytes(score())
                tracks=[{'path':str(path),'name':'original.bin','events':9,'period_ms':1100}]
                return self.player.run_playlist(stream,tracks,repeat=mode=='repeat',write=write)
        finally:self.host.time=old_host_time;self.player.time=old_player_time

    def test_unchanged_host_and_player_complete_through_sda_scl(self):
        self.assertEqual(self.run_player(),{'completed':1,'cycles':1})
        self.assertEqual(self.r.wire_trace_count(),9)
        self.assertEqual(self.status()[9],4);self.assertEqual(self.r.wire_gate(),0)

    def test_unchanged_player_repeat_and_ctrl_c_mute_without_replay(self):
        with self.assertRaises(KeyboardInterrupt):self.run_player('repeat')
        self.assertEqual(self.r.wire_trace_count(),18);self.assertEqual(self.r.wire_gate(),0)
        self.r.wire_init()
        with self.assertRaises(KeyboardInterrupt):self.run_player('interrupt')
        count=self.r.wire_trace_count();self.assertGreater(count,2);self.assertLess(count,9)
        self.r.wire_advance(4000000)
        self.assertEqual(self.r.wire_trace_count(),count);self.assertEqual(self.r.wire_gate(),0)


if __name__=='__main__':unittest.main()
