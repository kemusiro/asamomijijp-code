# SPDX-License-Identifier: MIT
"""USB wire + unchanged HOST -> Si5351 + real YM bus/serial/PCM/I2S fixture.
No sound chip synthesis, OS USB stack or electrical hardware is simulated.
"""
import binascii
import ctypes as C
import struct
import unittest
import test_real_ym as base

class UsbYmTests(unittest.TestCase):
    setUpClass=classmethod(base.RealYmTests.setUpClass.__func__)
    tearDownClass=classmethod(base.RealYmTests.tearDownClass.__func__)
    trace=base.RealYmTests.trace
    play=base.RealYmTests.play
    start_held=base.RealYmTests.start_held

    def setUp(self):
        base.RealYmTests.setUp(self)
        self.assertEqual(self.r.usb_enumerate(),0)
        self.assertEqual(self.r.usb_online(),1)
        self.mt=0;self.ct=0

    def note(self,v,n=60,velocity=100):
        self.assertEqual(self.r.usb_midi(9|((0x90+v)<<8)|(n<<16)|(velocity<<24),self.mt),0)
        self.mt^=1

    def chord(self):
        for v in range(6):self.note(v,60+(v%3)*4)
        self.r.real_advance(30000)
        self.assertEqual(self.r.usb_midi_owned(),1)
        self.assertEqual(self.r.usb_midi_mask(),63)
        self.assertEqual(self.r.real_gate(),1)
        self.assertEqual(self.r.real_sources(),63)
        self.assertEqual(self.r.usb_midi_fault(),0)

    def quiet(self):
        self.r.real_advance(10000)
        self.assertEqual(self.r.real_gate(),0)
        self.assertEqual(self.r.real_sources(),0)
        self.assertEqual(self.r.usb_midi_owned(),0)
        self.assertEqual(self.r.real_fault(),0)

    def cdc(self,s):
        b=s.encode();self.assertEqual(self.r.usb_cdc(b,len(b),self.ct),0);self.ct^=1
        self.r.real_advance(500)

    def test_midi_begin_reject_global_stop_i2c_blocks_midi_explicit_return(self):
        self.chord();data=base.file_data()
        with self.assertRaises(self.host.ProtocolError):
            self.stream.command(2,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.assertEqual(self.r.real_gate(),1)
        self.assertEqual(self.r.real_config(1),2) # even quiet/preparing MIDI owns clock
        self.stream.stop();self.quiet()
        self.r.real_advance(201000)
        self.start_held()
        for v in range(6):self.note(v)
        self.assertEqual(self.r.usb_midi_owned(),0)
        self.assertEqual(self.r.real_sources(),63)
        self.stream.stop();self.quiet();self.r.real_advance(201000)
        self.assertEqual(self.r.real_gate(),0)
        self.chord()
        self.r.usb_midi(11|(0xb0<<8)|(120<<16),self.mt);self.mt^=1;self.quiet()
        self.play()

    def test_usb_unplug_mutes_midi_no_auto_resume_on_enumeration(self):
        self.chord();self.r.usb_vbus(0)
        self.assertEqual(self.r.real_gate(),0) # asynchronous VBUS inhibit
        self.quiet();self.r.usb_vbus(1);self.r.real_advance(100)
        self.assertEqual(self.r.usb_enumerate(),0);self.mt=self.ct=0
        self.assertEqual(self.r.real_gate(),0);self.chord()

    def test_bus_reset_and_suspend_mute_midi_without_resetting_audio(self):
        self.chord();self.r.usb_bus_reset();self.quiet()
        self.assertEqual(self.r.usb_enumerate(),0);self.mt=self.ct=0;self.chord()
        self.r.usb_sof_enable(0);self.r.real_advance(14000);self.quiet()
        self.assertEqual(self.r.usb_online(),0)
        self.r.usb_sof_enable(1);self.r.real_advance(202000)
        self.assertEqual(self.r.real_gate(),0);self.chord()

    def test_usb_detach_reset_suspend_never_stop_i2c(self):
        self.start_held();count=self.r.real_trace_count()
        self.r.usb_vbus(0);self.r.real_advance(10000)
        self.assertEqual(self.r.real_gate(),1);self.assertEqual(self.r.real_sources(),63)
        self.r.usb_vbus(1);self.r.real_advance(100);self.assertEqual(self.r.usb_enumerate(),0)
        self.r.usb_bus_reset();self.r.real_advance(10000)
        self.assertEqual(self.r.real_gate(),1)
        self.assertEqual(self.r.usb_enumerate(),0);self.mt=self.ct=0
        self.r.usb_sof_enable(0);self.r.real_advance(10000)
        self.assertEqual(self.r.real_gate(),1);self.assertEqual(self.r.real_fault(),0)
        self.assertEqual(self.r.real_trace_count(),count)
        self.stream.stop();self.r.usb_sof_enable(1);self.quiet()
        self.r.usb_vbus(0);self.r.real_advance(100);self.play()
        self.assertEqual(self.r.real_fault(),0);self.assertEqual(self.r.usb_configured(),0)

    def test_cdc_status_backpressure_stop_panic_scope_and_overlong_line(self):
        self.chord();self.cdc('status\n')
        # Never poll bulk IN: STOP must work even with an undrained response.
        self.cdc('stop\n');self.quiet();self.r.real_advance(201000)
        self.start_held();self.cdc('panic\n');self.assertEqual(self.r.real_gate(),1)
        self.cdc('x'*40+'stop\n');self.assertEqual(self.r.real_gate(),1)
        self.cdc('\x03');self.quiet()
        self.r.real_advance(201000);self.chord();self.cdc('status\n')
        result=bytearray()
        for _ in range(10):
            b=C.create_string_buffer(64);n=self.r.usb_cdc_read(b);self.assertGreaterEqual(n,0)
            result+=b.raw[:n]
            if result.endswith(b'\r\n'):break
        self.assertIn(b'STATUS F1 audio_ok=00000001',result)
        self.assertIn(b'MIDI_owned=00000001 mask=0000003f',result)
        self.cdc('panic\n');self.quiet()

if __name__=='__main__':unittest.main()
