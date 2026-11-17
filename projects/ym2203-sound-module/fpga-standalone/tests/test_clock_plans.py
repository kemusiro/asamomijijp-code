# SPDX-License-Identifier: MIT
import importlib.util
from pathlib import Path
import random
import unittest
from fractions import Fraction

spec=importlib.util.spec_from_file_location('plans',Path(__file__).resolve().parents[1]/'tools/si5351_profiles.py')
plans=importlib.util.module_from_spec(spec);spec.loader.exec_module(plans)


class PlanTests(unittest.TestCase):
    def test_committed_rom_is_exactly_regenerated(self):
        rtl,items=plans.render()
        self.assertEqual(rtl,(Path(__file__).resolve().parents[1]/'rtl/revc_si5351_rom.v').read_text())
        self.assertEqual(len(items),8)
        self.assertTrue(all(len(i['rows'])==53 for i in items))

    def test_independent_decode_matches_2000_arbitrary_rates_and_crystals(self):
        random_source=random.Random(5351)
        for xtal in [25000000,27000000]:
            for f in [*plans.DEFAULT,*[random_source.randrange(1500000,4000001) for _ in range(1000)]]:
                p=plans.plan(f,xtal);reg=dict((r,v) for r,v,_ in p['rows'])
                def decode(addr):
                    b=[reg[addr+i] for i in range(8)]
                    p1=((b[2]&3)<<16)|(b[3]<<8)|b[4]
                    p2=((b[5]&15)<<16)|(b[6]<<8)|b[7]
                    p3=((b[5]&240)<<12)|(b[0]<<8)|b[1]
                    self.assertTrue(0<p3<=1048575)
                    return Fraction((p1+512)*p3+p2,128*p3)
                self.assertEqual(xtal*decode(34)/decode(42),f)
                self.assertEqual(xtal*decode(26)/decode(50),49152000)
                self.assertTrue(600000000<=p['pllb_hz']<=900000000)
                self.assertEqual(p['src_num'],f);self.assertEqual(p['src_den'],72*48000)

    def test_limits_crystal_load_and_default_profile_are_explicit(self):
        for f in [0,1499999,4000001,8000000]:
            with self.assertRaises(ValueError):plans.plan(f)
        for xtal,load in [(24000000,10),(25000000,0)]:
            with self.assertRaises(ValueError):plans.plan(4000000,xtal,load)
        for load,encoded in [(6,0x52),(8,0x92),(10,0xd2)]:
            p=plans.plan(4000000,load=load)
            self.assertIn((183,encoded,255),p['rows'])
        with self.assertRaises(ValueError):plans.render([3000000]*8)
