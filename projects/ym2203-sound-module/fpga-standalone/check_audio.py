#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the F1 real-YM path; no board programming or hardware acceptance."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from check_session import sha, run, build_bridge, test_suite

HERE=Path(__file__).resolve().parent


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=HERE.parent)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--private-score',type=Path)
    a=p.parse_args();project=a.project.resolve();output=a.output.resolve()
    if output.exists() and any(output.iterdir()):raise FileExistsError('Use an empty output directory')
    output.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    control=[sys.executable,HERE/'check_session.py','--project',project,'--output',output/'control']
    if a.private_score:control.extend(['--private-score',a.private_score.resolve()])
    print(run(control,output/'control-check.log').strip(),flush=True)
    oracle=output/'wym1.o';source=project/'firmware-c/src'
    run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-I'+str(source),'-c',source/'wym1.c','-o',oracle],output/'pcm-oracle-build.log')
    component={}
    for name,top in [('pcm','revc_fm_pcm'),('bus','revc_ym_bus'),('i2s','revc_i2s_tx'),('audio_path','revc_audio_path')]:
        build=output/('build-'+name)
        command=['verilator','--cc','--exe','--build','-j','4','-Wall','--top-module',top,
                 '--Mdir',build,'-CFLAGS','-std=c++17 -I'+str(source),'-o','test',
                 *sorted((HERE/'rtl').glob('*.v')),HERE/'tests'/(name+'_test.cpp')]
        if name=='pcm':command.extend(['-LDFLAGS',str(oracle)])
        run(command,output/(name+'-build.log'))
        component[name]=run([build/'test'],output/(name+'-test.log')).strip()
        print(component[name],flush=True)
    lib=build_bridge(output,'revc_real_ym_top','real_ym_bridge.cpp','real')
    env=dict(os.environ,F1_PROJECT=str(project),F1_REAL_LIB=str(lib))
    integrated=test_suite(output,'test_real_ym.py','real',env)
    ys=output/'real.ys'
    ys.write_text('read_verilog -sv '+' '.join(json.dumps(str(x)) for x in sorted((HERE/'rtl').glob('*.v')))+'\n'
                  'synth_ecp5 -top revc_real_ym_top -json '+json.dumps(str(output/'real.json'))+'\n'
                  'check -assert\ntee -o '+json.dumps(str(output/'stat.json'))+' stat -json\n')
    run(['yosys','-ql',output/'synthesis.log',ys],output/'synthesis-console.log')
    print(run([sys.executable,HERE/'check_real_cdc.py',output/'real.json','--output',output/'cdc.json'],output/'cdc.log').strip(),flush=True)
    summarize(output,component,integrated,started)


def summarize(output,component,integrated,started):
    control_summary=json.loads((output/'control/summary.json').read_text())
    files=[*sorted((HERE/'rtl').glob('*.v')),*sorted((HERE/'tests').glob('*.cpp')),*sorted((HERE/'tests').glob('*.h')),
           *sorted((HERE/'tools').glob('*.py')),
           *sorted((HERE/'tests').glob('test_*.py')),*sorted(HERE.glob('check*.py'))]
    summary={
        'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),
        'kind':'F1 real-YM bus and audio RTL simulation/ECP5 mapping; not hardware/audio acceptance',
        'tools':control_summary['tools'],'python_version':sys.version.split()[0],
        'sources_sha256':{str(x.relative_to(HERE)):sha(x) for x in files},
        'unchanged_host_sha256':control_summary['unchanged_host_sha256'],
        'c_oracle_sha256':control_summary['c_oracle_sha256'],
        'control_regression':control_summary,
        'component_tests':component,'integrated_tests':integrated,
        'synthesis':json.loads((output/'stat.json').read_text())['design'],
        'clock_boundary_structure':json.loads((output/'cdc.json').read_text()),
        'configuration':{'control_hz':48000000,'audio_hz':49152000,'ym_hz':4000000,
                         'native_hz':'4000000/72','pcm_hz':48000,'ratio':'125:108','gain_eighths':8,
                         'i2s_bclk_hz':3072000,'i2s_slot_bits':32,'i2s_left_pcm_bits':16,'i2s_right':0,
                         'native_fifo_words':64,'pcm_fifo_words':64,'queue_events':1024},
        'place_route':'not run','timing_measured':False,'physical_pins_assigned':False,
        'limits':[
            'Synthetic bus/serial peripheral is a protocol fixture, not a YM2203 sound emulator or electrical model.',
            'Integrated tests cycle both clocks; optional private full-song test exercises the control model only.',
            'Structural check proves listed synchronizer chains and registered controls, not exhaustive CDC or STA/MTBF signoff.',
            'No final module/pin constraints, place/route, Fmax, analog listening or physical acceptance.',
            'Si5351 startup manager, USB/MIDI and independent external final inhibit remain to be implemented.',
            'Only fixed 4MHz YM with coherent 49.152MHz audio is verified; no runtime variable-clock or gain ramp support.'
        ],'wall_seconds':round(time.monotonic()-started,3)}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS real-YM/audio ECP5 mapping:',summary['synthesis']['num_cells_by_type'],flush=True)
    print('No place/route, Fmax or physical audio acceptance.',flush=True)


if __name__=='__main__':main()
