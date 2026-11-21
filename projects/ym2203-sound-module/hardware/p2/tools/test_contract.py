# SPDX-License-Identifier: MIT
import copy,csv,unittest
from contract import load,verify,verify_bom,ROOT
class Contract(unittest.TestCase):
 def setUp(self):self.d=load()
 def reject(self,b,r,pin,net):
  d=copy.deepcopy(self.d);p=next(p for p in d[b]['parts'] if p['ref']==r);next(p for p in p['pins'] if p['num']==pin)['net']=net
  with self.assertRaises(AssertionError):verify(d)
 def test_current(self):self.assertTrue(verify(self.d));self.assertTrue(verify_bom(self.d))
 def test_swapped_trs(self):self.reject('base','JLINE','2','LINE_L')
 def test_5v_on_headamp(self):self.reject('base','UHP','9','V5_CARRIER')
 def test_unmuted_headamp(self):self.reject('base','UHP','5','V3V3')
 def test_charge_pump(self):self.reject('base','CHPFLY','2','GND')
 def test_negative_rail(self):self.reject('base','UHP','6','GND')
 def test_feedback(self):self.reject('base','RHPFBL','2','HP_FB_R')
 def test_clock_pin(self):self.reject('module','USOURCE','JP7.2','MOD_I2S_BCK')
 def test_host(self):self.reject('base','UBASE','JP6.4','HOST_SCL')
 def test_g40(self):self.reject('module','JMOD','1','MCU_3V3')
 def test_led_supply(self):self.reject('module','RVOICE1','2','V3V3')
 def test_run_wire(self):self.reject('module','USOURCE','SW1.S',None)
 def test_rgb(self):self.reject('base','DRGB','4','V5_CARRIER')
 def test_bom_missing_reference(self):
  with (ROOT/'procurement/parts-1set.csv').open() as f:rows=list(csv.DictReader(f))
  next(r for r in rows if r['refs'])['refs']=''
  with self.assertRaises(AssertionError):verify_bom(self.d,rows)
 def test_bom_wrong_pack_count(self):
  with (ROOT/'procurement/parts-1set.csv').open() as f:rows=list(csv.DictReader(f))
  rows[0]['packages_for_one_set']='0'
  with self.assertRaises(AssertionError):verify_bom(self.d,rows)
if __name__=='__main__':unittest.main()
