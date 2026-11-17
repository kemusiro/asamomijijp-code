#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build/test/place/route the dual-clock JT03 prototype. Never programs a board."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import re
from pathlib import Path
import subprocess
import sys
import time
import cdc_check

HERE = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def logged(args, log):
    with log.open('w') as f:
        result = subprocess.run(list(map(str,args)), stdout=f, stderr=subprocess.STDOUT, timeout=300)
    if result.returncode:
        raise RuntimeError(f'Command failed ({result.returncode}); inspect {log.name}')
    return log.read_text()


def verify_tests(output, sources):
    records = []
    for name, top, rtl, cpp, extra, cflags, count in [
        ('system', 'jt03_minimal', sources, 'system_test.cpp', ['-GLEASE_CYCLES=800000'], '', 17),
        ('fifo', 'async_pcm_fifo', [HERE/'rtl/async_pcm_fifo.v'], 'fifo_test.cpp', [], '', 3),
        ('default-lease', 'jt03_minimal', sources, 'system_test.cpp', [], '-DDEFAULT_LEASE_TEST', 1)]:
        build=output/('build-'+name)
        logged(['verilator','--cc','--exe','--build','-j','4','-O3','-Wno-fatal',
                '--top-module',top,*extra,'--Mdir',build,'-CFLAGS','-O3 -std=c++17 '+cflags,
                '-o','test',*rtl,HERE/'tests'/cpp],output/(name+'-build.log'))
        text=logged([build/'test'],output/(name+'-test.log'))
        passed=sum(line.startswith('PASS ') for line in text.splitlines())
        if passed!=count: raise RuntimeError(f'Expected {count} tests in {name}, saw {passed}')
        records.append({'suite':name,'passed':passed,'log_sha256':sha(output/(name+'-test.log'))})
        print('PASS',name,passed,flush=True)
    text=logged([sys.executable,'-m','unittest','discover','-s',HERE/'tests','-p','test_*.py','-v'],
           output/'python-tests.log')
    match=re.search(r"Ran (\d+) tests",text)
    if not match:raise RuntimeError('Missing unittest count')
    return records,int(match.group(1))


def summarize(report, log, rc, structural):
    errors=[l for l in log.splitlines() if l.startswith('ERROR:')]
    clocks=report.get('fmax',{}) if report else {}
    expected={'synth_clk':16,'audio_clk':49.152}
    measured={}
    for prefix,freq in expected.items():
        matches=[v for k,v in clocks.items() if k.startswith(prefix+'$') or k==prefix]
        if len(matches)!=1 or abs(matches[0]['constraint']-freq)>1e-3:
            raise ValueError('Missing or wrong clock constraint: '+prefix)
        measured[prefix]=matches[0]
    routed='Routing complete.' in log
    timing=all(v['achieved']>=v['constraint'] for v in measured.values())
    status='pass' if rc==0 and not errors and routed and timing else 'fail'
    cross=[];paths=[]
    for path in report.get('critical_paths',[]):
        a,b=path['from'],path['to']
        delay=sum(p['delay'] for p in path['path'])
        fields={'from':a,'to':b,'delay_ns':delay,
                'source_cell':path['path'][0]['from']['cell'],
                'sink_cell':path['path'][-1]['to']['cell']}
        paths.append(fields)
        if ('synth_clk' in a and 'audio_clk' in b) or ('audio_clk' in a and 'synth_clk' in b):cross.append(fields)
    # No blanket false paths. The audited data crossings terminate at first-stage
    # synchronizers. Bound even the complete routed crossing by the faster period.
    bound=1000/49.152
    if len(cross)!=2 or any(p['delay_ns']>=bound for p in cross): status='fail'
    if structural['unexpected_data_or_enable_crossings']!=0:status='fail'
    return {'classification':status,'exit_code':rc,'routing_complete':routed,
            'clocks':measured,'utilization':report['utilization'],'cross_domain_paths':cross,
            'cdc_complete_path_bound_ns':bound,'critical_paths':paths,'errors':errors}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=HERE.parent)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--allow-other-tools',action='store_true')
    args=p.parse_args();project=args.project.resolve();output=args.output.resolve()
    if output.exists() and any(output.iterdir()):raise FileExistsError('Use an empty output directory')
    source=load(project/'simulation-jt03/build.py','core_sources')
    source.verify_sources(project/'.cache/jt03/upstream')
    helpers=load(project/'synthesis-jt03/run.py','synthesis_helpers')
    tools={n:helpers.tool_info(n,v) for n,v in [('yosys',['-V']),('nextpnr-ice40',['--version'])]}
    match=helpers.check_tools(json.loads((project/'synthesis-jt03/toolchain-lock.json').read_text())['tools'],tools,args.allow_other_tools)
    tools['verilator']=helpers.tool_info('verilator',['--version'])
    lock=json.loads((project/'simulation-jt03/core-lock.json').read_text())
    if tools['verilator']['reported_version'].split()[1]!=lock['verilator_version'] and not args.allow_other_tools:
        raise ValueError('Verilator version differs from core-lock.json')
    rtl=[project/'.cache/jt03/upstream'/n for n in lock['files'] if n!='hdl/jt03.v']
    rtl += [project/'simulation-jt03/revc_jt03.v',*sorted((HERE/'rtl').glob('*.v'))]
    output.mkdir(parents=True);start=time.monotonic()
    tests,python_count=verify_tests(output,rtl)
    script='read_verilog -defer '+' '.join(json.dumps(str(f)) for f in rtl)+'\n'
    script+='synth_ice40 -device u -dsp -top jt03_minimal -json '+json.dumps(str(output/'system.json'))+'\n'
    script+='check -assert\ntee -o '+json.dumps(str(output/'stat.json'))+' stat -json\n'
    (output/'synth.ys').write_text(script)
    logged(['yosys','-ql',output/'synth.log',output/'synth.ys'],output/'synth-console.log')
    netlist=json.loads((output/'system.json').read_text())
    structural=cdc_check.inspect(netlist)
    (output/'cdc.json').write_text(json.dumps(structural,indent=2)+'\n')
    (output/'clocks.pcf').write_text('set_frequency synth_clk 16\nset_frequency audio_clk 49.152\n')
    def place(seed):
        name='seed'+str(seed)
        command=['nextpnr-ice40','--up5k','--package','sg48','--json',str(output/'system.json'),
                 '--pcf',str(output/'clocks.pcf'),'--pcf-allow-unconstrained','--seed',str(seed),
                 '--report',str(output/(name+'.json')),'--asc',str(output/(name+'.asc')),
                 '--write',str(output/(name+'-routed.json')),'--log',str(output/(name+'.log'))]
        with (output/(name+'-console.log')).open('w') as f:r=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,timeout=300)
        report=json.loads((output/(name+'.json')).read_text())
        summary=summarize(report,(output/(name+'.log')).read_text(),r.returncode,structural)
        summary['seed']=seed
        summary['artifacts_sha256']={f.name:sha(f) for f in [output/(name+'.json'),output/(name+'.log'),output/(name+'.asc')] if f.exists()}
        print(name,summary['classification'],summary['clocks'],flush=True)
        return summary
    with ThreadPoolExecutor(max_workers=3) as pool:cases=list(pool.map(place,[1,2,3]))
    own=list((HERE/'rtl').glob('*.v'))+list((HERE/'tools').glob('*.py'))+list((HERE/'tests').glob('*'))
    own=[f for f in own if f.is_file()]+[project/'simulation-jt03/revc_jt03.v',project/'simulation-jt03/core-lock.json']
    result={'schema_version':1,'date_utc':datetime.now(timezone.utc).isoformat(),
            'kind':'dual-clock FPGA prototype; no board programming or hardware acceptance',
            'device':'iCE40UP5K-SG48','upstream':{k:lock[k] for k in ['commit','jt49_commit']},
            'tools':tools,'toolchain_lock_matched':match,'sources_sha256':{str(f.relative_to(project)) if f.is_relative_to(project) else str(f.relative_to(HERE)):sha(f) for f in own},
            'configuration':{'synth_mhz':16,'audio_mhz':49.152,'emulated_ym_clock_hz':4000000,
                'pcm_rate_hz':48000,'bclk_hz':3072000,'event_capacity':257,'event_bits':48,
                'pcm_capacity':'64 RAM words + 1 prefetched word','pcm_prime_samples':8,
                'spi_mode':0,'spi_max_hz':1000000,'lease_cycles':16000000,
                'clock_source':'common reference required; arbitrary initial phase permitted',
                'timing_exceptions':[],'board_pinout':'automatic analysis-only assignment',
                'io_setup_hold_checked':False},
            'rtl_tests':tests,'python_tests_passed':python_count,'python_test_log_sha256':sha(output/'python-tests.log'),
            'synthesis':helpers.cell_summary(json.loads((output/'stat.json').read_text())),
            'cdc_structural_audit':structural,'place_route':cases,'wall_seconds':time.monotonic()-start,
            'limits':['Fixed 4 MHz and 48 kHz prototype, not variable-clock or production firmware.',
                'Linear FM conversion, two simple SSG lowpass poles, 0.5 common gain, DC blocker; not WAV-identical to PC reference.',
                'No FPGA loader, Pico SPI firmware or validated physical board pinout.',
                'Independent oscillator frequency drift, MTBF, reset recovery/removal and board electrical timing not certified.',
                'Reset controls and asynchronous line-allow output are outside the data-path CDC audit.',
                'Both clocks stopped together require the external permit/watchdog hardware to mute.']}
    (output/'summary.json').write_text(json.dumps(result,indent=2)+'\n')
    if any(c['classification']!='pass' for c in cases):raise RuntimeError('Timing/CDC implementation not accepted; inspect summary.json')
    print('PASS: all RTL tests, structural CDC and three dual-clock place/route cases',flush=True)


if __name__=='__main__':main()
