#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build functional USB/CDC/MIDI + I2C/YM RTL models and ECP5 mapping.
No pin assignment, OS enumeration, USB electrical compliance or P&R signoff.
"""
import argparse,json,os,re,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path
from check_session import run,sha,test_suite
from tools.prepare_usbcore import prepare
HERE=Path(__file__).resolve().parent

def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=HERE.parent)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--regression',type=Path,help='Reuse an unchanged-source check_clocks.py summary from this run')
 a=p.parse_args();project=a.project.resolve();out=a.output.resolve();start=time.monotonic()
 if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty output directory')
 out.mkdir(parents=True,exist_ok=True);vendor=prepare(out/'vendor')
 env=dict(os.environ,F1_PROJECT=str(project));metadata=test_suite(out,'test_usb_metadata.py','metadata',env)
 if a.regression:
  regression=json.loads(a.regression.read_text())
  # The old entry points must match. USB/MIDI modules are unreachable from those
  # entry points; their final sources and the USB harness are rebuilt below.
  for path,digest in regression['sources_sha256'].items():
   if path.startswith('rtl/') and not Path(path).name.startswith(('revc_usb_','revc_midi_')) and sha(HERE/path)!=digest:raise ValueError('Changed regression RTL: '+path)
 else:
  run([sys.executable,HERE/'check_clocks.py','--project',project,'--output',out/'regression'],out/'regression.log',timeout=1800)
  regression=json.loads((out/'regression/summary.json').read_text())
 objects=[]
 for name,path in [('midi',project/'firmware-c/src/midi.c'),('wym1',project/'firmware-c/src/wym1.c'),('midi_bridge',project/'firmware-c/tests/midi_bridge.c')]:
  obj=out/(name+'.o');run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(project/'firmware-c/src'),'-c',path,'-o',obj],out/(name+'-cc.log'));objects.append(obj)
 def build(top,test,name,flags=(),shared=False,extra=()):
  target=out/('build-'+name)
  cmd=['verilator','--cc','--exe','--build','-j','4','-Wall','--top-module',top,'--Mdir',target,
   '-CFLAGS','-std=c++17'+(' -fPIC -DF1_CLOCKED -DF1_USB' if shared else ''),'-o',name+'.so' if shared else 'test',
   *flags,out/'vendor/vendor.vlt',*sorted((HERE/'rtl').glob('*.v')),*vendor,HERE/'tests'/test,*extra]
  if shared:cmd+=['-LDFLAGS','-shared']
  run(cmd,out/(name+'-build.log'));return target/(name+'.so' if shared else 'test')
 components={}
 for name,top,test,flags,extra in [
  ('midi','revc_midi_planner','midi_planner_test.cpp',[],objects),
  ('phy','revc_usb_composite','usb_phy_test.cpp',["-GVID=16'hcafe","-GPID=16'h4001"],[]),
  ('disabled','revc_usb_composite','usb_disabled_test.cpp',[],[])]:
  exe=build(top,test,name,flags,extra=extra);components[name]=run([exe],out/(name+'-test.log')).strip();print(components[name],flush=True)
 lib=build('revc_usb_ym_top','real_ym_bridge.cpp','usb', ["-GUSB_VID=16'hcafe","-GUSB_PID=16'h4001"],shared=True)
 env['F1_REAL_LIB']=str(lib)
 log=out/'integrated-tests.log'
 with log.open('w') as f:subprocess.run([sys.executable,'-m','unittest','discover','-s',HERE/'tests','-p','test_usb_ym.py','-v'],env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=1800)
 text=log.read_text();n=int(re.search(r'Ran (\d+) tests',text)[1]);assert re.search(r'^OK',text,re.M)
 integrated={'tests':n,'passed':n,'log_sha256':sha(log)};print('PASS integrated',integrated,flush=True)
 ys=out/'usb.ys';ys.write_text('read_verilog -sv '+' '.join(json.dumps(str(x)) for x in [*sorted((HERE/'rtl').glob('*.v')),*vendor])+ '\nchparam -set USB_VID 51966 -set USB_PID 16385 revc_usb_ym_top\nsynth_ecp5 -top revc_usb_ym_top -json '+json.dumps(str(out/'usb.json'))+'\ncheck -assert\ntee -o '+json.dumps(str(out/'stat.json'))+' stat -json\n')
 run(['yosys','-ql',out/'synthesis.log',ys],out/'synthesis-console.log')
 print(run([sys.executable,HERE/'check_real_cdc.py',out/'usb.json','--usb','--output',out/'cdc.json'],out/'cdc.log').strip(),flush=True)
 files=[*sorted((HERE/'rtl').glob('*.v')),*sorted((HERE/'tests').glob('*.cpp')),*sorted((HERE/'tests').glob('*.h')),*sorted((HERE/'tests').glob('test_*.py')),*sorted((HERE/'tools').glob('*.py')),*sorted(HERE.glob('check*.py')),*sorted((HERE/'vendor/usbcorev').rglob('*'))]
 files=[f for f in files if f.is_file() and '__pycache__' not in f.parts]
 host_files=sorted((project/'firmware-c/host').rglob('*.py'))
 result={'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),'kind':'USB FS CDC/MIDI functional RTL + I2C/Si5351/real-YM behavioral integration; not physical acceptance',
 'tools':regression['tools'],'sources_sha256':{str(x.relative_to(HERE)):sha(x) for x in files},
 'unchanged_host_sha256':{str(x.relative_to(project)):sha(x) for x in host_files},
 'c_oracle_sha256':{str(x.relative_to(project)):sha(x) for x in [project/'firmware-c/src/midi.c',project/'firmware-c/src/midi_pitch.h',project/'firmware-c/src/wym1.c',project/'firmware-c/tests/midi_bridge.c']},
 'vendor':json.loads((HERE/'vendor/usbcorev/upstream.json').read_text()),'metadata':metadata,'components':components,'integrated':integrated,
 'regression':regression,'regression_reuse_scope':'SHA check for all old-top reachable RTL; unreachable USB/MIDI modules and USB harness rebuilt for this report','synthesis':json.loads((out/'stat.json').read_text())['design'],'clock_boundary_structure':json.loads((out/'cdc.json').read_text()),
 'configuration':{'usb_hz':48000000,'audio_hz':49152000,'midi_ym_hz':4000000,'i2c_address':'0x42','i2c_protocol':2,'simulation_only_vid_pid':'cafe:4001','production_id_defaults':'0000:0000, USB detached','sof_timeout_us':3000,'midi_quarantine_us':200000},
 'place_route':'not run','timing_measured':False,'physical_pins_assigned':False,'os_enumeration_tested':False,'usb_electrical_compliance_tested':False,
 'limits':['Ideal USB bit-level host and synthetic register/serial peripherals; not an OS, analog PLL, USB pad or real YM model.',
 'No allocated production VID/PID or board-specific USB transceiver, VBUS detection, pull-up, constraints or external inhibit selection.',
 'MIDI subset: six monophonic voices, Note On/Off, velocity-zero Off, CC120/123 and System Reset; fixed amplitude, no GM/program/pitch bend/sustain/SysEx.',
 'CDC subset: status/help/stop/s/Ctrl+C/panic; no REPL, file upload, embedded play/test, fm/bus/profile console commands or MCU reset commands.',
 'All endpoint payloads are at most 64 bytes; single buffered OUT per class, with normal USB NAK backpressure.',
 'Limited structural CDC audit only; no exhaustive CDC, STA, Fmax, place/route, USB certification or physical acceptance.'],
 'wall_seconds':round(time.monotonic()-start,3)}
 (out/'summary.json').write_text(json.dumps(result,indent=2)+'\n');print('PASS USB ECP5 mapping:',result['synthesis']['num_cells_by_type'])
if __name__=='__main__':main()
