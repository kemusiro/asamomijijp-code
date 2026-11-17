#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify Si5351 startup, variable-clock audio, unchanged HOST and ECP5 mapping."""
import argparse
from datetime import datetime,timezone
import json,os
from pathlib import Path
import sys,time
from check_session import run,sha,test_suite
HERE=Path(__file__).resolve().parent


def build(output,top,test,name,flags=(),shared=False):
    target=output/('build-'+name)
    cmd=['verilator','--cc','--exe','--build','-j','4','-Wall','--top-module',top,'--Mdir',target,
         '-CFLAGS','-std=c++17'+(' -fPIC -DF1_CLOCKED' if shared else ''),
         '-o',name+'.so' if shared else 'test',*flags,*sorted((HERE/'rtl').glob('*.v')),HERE/'tests'/test]
    if shared:cmd+=['-LDFLAGS','-shared']
    run(cmd,output/(name+'-build.log'))
    return target/(name+'.so' if shared else 'test')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,default=HERE.parent)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--private-score',type=Path)
    a=p.parse_args();project=a.project.resolve();out=a.output.resolve();start=time.monotonic()
    if out.exists() and any(out.iterdir()):raise FileExistsError('Use an empty output directory')
    out.mkdir(parents=True,exist_ok=True)
    old=[sys.executable,HERE/'check_audio.py','--project',project,'--output',out/'audio']
    if a.private_score:old+=['--private-score',a.private_score.resolve()]
    print(run(old,out/'audio-check.log',timeout=1800).strip(),flush=True)
    env=dict(os.environ,F1_PROJECT=str(project));plan=test_suite(out,'test_clock_plans.py','plans',env)
    tests={}
    for name,top,test,flags in [
        ('manager','revc_si5351_manager','clock_manager_test.cpp',[]),
        ('variable-pcm','revc_fm_pcm','variable_pcm_test.cpp',['-GSTEP_NUM=4000000','-GSTEP_DEN=3456000','-GDYNAMIC_STEP=1']),
        ('variable-audio','revc_audio_path','variable_audio_test.cpp',['-GDYNAMIC_CLOCK=1'])]:
        executable=build(out,top,test,name,flags)
        tests[name]=run([executable],out/(name+'-test.log')).strip();print(tests[name],flush=True)
    lib=build(out,'revc_clocked_ym_top','real_ym_bridge.cpp','clocked',shared=True)
    env['F1_REAL_LIB']=str(lib);integrated=test_suite(out,'test_clocked_ym.py','clocked',env,timeout=900)
    ys=out/'clocked.ys'
    ys.write_text('read_verilog -sv '+' '.join(json.dumps(str(x)) for x in sorted((HERE/'rtl').glob('*.v')))+'\n'
        'synth_ecp5 -top revc_clocked_ym_top -json '+json.dumps(str(out/'clocked.json'))+'\n'
        'check -assert\ntee -o '+json.dumps(str(out/'stat.json'))+' stat -json\n')
    run(['yosys','-ql',out/'synthesis.log',ys],out/'synthesis-console.log')
    print(run([sys.executable,HERE/'check_real_cdc.py',out/'clocked.json','--clocked','--output',out/'cdc.json'],out/'cdc.log').strip(),flush=True)
    audio=json.loads((out/'audio/summary.json').read_text())
    files=[*sorted((HERE/'rtl').glob('*.v')),*sorted((HERE/'tests').glob('*.cpp')),*sorted((HERE/'tests').glob('*.h')),
           *sorted((HERE/'tests').glob('test_*.py')),*sorted((HERE/'tools').glob('*.py')),*sorted(HERE.glob('check*.py'))]
    summary={
        'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),
        'kind':'Si5351A startup/variable-clock RTL simulation and ECP5 mapping; not physical acceptance',
        'tools':audio['tools'],'python_version':sys.version.split()[0],
        'sources_sha256':{str(x.relative_to(HERE)):sha(x) for x in files},
        'unchanged_host_sha256':audio['unchanged_host_sha256'],'c_oracle_sha256':audio['c_oracle_sha256'],
        'audio_regression':audio,'plan_tests':plan,'components':tests,'integrated':integrated,
        'synthesis':json.loads((out/'stat.json').read_text())['design'],
        'clock_boundary_structure':json.loads((out/'cdc.json').read_text()),
        'configuration':{'control_hz':48000000,'audio_hz':49152000,'xtal_hz':25000000,'load_pf':10,
            'profile_hz':[4000000,3579545,3993600,3000000,2000000,1500000,2500000,3500000],
            'src_den':3456000,'si5351_address':'0x60','si5351_model_bus_hz':100000,'host_address':'0x42',
            'host_protocol':2,'host_accepted_clock_hz':4000000,'status_poll_ms':5},
        'place_route':'not run','timing_measured':False,'physical_pins_assigned':False,
        'limits':['Clock profiles are selected through a synchronous internal RTL interface; no new public HOST command.',
                  'Legacy HOST/v2 remains 4MHz-only; other selected profiles reject its BEGIN with DATA6.',
                  'Generator handles integer-Hz plans within 1.5..4MHz; initial ROM has eight profiles, not arbitrary runtime Hz.',
                  '25/27MHz register arithmetic is verified; integrated behavioral peripheral uses 25MHz nominal.',
                  'Synthetic Si5351/YM peripherals model registers/buses/ideal serial timing, not analog PLL jitter or real silicon.',
                  'Optional full YsII is control-model event/CRC validation, not full-song physical audio acceptance.',
                  'Structural synchronizer checks are limited; no exhaustive CDC/MTBF/STA or physical timing signoff.',
                  'Module/pins, voltage/clock levels, final external inhibit, USB/MIDI and real hardware acceptance remain outstanding.'],
        'wall_seconds':round(time.monotonic()-start,3)}
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS clocked-YM ECP5 mapping:',summary['synthesis']['num_cells_by_type'],flush=True)


if __name__=='__main__':main()
