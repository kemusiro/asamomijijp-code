#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create a portable, source-only Diamond review bundle. Run on the preparation host.
GNU patch is needed here, not on the Windows Diamond host receiving the bundle.
"""
import argparse,csv,hashlib,json,re,shutil,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent
F1=HERE.parents[2]
sys.path.insert(0,str(F1/'tools'))
from prepare_usbcore import prepare as prepare_vendor

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def wrapper(pins):
 ports={}
 for p in pins:
  m=re.fullmatch(r'(\w+)(?:\[(\d+)\])?',p['port']);name,index=m.groups();n=0 if index is None else int(index)+1
  if name in ports:
   assert ports[name][0]==p['direction'];n=max(n,ports[name][1])
  ports[name]=(p['direction'],n)
 lines=[d+' wire '+('['+str(n-1)+':0] ' if n else '')+name for name,(d,n) in ports.items()]
 return '// SPDX-License-Identifier: MIT\n// REPORT-ONLY model IDs; never generate/program a bitstream from this bundle.\nmodule revc_ulx3s_diamond_top(\n '+',\n '.join(lines)+'\n);\n (* syn_hier="hard" *) revc_ulx3s_top #(.USB_VID(16\'hcafe),.USB_PID(16\'h4001)) dut (\n '+',\n '.join('.'+n+'('+n+')' for n in ports)+'\n );\nendmodule\n'

def prepare(out):
 out=Path(out).resolve()
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty bundle directory')
 out.mkdir(parents=True,exist_ok=True);src=out/'src';src.mkdir()
 board=HERE.parent;manifest=json.loads((board/'pins.json').read_text());origins={}
 for f in [*sorted((F1/'rtl').glob('*.v')),board/'top.v',board/'clocking.v']:
  target=src/(f.stem+'.sv');shutil.copyfile(f,target);origins[str(target.relative_to(out))]={'source':str(f.relative_to(F1)),'sha256':sha(f)}
 vendor=prepare_vendor(out/'vendor-original-patched')
 for f in vendor:
  target=src/('vendor_'+f.stem+'.sv');shutil.copyfile(f,target)
  origins[str(target.relative_to(out))]={'source':'vendor/usbcorev/'+f.name+' + patches/f1-validation.patch','sha256':sha(f)}
 # Preserve original upstream licensing; generated vendor copies are not relicensed.
 shutil.copyfile(F1/'vendor/usbcorev/LICENSE',out/'USB_CORE_LICENSE')
 shutil.copyfile(F1.parent/'LICENSE',out/'PROJECT_LICENSE')
 shutil.copyfile(F1/'vendor/usbcorev/upstream.json',out/'usbcore-upstream.json')
 shutil.copyfile(F1/'vendor/usbcorev/patches/f1-validation.patch',out/'usbcore-f1-validation.patch')
 shutil.rmtree(out/'vendor-original-patched')
 (src/'diamond_top.sv').write_text(wrapper(manifest['pins']))
 clocks='''\n# Physical clocks; do not copy the nextpnr 50MHz margin as the PLL output ratio.
FREQUENCY PORT "ref12" 12.000 MHz;
FREQUENCY PORT "audio49" 49.152 MHz;
# PROVISIONAL hierarchical name: resolve in Spreadsheet View after Translate.
# If unmatched, replace with the actual CLKOP net and record it in timing-review.json.
FREQUENCY NET "dut/clk" 48.000 MHz;
# No blanket asynchronous/reset exclusions. IO budgets are in io-review.csv.
'''
 (out/'carrier.lpf').write_text((board/'board.lpf').read_text()+clocks)
 (out/'synthesis.sdc').write_text('''# Primary input clocks for synthesis. Derived PLL clock must be checked after Translate.
create_clock -name ref12 -period 83.333333333333 [get_ports ref12]
create_clock -name audio49 -period 20.345052083333 [get_ports audio49]
# No asynchronous clock-group or whole-reset false paths.
''')
 for name in ['project.tcl','route.tcl','collect.py','README.md']:shutil.copyfile(HERE/name,out/name)
 shutil.copyfile(board/'pins.json',out/'pins.json')
 shutil.copyfile(board/'UPSTREAM-LICENSE.md',out/'ULX3S_UPSTREAM_LICENSE.md')
 with (out/'io-review.csv').open('w',newline='') as f:
  w=csv.writer(f);w.writerow(['port','ball','direction','group','timing_scope','external_budget','status'])
  for p in manifest['pins']:
   g=p['group'];scope='Asynchronous primary IO; inspect actual synchronizer/enable and pad timing; no blanket clock cut'
   budget='Characterize buffer/level translator/load and trace delay'
   if p['port']=='ref12':scope='PLL dedicated input/P3; verify insertion jitter lock and reset recovery';budget='12MHz; +/-50ppm design target; P3 10-90% rise/fall <=1ns to verify'
   elif p['port']=='audio49':scope='Independent primary audio global clock';budget='49.152MHz from Si5351 CLK1; characterize jitter and DCCA insertion'
   elif p['port'].startswith('i2s_'):scope='Source-synchronous to forwarded BCLK rising edge; setup AND hold at DAC';budget='Design allowance: pad skew4ns + PCB skew2ns + receiver setup/hold10ns EACH; replace with characterized limits'
   elif g=='usb':scope='USB asynchronous pins and output enable/bias; inspect oversampling and pad timing';budget='12Mb/s full-speed signal-integrity and USB electrical measurements pending'
   w.writerow([p['port'],p['ball'],p['direction'],g,scope,budget,'UNREVIEWED'])
 review={'schema_version':1,'vendor_execution':False,'timing_closed':False,'diamond_version':None,'synplify_version':None,'device':manifest['device'],
  'pll':{'reference_mhz':12,'input_divider':1,'feedback_divider':4,'output_divider':12,'vco_mhz':576,'actual_output_mhz':48,'resolved_clkop_net':None,'actual_constraint_applied':None},
  'checks':{n:None for n in ['all_49_pads_matched','native_obz_dn_bias_T_high','pll_and_two_global_clock_routes','all_clock_constraints_matched','setup_all_corners','hold_all_corners','recovery_removal','clock_insertion_skew_jitter_budget','cdc_first_stage_endpoint_review','fifo_gray_and_bundled_stable_crossings','async_assert_sync_release','external_io_setup_hold','usb_enable_and_bias_paths','no_unexplained_unconstrained_paths','no_blanket_clock_or_reset_waivers','warnings_disposition']},
  'exceptions':[],'unconstrained_path_dispositions':[],'report_sha256':{},'scope':'Template only. No digital or electrical signoff until actual vendor reports and external budgets are reviewed.'}
 (out/'timing-review.json').write_text(json.dumps(review,indent=2)+'\n')
 hashes={str(f.relative_to(out)):sha(f) for f in sorted(out.rglob('*')) if f.is_file()}
 data={'schema_version':1,'kind':'Portable source-only Diamond preparation; not a vendor run','vendor_execution':False,'timing_closed':False,'physical_acceptance':False,'bitstream_generated':False,'device':manifest['device'],'physical_pads':len(manifest['pins']),'model_only_usb_ids':'cafe:4001','sources':origins,'files_sha256':hashes,'upstream_patch_sha256':sha(F1/'vendor/usbcorev/patches/f1-validation.patch')}
 (out/'bundle-manifest.json').write_text(json.dumps(data,indent=2)+'\n')
 return data

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();m=prepare(a.output);print('Prepared',len(m['sources']),'RTL sources;49 pads;vendor execution=False;timing closure=False')
