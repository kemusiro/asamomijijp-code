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
   r=subprocess.run([sys.executable,str(Path(__file__).with_name('verify_cam.py')),str(tmp),'--no-previews'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   self.assertNotEqual(r.returncode,0,'Corrupted CAM was accepted')
 def test_01_missing_hole(self):
  def mutation(t):
   p=t/'artifacts/module/gerbers/p2-ym2203-lc-t-NPTH.drl';s=p.read_text();s=s.replace('X3.5Y-3.5\n','',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_02_drill_offset(self):
  def mutation(t):
   p=t/'artifacts/module/gerbers/p2-ym2203-lc-t-NPTH.drl';s=p.read_text();s=s.replace('X3.5Y-3.5','X3.6Y-3.5',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_03_missing_copper_layer(self):
  self.check_mutation(lambda t:(t/'artifacts/base/gerbers/p2-base-lc-t-In1_Cu.g1').unlink())
 def test_04_wrong_layer_count(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-job.gbrjob';d=json.loads(p.read_text());d['GeneralSpecs']['LayerNumber']=2;p.write_text(json.dumps(d))
  self.check_mutation(mutation)
 def test_05_unconnected_report(self):
  def mutation(t):
   p=t/'artifacts/base/drc.json';d=json.loads(p.read_text());d['unconnected_items']=[{'type':'unconnected_items'}];p.write_text(json.dumps(d))
  self.check_mutation(mutation)

 def test_06_clock_module_hole_missing(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-PTH.drl';s=p.read_text();s=s.replace('X36.19Y-34.19\n','',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_07_clock_module_hole_offset(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-PTH.drl';s=p.read_text();s=s.replace('X43.81Y-34.19','X44.81Y-34.19',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)

 def test_08_usb_slot_length(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-PTH.drl';s=p.read_text();s=s.replace('G01X79.68Y-93.775','G01X79.68Y-93.975',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_09_source_swd_hole_missing(self):
  def mutation(t):
   p=t/'artifacts/module/gerbers/p2-ym2203-lc-t-PTH.drl';s=p.read_text();s=s.replace('X23.72Y-44.095\n','',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_10_lcd_hole_old_pitch(self):
  def mutation(t):
   p=t/'artifacts/panel/gerbers/p2-panel-lc-n-NPTH.drl';s=p.read_text();s=s.replace('X45.22Y-7.5','X46.22Y-7.5',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)

 def test_11_dc_slot_length(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-PTH.drl';s=p.read_text();s=s.replace('G01X86.4Y-85.2','G01X86.4Y-85.1',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)

 def test_12_jack_locator_missing(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-NPTH.drl';s=p.read_text();s=s.replace('X68.5Y-93.0\n','',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_13_second_tip_leg_missing(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-PTH.drl';s=p.read_text();s=s.replace('X73.9Y-96.5\n','',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)
 def test_14_pot_pin_offset(self):
  def mutation(t):
   p=t/'artifacts/base/gerbers/p2-base-lc-t-PTH.drl';s=p.read_text();s=s.replace('X53.5Y-95.0\n','X53.7Y-95.0\n',1);assert s!=p.read_text();p.write_text(s)
  self.check_mutation(mutation)

if __name__=='__main__':
 sys.argv_work=sys.argv.pop(1)
 result=unittest.TextTestRunner(verbosity=1).run(unittest.defaultTestLoader.loadTestsFromTestCase(CAMRejection))
 (Path(sys.argv_work)/'cam-negative-verification.json').write_text(json.dumps(dict(tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),result='PASS' if result.wasSuccessful() else 'FAIL'),indent=2)+'\n')
 raise SystemExit(0 if result.wasSuccessful() else 1)
