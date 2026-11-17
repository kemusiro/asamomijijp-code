#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Physical ULX3S 85F pads/PLL/globals P&R; estimated timing, not board acceptance."""
import argparse,json,os,sys,time,subprocess,shutil
from datetime import datetime,timezone
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from check_session import run,sha
from tools.prepare_usbcore import prepare
from tools.board_checks import lpf,mapped_checks,routed_checks
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__)
 p.add_argument('--project',type=Path,default=HERE.parent);p.add_argument('--nextpnr',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--functional-report',type=Path)
 p.add_argument('--seeds',type=int,nargs='+',default=[1,2,3]);p.add_argument('--jobs',type=int,default=2)
 p.add_argument('--write-constraints',action='store_true');a=p.parse_args();start=time.monotonic()
 if len(set(a.seeds))<3 or not 1<=a.jobs<=3:raise ValueError('Three distinct seeds; jobs 1..3')
 out=a.output.resolve();project=a.project.resolve();pnr=a.nextpnr.resolve();board=HERE/'boards/ulx3s'
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty output directory')
 out.mkdir(parents=True,exist_ok=True)
 manifest=json.loads((board/'pins.json').read_text());generated=lpf(manifest)
 if a.write_constraints:(board/'board.lpf').write_text(generated)
 if (board/'board.lpf').read_text()!=generated:raise ValueError('Regenerate constraints with --write-constraints')
 if a.functional_report:
  f=json.loads(a.functional_report.read_text());embedded=f.get('source_report',f)
  if not f.get('all_passed') or not embedded.get('all_passed'):raise ValueError('Failed functional report')
  for root,entries in [(HERE,embedded['sources_sha256']),(project,embedded['unchanged_host_sha256']),(project,embedded['c_oracle_sha256'])]:
   for rel,digest in entries.items():
    if sha(root/rel)!=digest:raise ValueError('Changed tested file: '+rel)
  functional={'report_sha256':sha(a.functional_report),'reuse_scope':'Every recorded source/HOST/C oracle hash checked; unchanged core functional evidence reused','report':f}
 else:
  run([sys.executable,HERE/'check_usb.py','--project',project,'--output',out/'functional'],out/'functional.log',timeout=3600)
  functional={'report':json.loads((out/'functional/summary.json').read_text()),'reuse_scope':'Fresh full functional run'}
 env=dict(os.environ,F1_PROJECT=str(project),PYTHONPATH=str(HERE))
 run([sys.executable,'-m','unittest','discover','-s',HERE/'tests','-p','test_board_checks.py','-v'],out/'report-tests.log',env=env)
 adapter=out/'adapter'
 run(['verilator','--cc','--exe','--build','-j','4','--top-module','revc_ulx3s_top','--Mdir',adapter,
  '-Wno-fatal',board/'top.v',HERE/'rtl/revc_domain_reset.v',HERE/'tests/ulx3s_stubs.v',HERE/'tests/ulx3s_adapter_test.cpp'],out/'adapter-build.log')
 adapter_result=run([adapter/'Vrevc_ulx3s_top'],out/'adapter-test.log').strip();print(adapter_result,flush=True)
 vendor=prepare(out/'vendor');files=[*sorted((HERE/'rtl').glob('*.v')),board/'clocking.v',board/'top.v',*vendor]
 ys=out/'synth.ys';ys.write_text('read_verilog -sv '+' '.join(json.dumps(str(f)) for f in files)+'\nchparam -set USB_VID 51966 -set USB_PID 16385 revc_ulx3s_top\nsynth_ecp5 -top revc_ulx3s_top -json '+json.dumps(str(out/'mapped.json'))+'\ncheck -assert\ntee -o '+json.dumps(str(out/'stat.json'))+' stat -json\n')
 run(['yosys','-ql',out/'synthesis.log',ys],out/'synth-console.log')
 mapped=json.loads((out/'mapped.json').read_text())['modules']['revc_ulx3s_top'];audit=mapped_checks(mapped)
 (out/'mapped-audit.json').write_text(json.dumps(audit,indent=2)+'\n');print('PASS mapped physical top',audit['ff_cones']['ff_bits_checked'],flush=True)
 def route(seed):
  d=out/('seed-'+str(seed));d.mkdir();ev=dict(os.environ,F1_CLOCK_ROUTES=str(d/'clock-routes.json'))
  cmd=[pnr,'--85k','--package','CABGA381','--speed','6','--json',out/'mapped.json','--lpf',board/'board.lpf','--sdc',board/'board.sdc',
    '--seed',str(seed),'--report',d/'report.json','--write',d/'routed.json','--detailed-timing-report','--post-route',board/'clock_routes.py']
  run(cmd,d/'run.log',env=ev,timeout=1800)
  rpt=json.loads((d/'report.json').read_text());routed=json.loads((d/'routed.json').read_text())['modules']['top']
  checks=routed_checks(rpt,routed,manifest,mapped,json.loads((d/'clock-routes.json').read_text()))
  checks.update(seed=seed,files_sha256={n:sha(d/n) for n in ['report.json','routed.json','run.log','clock-routes.json']})
  (d/'checks.json').write_text(json.dumps(checks,indent=2)+'\n');print('PASS seed',seed,{k:round(v['fmax_mhz'],3) for k,v in checks['clocks'].items()},flush=True);return checks
 with ThreadPoolExecutor(max_workers=a.jobs) as pool:routes=list(pool.map(route,a.seeds))
 files=[*sorted((HERE/'rtl').glob('*.v')),*[f for f in board.iterdir() if f.is_file()],HERE/'check_board.py',HERE/'tools/board_checks.py',HERE/'tests/test_board_checks.py',HERE/'tests/ulx3s_adapter_test.cpp',HERE/'tests/ulx3s_stubs.v']
 tools={n:{'version':run([exe,flag],out/(n+'-version.log')).strip(),'sha256':sha(exe)} for n,exe,flag in [('yosys',Path(shutil.which('yosys')),'-V'),('nextpnr',pnr,'--version'),('verilator',Path(shutil.which('verilator')),'--version')]}
 result={'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),'kind':'Physical ULX3S 85F v3.0.8 normal P&R with IO/PLL/global routes; not hardware signoff',
  'all_passed':True,'configuration':manifest,'sources_sha256':{str(f.relative_to(HERE)):sha(f) for f in files},'tools':tools,
  'toolchain_distribution':json.loads((HERE/'toolchain-pnr-lock.json').read_text()),'functional_regression':functional,'adapter_test':adapter_result,
  'mapped_audit':audit,'synthesis':json.loads((out/'stat.json').read_text())['design'],'routes':routes,'physical_io_allocated':True,'global_clocks_routed':True,
  'bitstream_generated':False,'hardware_programmed':False,'hardware_tested':False,'usb_electrical_compliance':False,
  'limits':['Global distribution is physically routed but its delay is zero in the pinned nextpnr ECP5 model: no silicon clock insertion/skew proof.',
   'Pad-net route bounds and I2S setup/hold design budget include explicit external allowances, not characterized pad/translator/PCB/DAC/USB timing.',
   'PLL ratio/PFD/VCO checked statically; lock, jitter, frequency accuracy and reset recovery/removal require physical/vendor validation.',
   'No blanket false paths, asynchronous-group cut, OOC, timing-allow-fail or ignored timing loop option.',
   'USB IDs cafe:4001 are model-only; defaults remain detached. US2 VBUS isolation/sense, hardware supervisor and external mute/translator circuits are required.',
   'Existing HOST/wire format unchanged. STOP/lease/ownership/detach evidence is digital-model verification; F1 hardware acceptance remains pending.'],
  'wall_seconds':round(time.monotonic()-start,3)}
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS physical pad/PLL/global route evaluation; hardware/electrical limits recorded',flush=True)
if __name__=='__main__':main()
