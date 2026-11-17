#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run native KiCad validation, bind reports to saved CAD, then inspect pads/stack."""
import subprocess,json,hashlib
from pathlib import Path
from verify import H,run

def bind():
 files=['p2-editor-b.kicad_pcb','drc.json','erc.json','p2-editor-b.kicad_pro']+[p.name for p in H.glob('*.kicad_sch')]
 (H/'native-binding.json').write_text(json.dumps({n:hashlib.sha256((H/n).read_bytes()).hexdigest() for n in sorted(files)},indent=2)+'\n')

if __name__=='__main__':
 subprocess.run(['kicad-cli','sch','erc','--format','json','-o',str(H/'erc.json'),str(H/'p2-editor-b.kicad_sch')],check=True)
 subprocess.run(['kicad-cli','pcb','drc','--refill-zones','--save-board','--schematic-parity','--format','json','--exit-code-violations','-o',str(H/'drc.json'),str(H/'p2-editor-b.kicad_pcb')],check=True)
 for n in ['drc.json','erc.json']:
  p=H/n;p.write_text(p.read_text().replace(str(H)+'/',''))
 bind();run(H.parent.parent/'clean-sheet-pcb-review-i',True)
