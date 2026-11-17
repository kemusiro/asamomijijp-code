# SPDX-License-Identifier: MIT
"""Fail-closed report acceptance; do not silently accept missing/relaxed clocks."""
import importlib.util
from pathlib import Path
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from check_pnr_cdc import census,CONTROL_META,AUDIO_META,BUNDLE,RESET
s=importlib.util.spec_from_file_location('pnr_checks',Path(__file__).resolve().parents[1]/'tools/pnr_checks.py');p=importlib.util.module_from_spec(s);s.loader.exec_module(p)
class PnrChecksTests(unittest.TestCase):
 def model(self):return {'fmax':{'clk':{'constraint':48.0008,'achieved':60},'audio_clk':{'constraint':49.1521,'achieved':80}},'utilization':{'TRELLIS_IO':{'used':0},'DCCA':{'used':0}},'critical_paths':[]}
 def test_both_clocks_required(self):
  r=self.model();self.assertEqual(set(p.timing(r)['clocks']),{'clk','audio_clk'})
  del r['fmax']['audio_clk']
  with self.assertRaises(ValueError):p.timing(r)
 def test_failed_or_relaxed_clock_rejected(self):
  for field,val in [('achieved',47.9),('constraint',24)]:
   r=self.model();r['fmax']['clk'][field]=val
   with self.assertRaises(ValueError):p.timing(r)
 def test_evaluation_mode_must_not_allocate_io_or_clock_tree(self):
  for kind in ['TRELLIS_IO','DCCA']:
   r=self.model();r['utilization'][kind]['used']=1
   with self.assertRaises(ValueError):p.timing(r)
class CdcMemoryTests(unittest.TestCase):
 def model(self):
  return {'ports':{'clk':{'bits':[2]},'audio_clk':{'bits':[3]}},
   'netnames':{n:{'bits':[]} for n in CONTROL_META+AUDIO_META+[BUNDLE,RESET]},
   'cells':{
    'rom':{'type':'DP16KD','parameters':{'DATA_WIDTH_A':format(36,'032b'),'DATA_WIDTH_B':format(36,'032b')},
     'connections':{'CLKA':['0'],'CLKB':[2],'WEB':['0'],'DOA0':[10]},'port_directions':{'CLKA':'input','CLKB':'input','WEB':'input','DOA0':'output'}},
    'consumer':{'type':'TRELLIS_FF','parameters':{},'connections':{'CLK':[2],'DI':[10],'Q':[11]},'port_directions':{'CLK':'input','DI':'input','Q':'output'}}}}
 def test_width36_read_uses_b_clock_for_doa_half(self):
  r=self.model();self.assertEqual(census(r)['unclassified_crossings'],0)
  r['cells']['rom']['connections']['CLKB']=[3]
  with self.assertRaisesRegex(ValueError,'Unclassified CDC'):census(r)
if __name__=='__main__':unittest.main()
