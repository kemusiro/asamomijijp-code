#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Refresh native KiCad reports; each command must succeed and no defects are accepted."""
from pathlib import Path
import argparse,subprocess,json
H=Path(__file__).resolve().parent
p=argparse.ArgumentParser();p.add_argument('--kicad-cli',default='kicad-cli');a=p.parse_args()
for side,name in [('base','p2-base-k'),('module','p2-ym2203-k')]:
 folder=H/side
 subprocess.run([a.kicad_cli,'sch','erc','--format','json','--severity-all','--exit-code-violations','--output','erc.json',name+'.kicad_sch'],cwd=folder,check=True)
 subprocess.run([a.kicad_cli,'sch','export','netlist','--format','kicadxml','--output','netlist.xml',name+'.kicad_sch'],cwd=folder,check=True)
 subprocess.run([a.kicad_cli,'pcb','drc','--refill-zones','--save-board','--schematic-parity','--format','json','--severity-all','--exit-code-violations','--output','drc.json',name+'.kicad_pcb'],cwd=folder,check=True)
 # Export metadata uses an absolute path even with relative CLI inputs; keep this artifact portable.
 net=folder/'netlist.xml';text=net.read_text();text=text.replace(str((folder/(name+'.kicad_sch')).resolve()),name+'.kicad_sch');net.write_text(text)
 d=json.loads((folder/'drc.json').read_text());assert not any(d[k] for k in ['violations','unconnected_items','schematic_parity'])
 assert not any(s['violations'] for s in json.loads((folder/'erc.json').read_text())['sheets'])
 print(side,'native ERC/DRC/unrouted/parity = 0')
