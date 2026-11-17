#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check split contracts, physical pad numbers and explicitly assumed design budgets."""
import argparse,hashlib,json,math,re,sys,unittest
from pathlib import Path
from check import ContractTests,validate
from design import HERE,REFERENCE,PINFILE,make

def budgets():
 # Retain reviewB259.4mA entirely, even though some loads moved onto the module.
 # Adding the whole20mA module allowance is deliberately conservative (some double counting).
 pga=259.4+20;aux=150;input5=674.4+20+(180-150)+4
 # Bound includes a full rail-sized SSG transition, not just half of a steady square wave.
 peak_in=3*5.25+(2.2+2.0)*math.sqrt(2)
 gain_max=(8200*1.01)/(100000*.99)
 peak_out=peak_in*gain_max
 center_min=4.75*.99/(1.01+.99)
 room=center_min-.30
 assert pga<300 and aux<500 and input5<1100
 assert peak_out<room
 return dict(scope='design allocations and linear bound; NOT measurements or guaranteed whole-system limits',module_5v_allocation_ma=180,module_3v3_io_allocation_ma=20,pga_3v3_conservative_ma=round(pga,1),pga_regulator_rating_ma=300,aux_3v3_ma=aux,aux_regulator_rating_ma=500,external5v_conservative_ma=round(input5,1),supply_target_ma=1500,ptc_hold_nominal_ma=1100,headroom=dict(ssg_bound_each_peak_v=5.25,ssg_bound_includes_dc_steps=True,dac_assumed_max_rms_v=2.2,aux_limit_rms_v=2.0,feedback_ohms=8200,input_ohms=100000,tolerance_fraction=.01,gain_max=round(gain_max,5),sum_output_peak_bound_v=round(peak_out,3),available_peak_v=round(room,3),remaining_peak_margin_v=round(room-peak_out,3),qualifications='No SPICE or analog measurements; verify output loading, startup, rail drop, distortion, AUX DC and real chip output. Overall gain is lower than reviewB; FM/SSG ratio retained.'))

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--footprints',type=Path);args=p.parse_args()
 libs=args.footprints
 if libs is None:
  libs=next((x for x in [Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints'),Path('/usr/share/kicad/footprints'),Path('/opt/homebrew/share/kicad/footprints')] if x.is_dir()),None)
 if libs is None:raise SystemExit('Provide --footprints with the KiCad10 library directory')
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(ContractTests))
 if not result.wasSuccessful():raise SystemExit(1)
 custom=HERE.parent/'carrier-p2/pcb-review-b/schematic/P2C.pretty';parts=0
 for board,d in make().items():
  assert json.loads((HERE/board/'circuit.json').read_text())==d,'Regenerate native schematics first'
  for p in d['parts']:
   lib,name=p['footprint'].split(':');f=(custom if lib=='P2C' else libs/(lib+'.pretty'))/(name+'.kicad_mod')
   if not f.is_file():raise ValueError('Missing footprint '+p['footprint'])
   pads=set(re.findall(r'\(pad\s+"([^\"]+)"',f.read_text()))
   if not {x['num'] for x in p['pins']}<=pads:raise ValueError('Footprint pin mismatch '+board+'/'+p['ref'])
   parts+=1
 native=json.loads((HERE/'verification.json').read_text())
 assert native['kicad_version']=='10.0.5'
 assert all(v['erc_violations']==0 for v in native['boards'].values())
 report=dict(schema_version=1,date='2026-11-16',python=sys.version.split()[0],native_kicad=native['kicad_version'],contract_tests_passed=result.testsRun,physical_pad_sets_checked=parts,native_gpio_used=47,native_gpio_changed=False,firmware_implemented=False,pcb_created=False,hardware_accepted=False,source_sha256={str(p.relative_to(HERE.parent)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [REFERENCE,PINFILE]},budgets=budgets(),scope='ERC/netlist/pad/contract checks and design budgets only; no firmware runtime, PCB DRC or bench acceptance')
 (HERE/'static-checks.json').write_text(json.dumps(report,indent=2)+'\n')
 print('PASS split contract,195 physical pad sets and declared power/headroom budgets')
