#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export one board per native process; Gerbonara independently validates all CAM."""
from pathlib import Path
import argparse,subprocess,json,zipfile,hashlib
H=Path(__file__).resolve().parents[1];names={'base':'p2-base-lc-t','module':'p2-ym2203-lc-t','panel':'p2-panel-lc-n'}
a=argparse.ArgumentParser();a.add_argument('board',choices=list(names));a.add_argument('--pcb-python',required=True);args=a.parse_args();B=args.board;name=names[B];D=H/'cad'/B;O=H/'artifacts'/B;G=O/'gerbers';G.mkdir(parents=True,exist_ok=True)
def run(c):subprocess.run(c,check=True,stdout=subprocess.DEVNULL)
# Verified reports must correspond to the actual routed CAD.
run(['kicad-cli','pcb','drc','--refill-zones','--save-board','--schematic-parity','--format','json','--severity-all','--exit-code-violations','-o',str(D/'drc.json'),str(D/(name+'.kicad_pcb'))])
run(['kicad-cli','sch','erc','--format','json','--severity-all','--exit-code-violations','-o',str(D/'erc.json'),str(D/(name+'.kicad_sch'))])
run([args.pcb_python,str(H/'tools/check_design.py'),B])
cu='F.Cu,In1.Cu,In2.Cu,B.Cu' if B=='base' else 'F.Cu,B.Cu'
run(['kicad-cli','pcb','export','gerbers','--layers',cu+',F.Mask,B.Mask,F.Silkscreen,B.Silkscreen,Edge.Cuts','--subtract-soldermask','--precision','6','-o',str(G),str(D/(name+'.kicad_pcb'))])
run(['kicad-cli','pcb','export','drill','--format','excellon','--drill-origin','absolute','--excellon-units','mm','--excellon-zeros-format','decimal','--excellon-oval-format','route','--excellon-separate-th','--generate-map','--map-format','svg','--generate-report','-o',str(G),str(D/(name+'.kicad_pcb'))])
j=G/(name+'-job.gbrjob');job=json.loads(j.read_text());job.pop('MaterialStackup',None);j.write_text(json.dumps(job,indent=2)+'\n')
run([args.pcb_python,str(H/'tools/native_geometry.py'),str(H),B])
for typ in ['drc','erc']:
 d=json.loads((D/(typ+'.json')).read_text());(O/(typ+'.json')).write_text(json.dumps(d,indent=2)+'\n')
run(['kicad-cli','pcb','export','svg','--black-and-white','--layers','F.Fab,F.Silkscreen,Edge.Cuts','--mode-single','--fit-page-to-board','--exclude-drawing-sheet','--sketch-pads-on-fab-layers','-o',str(O/'assembly-top.svg'),str(D/(name+'.kicad_pcb'))])
for svg in G.glob('*.svg'):
 svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
print('CAM exported',B,flush=True)
