#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fresh L CAM export using existing project native/CAM checks; never edit source CAD."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--work', required=True, type=Path)
    ap.add_argument('--hardware-root', type=Path, default=HERE.parent)
    ap.add_argument('--kicad-cli', default='kicad-cli')
    ap.add_argument('--kicad-python', default='python3')
    ap.add_argument('--cam-python', default='python3')
    a = ap.parse_args()
    w = a.work.resolve()
    assert not w.exists(), 'Use a new work directory'
    cli = shutil.which(a.kicad_cli)
    assert cli, 'kicad-cli not found'
    h = a.hardware_root.resolve()
    src = h / 'clean-sheet-pcb-review-l'
    inputs = {str(p.relative_to(src)): hashlib.sha256(p.read_bytes()).hexdigest()
              for d in ['base', 'P2H.pretty', 'P2L.pretty'] for p in (src / d).rglob('*')
              if p.is_file() and p.suffix in ['.kicad_pcb', '.kicad_pro', '.kicad_sch', '.kicad_mod', '.kicad_sym']}
    shutil.copytree(src / 'base', w / 'cad/base-l4', ignore=shutil.ignore_patterns('*.kicad_prl', '*.lck'))
    for name in ['P2H.pretty', 'P2L.pretty']:
        shutil.copytree(src / name, w / 'cad' / name)
    (w / 'boards.json').write_text(json.dumps({'base-l4': {
        'name': 'p2-base-l', 'layers': 4, 'dir': 'clean-sheet-pcb-review-l/base'}}, indent=2) + '\n')
    tools = h / 'manufacturing-review-k/tools'
    env = dict(os.environ, PATH=str(Path(cli).parent) + os.pathsep + os.environ.get('PATH', ''),
               PYTHONDONTWRITEBYTECODE='1')
    commands = [
        [sys.executable, str(tools / 'cam_export.py'), str(w)],
        [a.kicad_python, str(tools / 'native_geometry.py'), str(w)],
        [a.cam_python, str(tools / 'verify_cam.py'), str(w)],
        [a.kicad_python, str(tools / 'source_equivalence.py'), '--hardware-root', str(h), '--work', str(w)],
    ]
    for command in commands:
        subprocess.run(command, env=env, check=True)
    for name, sha in inputs.items():
        assert hashlib.sha256((src / name).read_bytes()).hexdigest() == sha, 'Source CAD changed'
    (w / 'source-inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    print('PASS: fresh L native/CAM export, original geometry equivalent, source inputs unchanged')


if __name__ == '__main__':
    main()
