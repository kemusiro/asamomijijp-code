#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""USB-integrated ECP5 OOC place/route and internal-clock timing verification.
No physical pin assignment, clock-tree/pad/board timing signoff or bitstream.
"""
import argparse,copy,json,os,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from check_session import run,sha,test_suite
from tools.prepare_usbcore import prepare
from tools.pnr_checks import timing,stage_delays
from check_pnr_cdc import census
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=HERE.parent)
 p.add_argument('--nextpnr',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
 p.add_argument('--functional-report',type=Path,help='Reuse passed current-RTL functional regression; all recorded source hashes are checked')
 p.add_argument('--seeds',type=int,nargs='+',default=[1,2,3]);p.add_argument('--jobs',type=int,default=2)
 a=p.parse_args();out=a.output.resolve();start=time.monotonic();project=a.project.resolve();pnr=a.nextpnr.resolve()
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty output directory')
 if len(set(a.seeds))<3:raise ValueError('At least three distinct seeds required')
 if a.jobs<1 or a.jobs>3:raise ValueError('Use 1..3 concurrent jobs')
 out.mkdir(parents=True,exist_ok=True)
 if a.functional_report:
  functional=json.loads(a.functional_report.read_text())
  if not functional.get('all_passed',False):raise ValueError('Functional tests did not pass')
  for rel,digest in functional['sources_sha256'].items():
   if sha(HERE/rel)!=digest:raise ValueError('Changed tested source: '+rel)
  for group in ['unchanged_host_sha256','c_oracle_sha256']:
   for rel,digest in functional[group].items():
    if sha(project/rel)!=digest:raise ValueError('Changed HOST/C oracle: '+rel)
 else:
  run([sys.executable,HERE/'check_usb.py','--project',project,'--output',out/'functional'],out/'functional.log',timeout=3600)
  f=json.loads((out/'functional/summary.json').read_text());functional=dict(f,all_passed=True)
 env=dict(os.environ,F1_PROJECT=str(project),PYTHONPATH=str(HERE));unit=test_suite(out,'test_pnr_checks.py','report-checks',env)
 vendor=prepare(out/'vendor');rtl=sorted((HERE/'rtl').glob('*.v'))
 ys=out/'synth.ys';ys.write_text('read_verilog -sv '+' '.join(json.dumps(str(x)) for x in [*rtl,*vendor])+ '\nchparam -set USB_VID 51966 -set USB_PID 16385 revc_usb_ym_top\nsynth_ecp5 -top revc_usb_ym_top -json '+json.dumps(str(out/'mapped.json'))+'\ncheck -assert\ntee -o '+json.dumps(str(out/'stat.json'))+' stat -json\n')
 run(['yosys','-ql',out/'synthesis.log',ys],out/'synthesis-console.log')
 run([sys.executable,HERE/'check_real_cdc.py',out/'mapped.json','--usb','--output',out/'cdc.json'],out/'cdc.log')
 module=json.loads((out/'mapped.json').read_text())['modules']['revc_usb_ym_top'];crossings=census(module)
 # Demonstrate that direct cross-domain data and enable bypasses fail the census.
 mutations=0
 q=module['netnames']['board.real_ym.backend.audio_heartbeat']['bits'][0]
 sink=next(n for n,c in module['cells'].items() if c['type']=='TRELLIS_FF' and c['connections']['CLK']==module['ports']['clk']['bits'] and n.startswith('midi.') and c['parameters'].get('CEMUX')=='CE' and 'CE' in c['connections'])
 for port in ['DI','CE']:
  bad=copy.deepcopy(module);bad['cells'][sink]['connections'][port]=[q];bad['cells'][sink]['port_directions'][port]='input'
  try:census(bad)
  except ValueError:mutations+=1
  else:raise RuntimeError('CDC bypass mutation was not detected')
 crossings['bypass_mutations_rejected']=mutations
 (out/'crossings.json').write_text(json.dumps(crossings,indent=2)+'\n')
 sdc=HERE/'constraints/ecp5-ooc.sdc'
 def route(seed):
  d=out/('seed-'+str(seed));d.mkdir();cmd=[pnr,'--85k','--package','CABGA381','--speed','6','--out-of-context',
   '--json',out/'mapped.json','--sdc',sdc,'--seed',str(seed),'--freq','49.152','--report',d/'report.json',
   '--write',d/'routed.json','--detailed-timing-report']
  # No --force, --ignore-loops, --ignore-rel-clk, or --timing-allow-fail.
  with (d/'run.log').open('w') as log:subprocess.run([str(x) for x in cmd],stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1800)
  r=json.loads((d/'report.json').read_text());result=timing(r);result['interstage']=stage_delays(module,r)
  result.update({'seed':seed,'report_sha256':sha(d/'report.json'),'routed_sha256':sha(d/'routed.json'),'log_sha256':sha(d/'run.log')})
  print('PASS seed',seed,{n:x['fmax_mhz'] for n,x in result['clocks'].items()},flush=True);return result
 with ThreadPoolExecutor(max_workers=a.jobs) as pool:routes=list(pool.map(route,a.seeds))
 tools={}
 for name,executable,flags in [('nextpnr-ecp5',pnr,['--version']),('yosys',Path(__import__('shutil').which('yosys')),['-V'])]:
  tools[name]={'version':run([executable,*flags],out/(name+'-version.log')).strip(),'sha256':sha(executable)}
 # Bundle executable+chipdb hashes with the pinned archive metadata when available.
 chipdb=pnr.parent.parent/'share/nextpnr/ecp5/chipdb-85k.bin'
 if chipdb.exists():tools['chipdb_85k_sha256']=sha(chipdb)
 files=[*rtl,*sorted((HERE/'tests').glob('*.cpp')),*sorted((HERE/'tests').glob('*.h')),*sorted((HERE/'tests').glob('test_*.py')),
  *sorted((HERE/'tools').glob('*.py')),*sorted(HERE.glob('check*.py')),sdc,HERE/'toolchain-pnr-lock.json',
  *[f for f in (HERE/'vendor/usbcorev').rglob('*') if f.is_file() and '__pycache__' not in f.parts]]
 result={'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),'kind':'ECP5 USB-integrated out-of-context routed internal timing; not board signoff',
  'configuration':{'device':'LFE5U-85F','package_context':'CABGA381','speed_grade':6,'mode':'out-of-context','seeds':a.seeds,
   'control_usb_mhz':48,'audio_mhz':49.152,'simulation_only_vid_pid':'cafe:4001','physical_io_allocated':False,'global_clocks_routed':False},
  'sources_sha256':{str(x.relative_to(HERE)):sha(x) for x in files},'tools':tools,'distribution_lock':json.loads((HERE/'toolchain-pnr-lock.json').read_text()),
  'functional_regression':functional,'report_acceptance_tests':unit,'synthesis':json.loads((out/'stat.json').read_text())['design'],
  'direct_pair_audit':json.loads((out/'cdc.json').read_text()),'mapped_ff_crossings':crossings,'routes':routes,
  'all_internal_clock_targets_met':True,'physical_pin_assignment':False,'bitstream_generated':False,'hardware_programmed':False,
  'timing_analyzed':True,'timing_measured':False,
  'limits':['Experimental nextpnr OOC mode: logic data routes only; clocks are ideal and IO buffers/global promotion/routing are disabled.',
   'No assigned module pins, pad/USB/translator/PCB/Si5351 electrical timing, clock skew/jitter/uncertainty, hold or reset recovery/removal signoff.',
   'No unsupported SDC false-path waiver, broad clock-group cutoff, timing-allow-fail or ignored loop/related-clock option used.',
   'Mapped FF D/CE/LSR census is complete only for its listed cell types. Bundled rate configuration relies on documented stable-during-reset protocol; no physical MTBF proof.',
   'MIDI USB detach/reset/suspend stops only MIDI; I2C owner continues. HOST wire format remains unchanged.',
   'Tool-estimated internal Fmax and utilization are not full-board operating-frequency or physical audio acceptance.'],
  'wall_seconds':round(time.monotonic()-start,3)}
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS all routed internal targets; physical signoff remains separate')
if __name__=='__main__':main()
