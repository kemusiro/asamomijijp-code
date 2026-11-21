#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Combine the three independently extracted native geometry reports."""
import json
from pathlib import Path
root = Path(__file__).resolve().parents[1]
all_boards = {}
for key in ('base', 'module', 'panel'):
    report = json.loads((root / 'artifacts' / key / 'native-geometry.json').read_text())
    assert set(report) == {key}
    all_boards.update(report)
(root / 'native-geometry.json').write_text(json.dumps(all_boards, indent=2) + '\n')
