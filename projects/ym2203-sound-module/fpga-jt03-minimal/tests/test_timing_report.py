# SPDX-License-Identifier: MIT
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from check import summarize


def fixture():
    paths=[]
    for a,b in [('synth_clk','audio_clk'),('audio_clk','synth_clk')]:
        paths.append({'from':'posedge '+a,'to':'posedge '+b,'path':[
            {'delay':10,'from':{'cell':'source'},'to':{'cell':'stage1'}}]})
    return {'fmax':{'synth_clk':{'constraint':16,'achieved':22},
                    'audio_clk':{'constraint':49.152,'achieved':60}},
            'utilization':{},'critical_paths':paths}


class Timing(unittest.TestCase):
    def test_two_clocks_and_routing_required(self):
        self.assertEqual(summarize(fixture(),'Routing complete.',0,{'unexpected_data_or_enable_crossings':0})['classification'],'pass')
        self.assertEqual(summarize(fixture(),'',0,{'unexpected_data_or_enable_crossings':0})['classification'],'fail')

    def test_missing_audio_constraint(self):
        r=fixture();del r['fmax']['audio_clk']
        with self.assertRaisesRegex(ValueError,'Missing'):summarize(r,'Routing complete.',0,{})

    def test_audio_timing_failure_not_hidden(self):
        r=fixture();r['fmax']['audio_clk']['achieved']=48
        self.assertEqual(summarize(r,'Routing complete.',0,{'unexpected_data_or_enable_crossings':0})['classification'],'fail')

    def test_crossing_delay_bound(self):
        r=fixture();r['critical_paths'][0]['path'][0]['delay']=21
        self.assertEqual(summarize(r,'Routing complete.',0,{'unexpected_data_or_enable_crossings':0})['classification'],'fail')


if __name__=='__main__':unittest.main()
