# SPDX-License-Identifier: MIT
"""Unchanged HOST -> SDA/SCL -> real-YM bus adapter -> serial/PCM/I2S RTL.

The peripheral is a protocol/serial fixture, not a YM2203 sound emulator.
"""
import binascii
import ctypes as C
import importlib.util
import os
from pathlib import Path
import struct
import tempfile
import unittest

PROJECT=Path(os.environ.get('F1_PROJECT',Path(__file__).resolve().parents[2]))


def file_data(held=False):
    events=[(0,0x30,1),(0,0x40,48),(0,0x50,31),(0,0x60,0),(0,0x80,15),
            (0,0xb0,7),(0,0xa4,0x22),(0,0xa0,0x69),(0,0x28,0xf0),(0,0x28,0xf1),(0,0x28,0xf2),
            (0,7,0x38),(0,8,7),(0,9,7),(0,10,7),
            (1500 if held else 20,0xa0,0x88),(1900 if held else 40,0x28,0)]
    return struct.pack('<4sIII',b'WYM1',len(events),2000 if held else 80,4000000)+b''.join(struct.pack('<IBB',*e) for e in events)


class RealYmTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r=C.CDLL(os.environ['F1_REAL_LIB'])
        cls.r.real_read.argtypes=cls.r.real_write.argtypes=[C.c_uint,C.c_void_p,C.c_uint]
        cls.r.real_advance.argtypes=[C.c_uint64];cls.r.real_now.restype=C.c_uint64
        cls.r.real_trace.restype=C.c_void_p
        spec=importlib.util.spec_from_file_location('f1_real_host',PROJECT/'firmware-c/host/lib/ym2203_revc_stream.py')
        cls.host=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.host)
        r=cls.r
        class Clock:
            @staticmethod
            def ticks_ms():return (r.real_now()//1000)&((1<<30)-1)
            @staticmethod
            def ticks_diff(a,b):return ((a-b+(1<<29))&((1<<30)-1))-(1<<29)
            @staticmethod
            def sleep_ms(ms):r.real_advance(ms*1000)
        class Bus:
            def writeto(self,address,p):
                n=r.real_write(address,bytes(p),len(p))
                if n!=len(p):raise OSError('physical model write failed')
                return n
            def readfrom(self,address,n):
                out=C.create_string_buffer(n)
                if r.real_read(address,out,n)!=n:raise OSError('physical model read failed')
                return out.raw
        cls.bus_type=Bus;cls.previous=cls.host.time;cls.host.time=Clock

    @classmethod
    def tearDownClass(cls):cls.host.time=cls.previous;cls.r.real_destroy()

    def setUp(self):
        self.r.real_init()
        self.assertEqual(self.r.real_healthy(),1)
        self.assertEqual(self.r.real_fault(),0)
        self.assertEqual(self.r.real_violations(),0)
        self.stream=self.host.RevCStream(self.bus_type())

    def trace(self):return C.string_at(self.r.real_trace(),2*self.r.real_trace_count())

    def start_held(self):
        data=file_data(True)
        self.stream.stop()
        self.stream.command(2,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.stream.command(3,data[16:]);self.stream.command(4);self.stream.command(6)
        self.r.real_advance(260000)
        self.assertEqual(self.r.real_gate(),1)
        self.assertEqual(self.r.real_sources(),63)
        self.assertGreater(self.r.real_nonzero(),0)

    def play(self):
        data=file_data();before=len(self.trace())
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'original.bin';p.write_bytes(data)
            result=self.stream.play_file(str(p))
        self.assertEqual(result['state'],3);self.assertEqual(result['error'],0)
        self.assertEqual(result['crc32'],binascii.crc32(data)&0xffffffff)
        self.assertEqual(self.trace()[before:],b''.join(data[i+4:i+6] for i in range(16,len(data),6)))
        self.assertEqual(self.r.real_gate(),0);self.assertEqual(self.r.real_healthy(),1)
        self.assertEqual(self.r.real_sources(),0)
        self.assertEqual(self.r.real_violations(),0)
        self.assertGreater(self.r.real_nonzero(),0)

    def test_unchanged_host_completes_through_bus_rx_pcm_i2s(self):self.play()

    def test_stop_mutes_cancels_tail_then_explicit_full_replay(self):
        self.start_held();self.stream.stop()
        count=self.r.real_trace_count();nonzero=self.r.real_nonzero()
        self.r.real_advance(10000)
        self.assertEqual(self.r.real_trace_count(),count);self.assertEqual(self.r.real_nonzero(),nonzero)
        self.assertEqual(self.r.real_gate(),0);self.assertEqual(self.stream.status()['state'],4)
        self.assertEqual(self.r.real_sources(),0)
        self.play()

    def test_lease_cleanup_read_only_reattachment_never_replays(self):
        self.start_held();self.r.real_advance(1000000)
        s=self.stream.status();self.assertEqual(s['state'],5);self.assertEqual(s['error'],8)
        self.assertEqual(s['queued'],0);self.assertEqual(self.r.real_gate(),0)
        self.assertEqual(self.r.real_sources(),0)
        count=self.r.real_trace_count()
        self.stream=self.host.RevCStream(self.bus_type())
        self.r.real_advance(10000)
        self.assertEqual(self.r.real_trace_count(),count);self.assertEqual(self.r.real_gate(),0)
        self.stream.stop();self.assertEqual(self.stream.status()['error'],0)

    def test_audio_clock_loss_and_return_do_not_auto_resume(self):
        self.start_held();self.r.real_audio_clock(0);self.r.real_advance(3000)
        self.assertEqual(self.r.real_gate(),0)
        self.assertEqual(self.stream.status()['state'],5)
        self.r.real_audio_clock(1);self.r.real_advance(12000)
        self.assertEqual(self.r.real_gate(),0);self.assertEqual(self.stream.status()['state'],5)

    def test_control_clock_loss_audio_side_watchdog_closes_gates(self):
        self.start_held();self.r.real_control_clock(0);self.r.real_advance(3000)
        self.assertEqual(self.r.real_gate(),0);self.assertEqual(self.r.real_fault(),1)
        self.r.real_control_clock(1);self.r.real_advance(12000)
        self.assertEqual(self.r.real_gate(),0);self.assertEqual(self.stream.status()['state'],5)

    def test_forbidden_exponent_mutes_instead_of_repairing_audio(self):
        self.start_held();self.r.real_bad_serial();self.r.real_advance(1000)
        self.assertEqual(self.r.real_gate(),0)
        s=self.stream.status();self.assertEqual(s['state'],5);self.assertFalse(s['flags']&2)

    def test_external_permit_loss_mutes_before_another_clock_edge(self):
        self.start_held();self.r.real_permit(0)
        self.assertEqual(self.r.real_gate(),0)
        self.r.real_advance(10);self.r.real_permit(1);self.r.real_advance(10000)
        self.assertEqual(self.r.real_gate(),0);self.assertEqual(self.stream.status()['state'],0)


if __name__=='__main__':unittest.main()
