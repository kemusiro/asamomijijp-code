# SPDX-License-Identifier: MIT
"""Negative tests on actual exported CAM; never mutate delivery files."""
import copy, importlib.util, json, subprocess, sys, tempfile, unittest
from pathlib import Path

class CAMRejection(unittest.TestCase):
 def setUp(self):
  self.real=Path(sys.argv_work)
 def check_mutation(self, mutate):
  import shutil
  with tempfile.TemporaryDirectory() as tmp:
   tmp=Path(tmp);shutil.copytree(self.real/'artifacts',tmp/'artifacts');shutil.copy(self.real/'native-geometry.json',tmp)
   mutate(tmp)
   r=subprocess.run([sys.executable,str(Path(__file__).with_name('verify_cam.py')),str(tmp)],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   self.assertNotEqual(r.returncode,0,'Corrupted CAM was accepted')
 def test_01_missing_hole(self):
  def mutation(t):
   p=t/'artifacts/module/gerbers/p2-ym2203-lc-f-NPTH.drl';s=p.read_text();s=s.replace('X3.5Y-3.5\n','',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_02_drill_offset(self):
  def mutation(t):
   p=t/'artifacts/module/gerbers/p2-ym2203-lc-f-NPTH.drl';s=p.read_text();s=s.replace('X3.5Y-3.5','X3.6Y-3.5',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_03_missing_copper_layer(self):
  self.check_mutation(lambda t:(t/'artifacts/base/gerbers/p2-base-lc-f-In1_Cu.g1').unlink())
 def test_04_wrong_layer_count(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-f-job.gbrjob';d=json.loads(p.read_text());d['GeneralSpecs']['LayerNumber']=2;p.write_text(json.dumps(d))
  self.check_mutation(mutation)
 def test_05_unconnected_report(self):
  def mutation(t):
   p=t/'artifacts/base/drc.json';d=json.loads(p.read_text());d['unconnected_items']=[{'type':'unconnected_items'}];p.write_text(json.dumps(d))
  self.check_mutation(mutation)

if __name__=='__main__':
 sys.argv_work=sys.argv.pop(1);unittest.main()
