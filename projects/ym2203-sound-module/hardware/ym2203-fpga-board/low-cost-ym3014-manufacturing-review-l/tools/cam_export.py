# SPDX-License-Identifier: MIT
from pathlib import Path
import subprocess,json,hashlib,sys
S=Path(sys.argv[1]).resolve();O=S/'artifacts';O.mkdir(exist_ok=True)
boards={'base':('p2-base-lc-k',4),'module':('p2-ym2203-lc-k',2),'panel':('p2-panel-lc-k',2)}
for key,(name,n) in boards.items():
 cad=S/'cad'/key;out=O/key;out.mkdir(exist_ok=True);board=cad/(name+'.kicad_pcb')
 def run(args,log):
  with (S/log).open('w') as f:subprocess.run(args,stdout=f,stderr=subprocess.STDOUT,check=True)
 print('Checking',key,flush=True)
 run(['kicad-cli','sch','erc','--format','json','-o',str(out/'erc.json'),str(cad/(name+'.kicad_sch'))],key+'-erc.log')
 run(['kicad-cli','pcb','drc','--refill-zones','--save-board','--schematic-parity','--format','json','--severity-all','--exit-code-violations','-o',str(out/'drc.json'),str(board)],key+'-drc.log')
 for q in ['erc.json','drc.json']:
  p=out/q;d=json.loads(p.read_text());t=p.read_text().replace(str(cad)+'/', '');p.write_text(t)
 d=json.loads((out/'drc.json').read_text());assert not any(d[k] for k in ['violations','unconnected_items','schematic_parity'])
 assert not any(t['violations'] for t in json.loads((out/'erc.json').read_text())['sheets'])
 gerber=out/'gerbers';gerber.mkdir(exist_ok=True);layers=['F.Cu']+(['In1.Cu','In2.Cu'] if n==4 else [])+['B.Cu','F.Mask','B.Mask','F.Silkscreen','B.Silkscreen','Edge.Cuts']
 run(['kicad-cli','pcb','export','gerbers','--layers',','.join(layers),'--subtract-soldermask','--precision','6','-o',str(gerber),str(board)],key+'-gerber.log')
 run(['kicad-cli','pcb','export','drill','--format','excellon','--drill-origin','absolute','--excellon-units','mm','--excellon-zeros-format','decimal','--excellon-oval-format','route','--excellon-separate-th','--generate-map','--map-format','svg','--generate-report','-o',str(gerber),str(board)],key+'-drill.log')
 # F has no explicit physical stackup. KiCad synthesizes 35um on every layer;
 # omit that placeholder so the job does not contradict the standard 0.5oz
 # inner copper requested in ORDERING.md. No copper/drill artwork is changed.
 job=gerber/(name+'-job.gbrjob');data=json.loads(job.read_text())
 data.pop('MaterialStackup',None)
 job.write_text(json.dumps(data,indent=2)+'\n')
 # Normalize only insignificant line-end whitespace in human-readable SVG maps.
 for p in gerber.glob('*.svg'):p.write_text('\n'.join(line.rstrip() for line in p.read_text().splitlines())+'\n')
 print('CAM exported',key,flush=True)
