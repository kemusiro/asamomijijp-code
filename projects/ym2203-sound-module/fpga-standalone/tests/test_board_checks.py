# SPDX-License-Identifier: MIT
import copy,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.board_checks import lpf,routed_checks,CLOCKS,pad_drivers
HERE=Path(__file__).resolve().parents[1]
class BoardChecksTests(unittest.TestCase):
 def setUp(self):self.m=json.loads((HERE/'boards/ulx3s/pins.json').read_text())
 def test_constraints_match_manifest(self):self.assertEqual(lpf(self.m),(HERE/'boards/ulx3s/board.lpf').read_text())
 def test_duplicate_and_fixed_pin_errors(self):
  for change in ['duplicate','usb','reserved','voltage']:
   m=copy.deepcopy(self.m)
   if change=='duplicate':m['pins'][1]['ball']=m['pins'][0]['ball']
   elif change=='usb':next(p for p in m['pins'] if p['port']=='usb_dp_tx')['ball']='A11'
   elif change=='reserved':m['pins'][-1]['ball']='F4'
   else:m['bank_vccio_volts']['0']=2.5
   with self.subTest(change=change),self.assertRaises(ValueError):lpf(m)
 def test_clock_fail_relaxation_and_reserve_rejected(self):
  for change in ['missing','relaxed','failed','reserve']:
   r={'fmax':{n:{'constraint':f,'achieved':100} for n,f in CLOCKS.items()}}
   if change=='missing':del r['fmax']['$glbnet$clk']
   elif change=='relaxed':r['fmax']['$glbnet$clk']['constraint']=24
   elif change=='failed':r['fmax']['$glbnet$clk']['achieved']=47
   else:r['fmax']['$glbnet$clk']['achieved']=48.1
   with self.subTest(change=change),self.assertRaises(ValueError):routed_checks(r,{},self.m,{}, {})
 def test_ooc_and_unallocated_io_rejected(self):
  r={'fmax':{n:{'constraint':f,'achieved':100} for n,f in CLOCKS.items()},'utilization':{'TRELLIS_IO':{'used':0},'DCCA':{'used':0},'EHXPLLL':{'used':0}}}
  with self.assertRaises(ValueError):routed_checks(r,{},self.m,{}, {})
 def test_const_z_fold_and_active_bus_high_rejected(self):
  ports={n:{'bits':[i]} for i,n in enumerate(['host_scl','host_sda','si_scl','si_sda','usb_dp_bias','usb_dn_bias'])}
  cells={n:{'type':'$_TBUF_','connections':{'A':['1' if n=='usb_dp_bias' else '0'],'Y':p['bits']}} for n,p in ports.items() if n!='usb_dn_bias'}
  cells['disabled']={'type':'TRELLIS_IO','connections':{'B':[5],'T':['1']}}
  m={'ports':ports,'cells':cells};pad_drivers(m)
  bad=copy.deepcopy(m);bad['cells']['disabled']['connections']['T']=['0']
  with self.assertRaises(ValueError):pad_drivers(bad)
  bad=copy.deepcopy(m);bad['ports']['usb_dn_bias']['bits']=['0'];del bad['cells']['disabled']
  with self.assertRaises(ValueError):pad_drivers(bad)
  bad=copy.deepcopy(m);bad['cells']['host_sda']['connections']['A']=['1']
  with self.assertRaises(ValueError):pad_drivers(bad)
if __name__=='__main__':unittest.main()
