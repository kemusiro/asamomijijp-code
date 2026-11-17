#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build the pinned, unpatched JT03 RTL plus the GPL simulation harness."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
LOCK = json.loads((HERE / 'core-lock.json').read_text())


def run(*args, **kwargs):
    return subprocess.run(args, check=True, **kwargs)


def verify_sources(upstream):
    for folder, expected in [(upstream, LOCK['commit']), (upstream / 'jt49', LOCK['jt49_commit'])]:
        actual = subprocess.check_output(['git', '-C', str(folder), 'rev-parse', 'HEAD'], text=True).strip()
        if actual != expected:
            raise ValueError(f'Unexpected upstream revision: {folder.name}')
    for name, expected in LOCK['files'].items():
        if hashlib.sha256((upstream / name).read_bytes()).hexdigest() != expected:
            raise ValueError(f'Upstream file changed: {name}')


def build(upstream, output, jobs=4, fetch=False):
    upstream, output = upstream.resolve(), output.resolve()
    if fetch and not upstream.exists():
        run('git', 'clone', '--no-checkout', LOCK['upstream'], str(upstream))
        run('git', '-C', str(upstream), 'checkout', '--detach', LOCK['commit'])
        run('git', '-C', str(upstream), 'submodule', 'update', '--init', 'jt49')
    verify_sources(upstream)
    version = subprocess.check_output(['verilator', '--version'], text=True).strip()
    if version.split()[1] != LOCK['verilator_version']:
        raise ValueError(f"Expected Verilator {LOCK['verilator_version']}; found {version}")
    output.mkdir(parents=True, exist_ok=True)
    # Do not enable FASTDIV: it changes FM/SSG/timer clock relationships.
    rtl = [str(upstream / p) for p in LOCK['files'] if p != 'hdl/jt03.v']
    run('verilator', '--cc', '--exe', '--build', '-j', str(jobs), '-O3',
        '-Wno-fatal', '-DSIMULATION', '--top-module', 'revc_jt03',
        '--Mdir', str(output), '-CFLAGS', '-O3 -std=c++17',
        '-o', 'jt03-render', str(HERE / 'revc_jt03.v'), *rtl,
        str(HERE / 'simulator.cpp'))
    info = {'verilator': version, 'upstream_commit': LOCK['commit'],
            'jt49_commit': LOCK['jt49_commit'], 'jt49_div': 3,
            'compiler': subprocess.check_output(['c++', '--version'], text=True).splitlines()[0],
            'project_sources_sha256': {p: hashlib.sha256((HERE / p).read_bytes()).hexdigest()
                                       for p in ['simulator.cpp', 'revc_jt03.v', 'core-lock.json']}}
    (output / 'build-info.json').write_text(json.dumps(info, indent=2) + '\n')
    print(output / 'jt03-render')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream', type=Path, default=HERE.parent / '.cache/jt03/upstream')
    parser.add_argument('--output', type=Path, default=HERE.parent / '.cache/jt03/build')
    parser.add_argument('--fetch', action='store_true', help='Clone exactly the locked revision if absent')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    build(args.upstream, args.output, args.jobs, args.fetch)
