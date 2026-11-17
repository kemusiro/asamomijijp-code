#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/test the F1 I2C v2 control RTL. No board programming or audio acceptance."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import time
import binascii

HERE=Path(__file__).resolve().parent


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command,log,env=None,timeout=300):
    with log.open('w') as out:
        subprocess.run([str(x) for x in command],stdout=out,stderr=subprocess.STDOUT,
                       check=True,timeout=timeout,env=env)
    return log.read_text()


def build_bridge(output,top,cpp,name):
    build=output/('build-'+name)
    run(['verilator','--cc','--exe','--build','-j','4','-Wall','--top-module',top,
         '--Mdir',build,'-CFLAGS','-fPIC -std=c++17','-LDFLAGS','-shared','-o',name+'.so',
         *sorted((HERE/'rtl').glob('*.v')),HERE/'tests'/cpp],output/(name+'-build.log'))
    return build/(name+'.so')


def test_suite(output,pattern,name,env,timeout=300):
    log=output/(name+'-tests.log')
    text=run([sys.executable,'-m','unittest','discover','-s',HERE/'tests','-p',pattern,'-v'],log,env,timeout=timeout)
    match=re.search(r'Ran (\d+) tests',text)
    if not match or not re.search(r'^OK',text,re.M):raise RuntimeError('Missing unittest result')
    skipped=len(re.findall(r'\.\.\. skipped ',text))
    result={'tests':int(match[1]),'skipped':skipped,'passed':int(match[1])-skipped,'log_sha256':sha(log)}
    print('PASS',name,result,flush=True)
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=HERE.parent)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--private-score',type=Path)
    a=p.parse_args();project=a.project.resolve();output=a.output.resolve()
    if output.exists() and any(output.iterdir()):raise FileExistsError('Use an empty output directory')
    output.mkdir(parents=True,exist_ok=True);started=time.monotonic()
    tools={}
    for name,flags in [('verilator',['--version']),('yosys',['-V']),('cc',['--version']),('c++',['--version'])]:
        executable=Path(shutil.which(name) or name)
        tools[name]={'version':subprocess.check_output([str(executable),*flags],text=True).splitlines()[0],
                     'sha256':sha(executable.resolve())}
    frame_log=run([sys.executable,HERE/'check.py','--project',project,'--output',output/'frame'],output/'frame-check.log')
    print(frame_log.strip(),flush=True)
    core=build_bridge(output,'revc_v2_core','session_bridge.cpp','session')
    wire=build_bridge(output,'revc_i2c_stream','i2c_bridge.cpp','wire')
    source=project/'firmware-c/src'
    oracle=output/'c-oracle.so'
    run(['cc','-std=c11','-O2','-Wall','-Wextra','-Werror','-shared','-fPIC','-I'+str(source),
         source/'wym1.c',source/'stream.c',source/'transport.c',project/'firmware-c/tests/stream_bridge.c',
         '-o',oracle],output/'c-oracle-build.log')
    env=dict(os.environ,F1_PROJECT=str(project),F1_SESSION_LIB=str(core),F1_I2C_LIB=str(wire),F1_C_ORACLE_LIB=str(oracle))
    env.pop('F1_PRIVATE_SCORE',None)
    private=None
    if a.private_score:
        path=a.private_score.resolve();raw=path.read_bytes()
        if raw[:4]!=b'WYM1' or len(raw)<16:raise ValueError('Expected private WYM1 file')
        events,period,clock=struct.unpack_from('<III',raw,4)
        private={'events':events,'period_ms':period,'clock_hz':clock,'crc32':f'{binascii.crc32(raw)&0xffffffff:08x}',
                 'sha256':sha(path),'kind':'private-data control simulation; no audio output or data included'}
        env['F1_PRIVATE_SCORE']=str(path)
    tests={
        'session':test_suite(output,'test_session.py','session',env),
        'i2c_wire':test_suite(output,'test_i2c_wire.py','wire',env)
    }
    if a.private_score and tests['session']['skipped']:raise RuntimeError('Private test did not run')
    ys=output/'control.ys'
    ys.write_text('read_verilog -sv '+' '.join(json.dumps(str(x)) for x in sorted((HERE/'rtl').glob('*.v')))+'\n'
                  'synth_ecp5 -top revc_i2c_control -json '+json.dumps(str(output/'control.json'))+'\n'
                  'check -assert\ntee -o '+json.dumps(str(output/'stat.json'))+' stat -json\n')
    run(['yosys','-ql',output/'synthesis.log',ys],output/'synthesis-console.log')
    stats=json.loads((output/'stat.json').read_text())['design']
    files=[*sorted((HERE/'rtl').glob('*.v')),*sorted((HERE/'tests').glob('*.cpp')),*sorted((HERE/'tests').glob('*.h')),
           *sorted((HERE/'tools').glob('*.py')),
           *sorted((HERE/'tests').glob('test_*.py')),HERE/'check_session.py',HERE/'check.py']
    oracle_sources=[source/x for x in ['stream.c','stream.h','transport.c','transport.h','wym1.c','wym1.h']]
    oracle_sources += [project/'firmware-c/tests/stream_bridge.c']
    host=[project/'firmware-c/host/lib'/x for x in ['ym2203_revc_stream.py','ym2203_revc_player.py']]
    summary={
        'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),
        'kind':'F1 I2C v2 RTL simulation and ECP5 technology mapping; not hardware/audio acceptance',
        'tools':tools,'python_version':sys.version.split()[0],
        'sources_sha256':{str(x.relative_to(HERE)):sha(x) for x in files},
        'c_oracle_sha256':{str(x.relative_to(project)):sha(x) for x in oracle_sources},
        'unchanged_host_sha256':{str(x.relative_to(project)):sha(x) for x in host},
        'frame':json.loads((output/'frame/summary.json').read_text()),'tests':tests,'private_score':private,
        'synthesis':stats,
        'configuration':{'queue_capacity':1024,'event_bits':48,'packet_slots':4,'packet_max_bytes':208,
                         'address':'0x42','i2c_model_nominal_hz':100000,'wire_model_clock_hz':16000000,
                         'control_wrapper_clock_hz':48000000,'lease_us':1000000,'play_delay_us':250000,
                         'late_limit_us':100000,'prepare_cleanup_timeout_us':100000},
        'place_route':'not run','timing_measured':False,'physical_pins_assigned':False,
        'limits':['YM writer, prepare, silence and audio_ok are explicit simulated adapters, not audio RTL.',
                  'Wire tests model open-drain SDA/SCL, finite clock stretching and input glitch rejection; not electrical compliance.',
                  'Model time can advance without simulating every oscillator cycle; no real-time performance or Fmax claim.',
                  'No USB/MIDI core, Si5351 startup manager, external YM bus/FM RX/audio or final external inhibit implementation.',
                  'Mapping includes timebase, I2C, request queue, session, event FIFO and status; excludes remaining full-board functions.'],
        'wall_seconds':round(time.monotonic()-started,3)}
    (output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
    print('PASS full I2C control ECP5 mapping/check:',stats['num_cells_by_type'],flush=True)
    print('No place/route, timing signoff, board programming or audio acceptance.',flush=True)


if __name__=='__main__':main()
