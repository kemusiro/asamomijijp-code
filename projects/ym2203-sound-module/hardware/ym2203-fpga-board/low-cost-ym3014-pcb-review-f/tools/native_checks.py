#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate schematics (not PCBs), native ERC/DRC, then independent checks."""
import argparse, json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--pcb-python', default=os.environ.get('KICAD_PYTHON'),
                    help='Python interpreter with the matching pcbnew module')
args = parser.parse_args()
if not args.pcb_python:
    parser.error('Pass --pcb-python or set KICAD_PYTHON; the ordinary Python may not load pcbnew.')
subprocess.run([sys.executable, str(ROOT / 'generate.py'), '--check'], cwd=ROOT, check=True)
for board, name in [('base', 'p2-base-lc-f'), ('module', 'p2-ym2203-lc-f'), ('panel', 'p2-panel-lc-f')]:
    subprocess.run(['kicad-cli', 'pcb', 'drc', '--refill-zones', '--save-board',
                    '--schematic-parity', '--format', 'json', '--severity-all',
                    '--exit-code-violations', '-o', 'drc.json', name + '.kicad_pcb'],
                   cwd=ROOT / board, check=True)
subprocess.run([args.pcb_python, str(ROOT / 'tools' / 'verify_pcb.py')], cwd=ROOT, check=True)
print('PASS: native ERC/DRC, every pin/net, connector geometry and preserved historical files')
