# SPDX-License-Identifier: MIT
"""Unchanged HOST with physical Si5351 register bus and real-YM audio RTL."""
import struct
import binascii
import test_real_ym as base


class ClockedYmTests(base.RealYmTests):
    def test_eight_profiles_reprime_without_automatic_notes_and_restore_4mhz(self):
        rates=[4000000,3579545,3993600,3000000,2000000,1500000,2500000,3500000]
        for p in range(1,8):
            self.assertEqual(self.r.real_config(p),0)
            self.assertEqual(self.r.real_clock_frequency(),rates[p])
            self.assertEqual(self.r.real_clock_profile(),p)
            self.assertEqual(self.r.real_healthy(),1)
            self.assertEqual(self.r.real_gate(),0)
            self.assertEqual(self.r.real_sources(),0)
        # v2 is deliberately still 4MHz; do not play a 4MHz file at 3.5MHz.
        data=base.file_data()
        with self.assertRaises(self.host.ProtocolError):
            self.stream.command(2,data[:16]+struct.pack('<I',binascii.crc32(data)&0xffffffff))
        self.assertEqual(self.stream.status()['result'],6)
        self.assertEqual(self.r.real_gate(),0)
        self.assertEqual(self.r.real_config(0),0)
        self.play()

    def test_profile_change_rejected_while_i2c_or_other_owner_active(self):
        self.start_held()
        self.assertEqual(self.r.real_config(1),2)
        self.assertEqual(self.r.real_clock_frequency(),4000000)
        self.assertEqual(self.r.real_gate(),1)
        self.stream.stop()
        self.r.real_other_owned(1)
        self.assertEqual(self.r.real_config(1),2)
        self.assertEqual(self.r.real_gate(),0)
        self.r.real_other_owned(0)
        self.assertEqual(self.r.real_config(15),1)

    def test_pll_loss_latches_off_then_explicit_configuration_and_play(self):
        self.start_held();self.r.real_clock_loss(1);self.r.real_advance(12000)
        self.assertEqual(self.r.real_clock_error(),7)
        self.assertEqual(self.r.real_gate(),0)
        self.assertEqual(self.stream.status()['state'],5)
        self.r.real_clock_loss(0);self.r.real_advance(12000)
        self.assertEqual(self.r.real_gate(),0)
        self.assertEqual(self.r.real_clock_error(),7)
        self.assertEqual(self.r.real_config(0),0)
        self.assertEqual(self.r.real_healthy(),1)
        self.assertEqual(self.r.real_gate(),0)
        self.play()
