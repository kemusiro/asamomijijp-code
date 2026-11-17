#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Bind native reports to the reviewed CAD. Run only after native ERC and DRC."""
from pathlib import Path
import json,hashlib
H=Path(__file__).resolve().parent
if __name__=='__main__':
 data={}
 for side,name in [('base','p2-base-j'),('module','p2-ym2203-i')]:
  folder=H/side
  report=json.loads((folder/'drc.json').read_text())
  assert not any(report[k] for k in ['violations','unconnected_items','schematic_parity'])
  assert not any(s['violations'] for s in json.loads((folder/'erc.json').read_text())['sheets'])
  files=[folder/(name+ext) for ext in ['.kicad_pcb','.kicad_pro']]+list(folder.glob('*.kicad_sch'))+[folder/n for n in ['erc.json','drc.json','circuit.json','netlist.xml']]
  for p in sorted(files):data[str(p.relative_to(H))]=hashlib.sha256(p.read_bytes()).hexdigest()
 (H/'native-binding.json').write_text(json.dumps(data,indent=2)+'\n')
 print('Bound',len(data),'native CAD/report inputs')
