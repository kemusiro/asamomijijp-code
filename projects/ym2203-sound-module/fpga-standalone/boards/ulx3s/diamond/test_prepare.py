#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Preparation regressions, including a mock Tcl API; not a Diamond execution."""
import argparse,csv,hashlib,json,re,subprocess,tempfile,unittest,sys
from pathlib import Path
from prepare import prepare,sha,HERE,F1

class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='f1-diamond-test-');cls.out=Path(cls.temp.name)/'bundle with spaces';cls.manifest=prepare(cls.out)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 def test_hashes(self):
  for name,h in self.manifest['files_sha256'].items():self.assertEqual(sha(self.out/name),h)
 def test_native_ports_and_pins(self):
  pins=json.loads((self.out/'pins.json').read_text())['pins'];lpf=(self.out/'carrier.lpf').read_text();self.assertEqual(len(pins),49)
  for p in pins:self.assertIn('LOCATE COMP "'+p['port']+'" SITE "'+p['ball']+'";',lpf)
  self.assertEqual(lpf.count('LOCATE COMP'),49)
  top=(self.out/'src/diamond_top.sv').read_text();self.assertIn('inout wire [7:0] ym_data',top);self.assertIn('output wire [2:0] led',top)
  self.assertIn('16\'hcafe',top);self.assertIn('USB_VID=0,USB_PID=0',(self.out/'src/top.sv').read_text());self.assertIn('OBZ dn_bias_disabled',(self.out/'src/top.sv').read_text())
 def test_clocks_and_no_blanket_waivers(self):
  lpf=(self.out/'carrier.lpf').read_text();sdc=(self.out/'synthesis.sdc').read_text();active='\n'.join(l for l in (lpf+'\n'+sdc).splitlines() if not l.strip().startswith('#'))
  self.assertIn('"dut/clk" 48.000 MHz',lpf);self.assertIn('"audio49" 49.152 MHz',lpf);self.assertNotIn('50.000 MHz',lpf)
  for forbidden in ['BLOCK ASYNC','BLOCK RESET','set_false_path','set_clock_groups']:self.assertNotIn(forbidden,active)
 def test_every_io_has_unreviewed_budget(self):
  rows=list(csv.DictReader((self.out/'io-review.csv').open()));self.assertEqual(len(rows),49);self.assertTrue(all(r['status']=='UNREVIEWED' and r['timing_scope'] for r in rows))
  r=json.loads((self.out/'timing-review.json').read_text());self.assertFalse(r['timing_closed']);self.assertFalse(r['vendor_execution']);self.assertTrue(all(v is None for v in r['checks'].values()))
 def test_output_protection(self):
  before=sha(self.out/'bundle-manifest.json')
  with self.assertRaises(FileExistsError):prepare(self.out)
  self.assertEqual(sha(self.out/'bundle-manifest.json'),before)
 def test_tcl_mock_paths_and_processes(self):
  # The mock checks dispatch and spaces in paths; it does not validate vendor API semantics.
  mock='''set calls {}\nproc prj_project {args} {global calls; lappend calls [linsert $args 0 prj_project]}\nproc prj_src {args} {global calls; if {![file exists [lindex $args 1]]} {error "missing source"}; lappend calls [linsert $args 0 prj_src]}\nproc prj_impl {args} {global calls; lappend calls [linsert $args 0 prj_impl]}\nproc prj_run {args} {global calls; lappend calls [linsert $args 0 prj_run]}\nsource [lindex $argv 0]\nsource [lindex $argv 1]\nforeach c $calls {puts "CALL $c"}\n'''
  m=Path(self.temp.name)/'mock.tcl';m.write_text(mock);r=subprocess.run(['tclsh',str(m),str(self.out/'project.tcl'),str(self.out/'route.tcl')],capture_output=True,text=True,check=True).stdout
  self.assertIn('LFE5U-85F-6BG381C',r);self.assertIn('prj_impl option top revc_ulx3s_diamond_top',r)
  steps=[line for line in r.splitlines() if line.startswith('CALL prj_run')];self.assertEqual(steps,['CALL prj_run Synthesis -impl impl','CALL prj_run Translate -impl impl','CALL prj_run Map -impl impl','CALL prj_run PAR -impl impl','CALL prj_run PAR -impl impl -task PARTrace'])
  self.assertNotIn('CALL prj_run Export',r);self.assertNotIn('Bitgen', '\n'.join(steps))
 def test_original_functional_evidence_unchanged(self):
  board=json.loads((F1/'verification/ulx3s-board-20261115.json').read_text());core=board['functional_regression']['report']['source_report']
  for root,key in [(F1,'sources_sha256'),(PROJECT,'unchanged_host_sha256'),(PROJECT,'c_oracle_sha256')]:
   for name,digest in core[key].items():self.assertEqual(sha(root/name),digest,name)
  for name,digest in board['sources_sha256'].items():
   if name.startswith('rtl/') or name in ['boards/ulx3s/top.v','boards/ulx3s/clocking.v','boards/ulx3s/pins.json','boards/ulx3s/board.lpf','boards/ulx3s/board.sdc']:self.assertEqual(sha(F1/name),digest,name)

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--project',type=Path,default=F1.parent);p.add_argument('--output',type=Path,required=True);a=p.parse_args();PROJECT=a.project
 r=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests))
 if not r.wasSuccessful():raise SystemExit(1)
 sources={str(f.relative_to(F1)):sha(f) for f in HERE.iterdir() if f.is_file()};report={'schema_version':1,'kind':'Diamond preparation regression with mock Tcl API; vendor execution NOT performed','all_passed':True,'tests':r.testsRun,'sources_sha256':sources,'vendor_execution':False,'timing_closed':False,'existing_host_and_rtl_hashes_match':True,'physical_acceptance':False}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS preparation only; no vendor timing result')
