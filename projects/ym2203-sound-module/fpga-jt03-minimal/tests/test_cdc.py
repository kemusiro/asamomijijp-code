# SPDX-License-Identifier: MIT
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import cdc_check


def fixture():
    cells={};nets={};counter=10
    def flop(name,clock,data):
        nonlocal counter
        q=counter;counter+=1
        cells[name]={'type':'SB_DFF','port_directions':{'C':'input','D':'input','Q':'output'},
                     'connections':{'C':[clock],'D':[data],'Q':[q]}}
        return q
    synth=flop('source_synth',2,'0');audio=flop('source_audio',3,'0')
    for name,source,clock,n in [('pcm_fifo.rq1_wgray',synth,3,7),('pcm_fifo.wq1_rgray',audio,2,7),
                               ('prime_sync',audio,2,1),('bad_sync',audio,2,1),('hb_sync',audio,2,1),
                               ('run_sync',synth,3,1),('spi.cs_sync',4,2,1),('spi.sck_sync',4,2,1),('spi.mosi_sync',4,2,1)]:
        nets[name]={'bits':[flop(name+str(i),clock,source) for i in range(n)]}
    return {'modules':{'jt03_minimal':{'ports':{'synth_clk':{'direction':'input','bits':[2]},
        'audio_clk':{'direction':'input','bits':[3]},'external':{'direction':'input','bits':[4]}},
        'cells':cells,'netnames':nets}}}


class CDC(unittest.TestCase):
    def test_expected_crossings(self):
        self.assertEqual(cdc_check.inspect(fixture())['checked_first_stage_bits'],21)

    def test_unapproved_crossing_rejected(self):
        j=fixture();m=j['modules']['jt03_minimal'];source=m['cells']['source_synth']['connections']['Q'][0]
        m['cells']['bad']={'type':'SB_DFF','port_directions':{'C':'input','D':'input','Q':'output'},
                          'connections':{'C':[3],'D':[source],'Q':[999]}}
        with self.assertRaisesRegex(ValueError,'Unapproved'):cdc_check.inspect(j)

    def test_combinational_gray_rejected(self):
        j=fixture();m=j['modules']['jt03_minimal'];source=m['cells']['source_synth']['connections']['Q'][0]
        m['cells']['xor']={'type':'SB_LUT4','port_directions':{'I0':'input','O':'output'},
                          'connections':{'I0':[source],'O':[999]}}
        m['cells']['pcm_fifo.rq1_wgray0']['connections']['D']=[999]
        with self.assertRaisesRegex(ValueError,'nonregistered'):cdc_check.inspect(j)

    def test_missing_kept_register_rejected(self):
        j=fixture();del j['modules']['jt03_minimal']['netnames']['run_sync']
        with self.assertRaisesRegex(ValueError,'Missing kept'):cdc_check.inspect(j)


if __name__=='__main__':unittest.main()
