#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reject quote/BOM inputs that mix quantities or fail reconciliation."""
from pathlib import Path
import json,shutil,subprocess,sys,tempfile,unittest
H=Path(__file__).resolve().parents[1]
class ComparisonTest(unittest.TestCase):
 def run_copy(self,change=None):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);shutil.copytree(H/'procurement',d/'procurement');(d/'tools').mkdir();shutil.copy(H/'tools/build_comparison.py',d/'tools');
   if change:change(d)
   r=subprocess.run([sys.executable,str(d/'tools/build_comparison.py')],capture_output=True,text=True)
   return r.returncode, json.loads((d/'procurement/comparison.json').read_text()) if r.returncode==0 else None
 def test_fixed_rate_totals(self):
  code,c=self.run_copy();self.assertEqual(code,0);self.assertEqual(c['variants']['primary']['vendors']['JLCPCB']['cheapest_inspected']['delivered_jpy'],37928);self.assertEqual(c['variants']['comparison']['vendors']['PCBWay']['cheapest_inspected']['delivered_jpy'],33992)
 def mutate(self,name,fn):
  def change(d):
   p=d/'procurement'/name;q=json.loads(p.read_text());fn(q);p.write_text(json.dumps(q))
  self.assertNotEqual(self.run_copy(change)[0],0)
 def test_reject_five_parts_sets(self):self.mutate('order-profile.json',lambda d:d.update(fitted_sets=5))
 def test_reject_shipping_wrong_goods(self):self.mutate('observations.json',lambda d:d['vendors']['JLCPCB']['freight']['primary'].update(goods_usd=0))
 def test_reject_pcb_wrong_quantity(self):self.mutate('observations.json',lambda d:d['vendors']['PCBWay']['boards']['base-k2'].update(quantity=2))
 def test_reject_free_freight_placeholder(self):self.mutate('observations.json',lambda d:d['vendors']['JLCPCB']['freight']['primary']['methods'][0].update(cost_usd=0,available=True))
if __name__=='__main__':unittest.main()
