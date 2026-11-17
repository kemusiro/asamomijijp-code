#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Pin-level and ideal external safety validation; never electrical certification."""
import argparse,hashlib,json,itertools,unittest,copy,subprocess
from pathlib import Path
from design import make,V3,V5,G
from generate import check_export
HERE=Path(__file__).resolve().parent

def validate(d,manifest):
 parts={p['ref']:p for p in d['parts']};nets=lambda r:{p['num']:p['net'] for p in parts[r]['pins']}
 def pin(r,n,net):
  if nets(r)[str(n)]!=net:raise ValueError(f'Wrong pin {r}.{n}')
 for p in manifest['pins']:
  if p['connector'].startswith(('J1.','J2.')):
   connector=p['connector'].split()[0];head,num=connector.split('.');pin('JULX'+head[-1],int(num),d['port_aliases'][p['port']])
 for r in ['U8','U9']:
  for n,net in [(1,V3),(23,V5),(24,V5),(11,G),(12,G),(13,G)]:pin(r,n,net)
  pin(r,22,'DATA_OE_N' if r=='U8' else 'CTRL_OE_N')
 pin('U5',5,'HB_SEEN_META');pin('U5',9,'HB_SEEN');pin('U5',12,'HB_SEEN_META')
 pin('U5',1,'PGWD_N');pin('U5',13,'PGWD_N');pin('U4',4,V3);pin('U4',5,G);pin('U4',6,G);pin('U4',7,'PGWD_N')
 pin('U6',3,'F_PERMIT');pin('U6',1,'PGWD_N');pin('U6',2,'HB_SEEN')
 for n,net in [(4,'F_PERMIT'),(5,'F_ARM_REQUEST'),(6,'RUN'),(8,'DAC_RUN'),(9,'RUN'),(10,'F_DAC_ALLOW'),(11,'LINE_RUN'),(12,'RUN'),(13,'F_LINE_ALLOW')]:pin('U6',n,net)
 for n,net in [(1,'RUN'),(2,'F_YM_RESET_N'),(4,'RESET_OK')]:pin('U7',n,net)
 for n,net in [(3,'F_HEARTBEAT'),(11,'F_HEARTBEAT'),(2,V3),(4,V3),(10,V3)]:pin('U5',n,net)
 for r,n,net in [('U11',1,'RUN'),('U11',2,'DATA_OE_REQ'),('U11',4,'DATA_EN'),('U10',2,'F_TRANSLATOR_OE_N'),('U10',4,'DATA_OE_REQ'),('Q3',3,'DATA_OE_N'),('Q4',3,'CTRL_OE_N'),('R24',1,'DATA_EN'),('R27',1,'RUN'),('R26',2,V3),('R29',2,V3),('U17',17,'DAC_RUN'),('R55',1,'LINE_RUN'),('U19',11,'MUTE_5V'),('U19',13,'VREF'),('U19',12,'MIX_MONO'),('U19',14,'MUTED_MONO'),('R57',1,V5)]:pin(r,n,net)
 if parts['R4']['value']!='110k 0.1%' or parts['R6']['value']!='66.5k 0.1%':raise ValueError('Wrong supervisor divider')
 pin('U2',1,'PGWD_N');pin('U3',1,'PGWD_N');pin('Q1',3,'Y_RESET_N');pin('Q1',1,'RESET_CLAMP_B');pin('Q2',3,'RESET_CLAMP_B')
 if d['module_modifications']['D9']!='REMOVE / OPEN; US2 VBUS sense-only':raise ValueError('VBUS backfeed path')
 if {p['ref'] for p in d['parts'] if any(x['net']=='US2_VBUS_RAW' for x in p['pins'])}!={'JVBUS','R1'}:raise ValueError('VBUS must be sense-only')
 for ref,value in [('R54','22k 1%'),('RL0','1k 1%'),('RL1','1k 1%'),('RL2','1k 1%')]:
  if parts[ref]['value']!=value:raise ValueError('Changed accepted analog baseline')
 for ref in ['RM0','RM1','RM2','RM3']:
  if parts[ref]['value']!='100k 1%':raise ValueError('Changed mix gain')
 pin('U15',1,'XO12');pin('U15',2,V3);pin('U15',3,'REF12_BUF');pin('U15',4,G);pin('U15',6,V3)
 # No 5V power supply may land on an FPGA signal or 3.3V power pin.
 pin('JULX2',40,V5);pin('JULX2',39,None)
 for n in [1,2,19,20]:pin('JULX2',n,V3)
 return {'parts':len(parts),'module_signal_pins_checked':33,'watchdog_timeout_ms':[10,30],'watchdog_pulse_ms':[100,300],'heartbeat_edge_interval_ms':0.5,'electrical_signoff':False}

class Safety:
 """Ideal PG/WDO and dual-DFF event model. Delays/PVT/metastability outside scope."""
 def __init__(self):self.meta=0;self.seen=0;self.pg=0;self.wdo=1;self.stop_closed=1
 def clear(self):
  if not(self.pg and self.wdo and self.stop_closed):self.meta=self.seen=0
 def edge(self):
  self.clear()
  if self.pg and self.wdo and self.stop_closed:self.seen,self.meta=self.meta,1
 def outputs(self,arm=1,dac=1,line=1,reset=1):
  self.clear();permit=bool(self.pg and self.wdo and self.stop_closed and self.seen);run=permit and arm
  return dict(permit=permit,reset_release=run and reset,dac=run and dac,line=run and line,controls_enabled=run)

class Tests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):cls.manifest=json.loads(PINFILE.read_text());cls.design=make(PINFILE)
 def test_pin_level(self):validate(self.design,self.manifest)
 def test_mutations(self):
  for kind in ['wrong_header','wrong_oe','inverted_seen','wdo_not_clearing','usb_power_bridge']:
   d=copy.deepcopy(self.design)
   if kind=='usb_power_bridge':d['module_modifications']['D9']='SHORT'
   else:
    ref,pin,net={'wrong_header':('JULX2','9','F_HOST_SDA'),'wrong_oe':('U8','22',G),'inverted_seen':('U5','9','HB_SEEN_META'),'wdo_not_clearing':('U5','13',V3)}[kind]
    next(p for p in d['parts'] if p['ref']==ref)['pins'][next(i for i,p in enumerate(next(p for p in d['parts'] if p['ref']==ref)['pins']) if p['num']==pin)]['net']=net
   with self.subTest(kind=kind),self.assertRaises(ValueError):validate(d,self.manifest)
 def test_startup_requires_two_edges(self):
  s=Safety();s.pg=1;self.assertFalse(s.outputs()['permit']);s.edge();self.assertFalse(s.outputs()['permit']);s.edge();self.assertTrue(s.outputs()['permit'])
 def test_fault_and_pulse_end_without_edges_stay_silent(self):
  for cause in ['pg','wdo','stop_closed']:
   s=Safety();s.pg=1;s.edge();s.edge();self.assertTrue(s.outputs()['line']);setattr(s,cause,0);self.assertFalse(any(s.outputs().values()));setattr(s,cause,1)
   for _ in range(100):self.assertFalse(any(s.outputs().values()))
   s.edge();self.assertFalse(s.outputs()['permit']);s.edge();self.assertTrue(s.outputs()['permit'])
 def test_independent_requests(self):
  s=Safety();s.pg=1;s.edge();s.edge()
  for arm,dac,line,reset in itertools.product([0,1],repeat=4):
   o=s.outputs(arm,dac,line,reset);self.assertEqual(o['dac'],bool(arm and dac));self.assertEqual(o['line'],bool(arm and line));self.assertEqual(o['reset_release'],bool(arm and reset))
 def test_worst_case_missing_pulse(self):
  for timeout,pulse in itertools.product([10,17,30],[100,200,300]):
   s=Safety();s.pg=1;w=Watchdog(s,timeout,pulse)
   # 1kHz heartbeat: both edges feed WDI, only rising edges clock the latch.
   for t in range(1,201):w.input(t*.5,t%2)
   self.assertTrue(s.outputs()['line'])
   w.advance(100+timeout-.001);self.assertTrue(s.outputs()['line'])
   w.advance(100+timeout);self.assertFalse(any(s.outputs().values()))
   w.advance(100+timeout+pulse);self.assertFalse(any(s.outputs().values()))
   # Repeated pulse releases without heartbeat must not reopen any gate.
   w.advance(100+timeout+pulse+5*(timeout+pulse));self.assertFalse(any(s.outputs().values()))
 def test_watchdog_recovery_needs_new_heartbeat(self):
  s=Safety();s.pg=1;w=Watchdog(s,30,300)
  w.input(1,1);w.input(2,0);w.input(3,1);self.assertTrue(s.outputs()['line'])
  w.advance(33);self.assertFalse(s.outputs()['permit'])
  w.advance(333);self.assertFalse(s.outputs()['permit'])
  w.input(333.5,0);w.input(334,1);self.assertFalse(s.outputs()['permit'])
  w.input(334.5,0);w.input(335,1);self.assertTrue(s.outputs()['permit'])

class Watchdog:
 """Ideal event-time missing-pulse timer, including startup delay and WDO pulse.
 Electrical propagation, undefined rails and synchronizer metastability are excluded.
 """
 def __init__(self,safety,timeout,pulse):
  self.safety=safety;self.timeout=timeout;self.pulse=pulse;self.level=0;self.next=timeout
 def advance(self,t):
  while t>=self.next:
   self.safety.wdo=1-self.safety.wdo;self.safety.clear()
   self.next+=self.timeout if self.safety.wdo else self.pulse
 def input(self,t,level):
  self.advance(t)
  if self.level!=level:
   self.level=level
   if self.safety.wdo:self.next=t+self.timeout
   if level:self.safety.edge()

def arithmetic():
 # Conservative reference band 0.400..0.410V, plus 0.1% divider resistors.
 rows=[]
 for rail,top in [(5,110000),(3.3,66500)]:rows.append({'rail_nominal_v':rail,'trip_nominal_v':.405*(1+top/10000),'trip_min_v':.400*(1+top*.999/(10000*1.001)),'trip_max_v':.410*(1+top*1.001/(10000*.999))})
 vb_min=4.4*(68000*.999)/(47000*1.001+68000*.999);vb_max=5.25*(68000*1.001)/(47000*.999+68000*1.001)
 assert vb_min>2.3 and vb_max<3.135
 return {'supervisor_dividers':rows,'reference_band_v':[.400,.410],'vbus_divider_v':[vb_min,vb_max],'i2c_150pf_rise_ns':.8473*2200*150e-12*1e9,'mix_each_gain':22000/100000,'fm_filter_hz':1/(2*3.141592653589793*470*2.2e-9),'limits':'Ideal resistor/reference bounds; actual threshold/hysteresis, transistor switching, RC and power ramps require measurement'}

def main():
 global PINFILE
 p=argparse.ArgumentParser();p.add_argument('--pins',type=Path,default=HERE.parents[2]/'fpga-standalone/boards/ulx3s/pins.json');p.add_argument('--output',type=Path,required=True);a=p.parse_args();PINFILE=a.pins
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(Tests));assert result.wasSuccessful()
 d=make(PINFILE);static=validate(d,json.loads(PINFILE.read_text()));erc=json.loads((HERE/'schematic/erc.json').read_text());violations=[v for s in erc['sheets'] for v in s['violations']]
 assert not violations,violations
 count=check_export(d,HERE/'schematic/netlist.xml');hashes={str(f.relative_to(HERE)):hashlib.sha256(f.read_bytes()).hexdigest() for f in [HERE/'design.py',HERE/'generate.py',HERE/'check.py',*sorted((HERE/'schematic').glob('*.kicad_sch')),HERE/'schematic/F1C.kicad_sym',HERE/'schematic/netlist.xml',HERE/'schematic/bom.csv',HERE/'schematic/assembly-extras.csv']}
 report={'schema_version':1,'kind':'Pin-level schematic/netlist/ERC plus ideal external stop logic review; no manufactured board','all_passed':True,'tests':result.testsRun,'erc_violations':0,'net_count':count,'static':static,'arithmetic':arithmetic(),'sources_sha256':hashes,'pcb_layout_done':False,'spice_done':False,'physical_acceptance':False,'host_changed':False,'pin_manifest_sha256':hashlib.sha256(PINFILE.read_bytes()).hexdigest()}
 a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print('PASS carrier review:',result.testsRun,'tests, ERC0; no physical acceptance')
if __name__=='__main__':main()
