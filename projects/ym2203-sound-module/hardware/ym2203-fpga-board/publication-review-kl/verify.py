#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify published K/L dependencies and unchanged manufacturing sources."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check_files(base, files):
    for name, expected in files.items():
        path = base / name
        assert path.name != '.DS_Store' and path.suffix != '.kicad_prl', name
        assert path.is_file() and not path.is_symlink(), name
        assert digest(path) == expected, name
    return len(files)

count = 0
for folder in ('low-cost-schematic-review-c', 'low-cost-ym3014-schematic-review-e',
               'low-cost-ym3014-pcb-review-f', 'low-cost-ym3014-pcb-review-k',
               'low-cost-ym3014-manufacturing-review-l'):
    doc = json.loads((ROOT / folder / 'preservation.json').read_text())
    count += check_files(ROOT, doc['files'])

adjustments = json.loads((HERE / 'publication-adjustments.json').read_text())
for change in adjustments['changes']:
    path = ROOT / change['path']
    archive_name = (path.parent.name + '-preservation.json' if path.name == 'preservation.json'
                    else 'manufacturing-review-l-manifest.json')
    assert digest(HERE / 'original-manifests' / archive_name) == change['original_sha256']
    assert digest(path) == change['published_sha256']
    if path.name == 'preservation.json':
        assert len(json.loads(path.read_text())['files']) == change['published_entries']

source = ROOT / 'low-cost-ym3014-pcb-review-k'
manufacturing = ROOT / 'low-cost-ym3014-manufacturing-review-l'
manifest = json.loads((manufacturing / 'manufacturing-manifest.json').read_text())
source_count = check_files(source, manifest['source_files_sha256'])
cam_count = check_files(manufacturing, manifest['files'])
print(f'PASS: {count} preserved hashes, {source_count} K source hashes, {cam_count} CAM hashes; original manifests retained')
