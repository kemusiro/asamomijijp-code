#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the pinned JT03 sound core on iCE40UP5K, without programming hardware."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import time

HERE = Path(__file__).resolve().parent
DEFAULT_CASES = [(4, 1), (16, 1), (16, 2), (16, 3), (24, 1), (49.152, 1)]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tool_info(name, version_args):
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f'Install {name} first')
    binary = Path(found).resolve()
    result = {'reported_version': subprocess.check_output([found, *version_args],
               text=True, stderr=subprocess.STDOUT).strip(), 'binary_sha256': sha(binary)}
    receipt = binary.parent.parent / 'INSTALL_RECEIPT.json'
    formula = binary.parent.parent / '.brew' / (name + '.rb')
    if receipt.exists():
        result['homebrew_package_version'] = receipt.parent.name
    if formula.exists():
        text = formula.read_text()
        for field, expression in [('source_url', r'^  url "([^"]+)"'),
                                   ('source_archive_sha256', r'^  sha256 "([^"]+)"')]:
            match = re.search(expression, text, re.M)
            if match:
                result[field] = match.group(1)
    return result


def check_tools(lock, actual, allow_other):
    same = all(actual[name]['binary_sha256'] == lock[name]['binary_sha256'] for name in lock)
    if not same and not allow_other:
        raise ValueError('Tool binaries differ from toolchain-lock.json. Review versions or use '
                         '--allow-other-tools for a separately labelled experiment.')
    return same


def synthesis_text(project, upstream, output, profile):
    sim = project / 'simulation-jt03'
    lock = json.loads((sim / 'core-lock.json').read_text())
    sources = [upstream / p for p in lock['files'] if p != 'hdl/jt03.v']
    sources.append(sim / 'revc_jt03.v')
    top = 'revc_jt03'
    if profile == 'probe':
        sources.append(HERE / 'jt03_fit_probe.v')
        top = 'jt03_fit_probe'
    elif profile != 'core':
        raise ValueError('Unknown synthesis profile')
    # -defer prevents hierarchy checks on the unused, default YM2612 elaboration.
    # No SIMULATION, FASTDIV, timing exceptions, memory rewrites or retiming.
    quote = lambda p: json.dumps(str(p.resolve()))
    return ('read_verilog -defer ' + ' '.join(map(quote, sources)) + '\n'
            + f'synth_ice40 -device u -dsp -top {top} -json {quote(output / (profile + ".json"))}\n'
            + 'check -assert\n'
            + f'tee -o {quote(output / (profile + "-stat.json"))} stat -json\n')


def cell_summary(stat):
    if len(stat['modules']) != 1:
        raise ValueError('Expected one flattened synthesis module')
    cells = next(iter(stat['modules'].values()))['num_cells_by_type']
    return {'lut4': cells.get('SB_LUT4', 0),
            'flip_flops': sum(v for k, v in cells.items() if k.startswith('SB_DFF')),
            'carry': cells.get('SB_CARRY', 0), 'dsp': cells.get('SB_MAC16', 0),
            'ebr': sum(v for k, v in cells.items() if k.startswith('SB_RAM40_4K')),
            'cells_by_type': cells}


def summarize_pnr(target, seed, rc, report, log):
    errors = [line for line in log.splitlines() if line.startswith('ERROR:')]
    routed = 'Routing complete.' in log
    if not report or not report.get('fmax') or not report.get('utilization') or not routed:
        return {'target_mhz': target, 'seed': seed, 'exit_code': rc,
                'classification': 'implementation_error', 'errors': errors}
    clocks = report['fmax']
    if any(abs(c['constraint'] - target) > 1e-3 for c in clocks.values()):
        raise ValueError('Report clock constraint differs from requested clock')
    fits_timing = all(c['achieved'] >= target for c in clocks.values())
    timing_only = all(e.startswith('ERROR: Max frequency for clock ') for e in errors)
    if rc == 0 and fits_timing and not errors:
        status = 'pass'
    elif rc != 0 and not fits_timing and errors and timing_only:
        status = 'timing_fail'
    else:
        status = 'implementation_error'
    utilization = report['utilization']
    if utilization['ICESTORM_LC']['used'] == 0:
        raise ValueError('Core was optimized away')
    paths = []
    for p in report.get('critical_paths', []):
        paths.append({'from_clock': p['from'], 'to_clock': p['to'],
                      'delay_ns': sum(item['delay'] for item in p['path']),
                      'source_cell': p['path'][0]['from']['cell'],
                      'sink_cell': p['path'][-1]['to']['cell']})
    return {'target_mhz': target, 'seed': seed, 'exit_code': rc, 'classification': status,
            'routing_complete': routed, 'fmax': clocks, 'utilization': utilization,
            'critical_paths': paths, 'errors': errors}


def pnr_case(output, case):
    target, seed = case
    if not math.isfinite(target) or target <= 0 or seed < 1:
        raise ValueError('Invalid timing case')
    name = f'pnr-{target:g}mhz-seed{seed}'
    args = ['nextpnr-ice40', '--up5k', '--package', 'sg48', '--json', str(output / 'probe.json'),
            '--freq', str(target), '--seed', str(seed), '--pcf-allow-unconstrained',
            '--report', str(output / (name + '.json')), '--asc', str(output / (name + '.asc')),
            '--log', str(output / (name + '.log'))]
    with (output / (name + '-console.txt')).open('w') as console:
        result = subprocess.run(args, stdout=console, stderr=subprocess.STDOUT)
    path = output / (name + '.json')
    report = json.loads(path.read_text()) if path.exists() else None
    log = (output / (name + '.log')).read_text() if (output / (name + '.log')).exists() else ''
    summary = summarize_pnr(target, seed, result.returncode, report, log)
    summary['artifacts'] = {p.name: sha(p) for p in [path, output / (name + '.log'),
                            output / (name + '.asc')] if p.exists()}
    print(name, summary['classification'], flush=True)
    return summary


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, default=HERE.parent)
    p.add_argument('--upstream', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--jobs', type=int, default=3)
    p.add_argument('--allow-other-tools', action='store_true')
    args = p.parse_args()
    project, output = args.project.resolve(), args.output.resolve()
    upstream = (args.upstream or project / '.cache/jt03/upstream').resolve()
    sim = project / 'simulation-jt03'
    spec = importlib.util.spec_from_file_location('jt03_source_lock', sim / 'build.py')
    source_lock = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(source_lock)
    source_lock.verify_sources(upstream)
    tools = {'yosys': tool_info('yosys', ['-V']), 'nextpnr-ice40': tool_info('nextpnr-ice40', ['--version'])}
    locked_tools = json.loads((HERE / 'toolchain-lock.json').read_text())['tools']
    tool_match = check_tools(locked_tools, tools, args.allow_other_tools)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError('Use an empty output directory; preserve previous results')
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    summaries = {}
    for profile in ['core', 'probe']:
        script = output / (profile + '.ys')
        script.write_text(synthesis_text(project, upstream, output, profile))
        with (output / (profile + '-console.txt')).open('w') as console:
            subprocess.run(['yosys', '-ql', str(output / (profile + '-synthesis.log')), str(script)],
                           check=True, stdout=console, stderr=subprocess.STDOUT)
        summaries[profile] = cell_summary(json.loads((output / (profile + '-stat.json')).read_text()))
    with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as pool:
        cases = list(pool.map(lambda case: pnr_case(output, case), DEFAULT_CASES))
    lock = json.loads((sim / 'core-lock.json').read_text())
    own_sources = [sim / 'revc_jt03.v', sim / 'core-lock.json', HERE / 'jt03_fit_probe.v',
                   HERE / 'run.py', HERE / 'toolchain-lock.json']
    report = {'schema_version': 1, 'kind': 'FPGA synthesis/place-and-route estimate, not hardware acceptance',
              'upstream': {k: lock[k] for k in ['upstream', 'commit', 'jt49_commit']},
              'upstream_hashes_checked': len(lock['files']), 'tools': tools, 'tool_lock_matched': tool_match,
              'own_sources_sha256': {str(f.relative_to(project)) if f.is_relative_to(project) else f.name: sha(f)
                                     for f in own_sources},
              'device': 'iCE40UP5K-SG48', 'configuration': {'JT49_DIV': 3, 'YM2203_LUMPED': 0,
                'yosys_flow': 'synth_ice40 -device u -dsp; ABC9 default in locked Yosys',
                'io_pins': 'automatically assigned for analysis; NOT a board pinout',
                'timing_exceptions': [], 'input_output_delays_constrained': False,
                'probe_lut_overhead': summaries['probe']['lut4'] - summaries['core']['lut4']},
              'synthesis': summaries, 'cases': cases, 'wall_seconds': time.monotonic() - start,
              'limits': ['Probe mux observes all 40 audio bits; its logic overhead is included in P&R.',
                'No SPI/event FIFO, timeline, resampler, I2S, CDC, loader or safety gate controller included.',
                'IRQ and GPIO outside the simulation wrapper remain unexposed.',
                'Fmax is internal register-to-register STA from the open-source device model.',
                'Async port setup/hold, board loading, duty cycle and hardware operation remain unverified.',
                'No program/flash commands run; no usable board bitstream is delivered.']}
    (output / 'summary.json').write_text(json.dumps(report, indent=2) + '\n')
    if any(c['classification'] == 'implementation_error' for c in cases):
        raise RuntimeError('An implementation failed; inspect logs and summary.json')
    print('DONE: summary.json (timing_fail entries are retained as failures, not promoted to passes)')


if __name__ == '__main__':
    main()
