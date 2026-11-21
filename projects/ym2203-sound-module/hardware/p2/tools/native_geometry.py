# SPDX-License-Identifier: MIT
"""Extract KiCad geometry without modifying historical source boards."""
import json, math, sys
from pathlib import Path
import pcbnew as p

root=Path(sys.argv[1]);key=sys.argv[2]
out={}
for key,name in [(key,{'base':'p2-base-lc-t','module':'p2-ym2203-lc-t','panel':'p2-panel-lc-n'}[key])]:
 b=p.LoadBoard(str(root/'cad'/key/(name+'.kicad_pcb')))
 holes={'PTH':[], 'NPTH':[]}; widths=[]; drills=[]; pads=0
 def hole(x,y,dx,dy,angle,kind):
  x,y,dx,dy=[p.ToMM(v) for v in [x,y,dx,dy]]; y=-y
  if min(dx,dy)<=0:return
  d=min(dx,dy); length=abs(dx-dy); a=math.radians(angle+(90 if dy>dx else 0))
  vx,vy=length/2*math.cos(a),length/2*math.sin(a)
  ends=sorted([[round(x-vx,4),round(y-vy,4)],[round(x+vx,4),round(y+vy,4)]])
  holes[kind].append([round(d,4),*ends[0],*ends[1]])
 for fp in b.GetFootprints():
  for pad in fp.Pads():
   pads+=1; size=pad.GetDrillSize(); pos=pad.GetPosition()
   hole(pos.x,pos.y,size.x,size.y,pad.GetOrientationDegrees(),'NPTH' if pad.GetAttribute()==p.PAD_ATTRIB_NPTH else 'PTH')
 for t in b.GetTracks():
  if isinstance(t,p.PCB_VIA):
   pos=t.GetPosition();d=t.GetDrillValue();hole(pos.x,pos.y,d,d,0,'PTH');drills.append(p.ToMM(d))
  else:widths.append(p.ToMM(t.GetWidth()))
 edges=[]
 for d in b.GetDrawings():
  if d.GetLayer()==p.Edge_Cuts:
   assert d.GetShape()==p.SHAPE_T_SEGMENT
   a,z=d.GetStart(),d.GetEnd()
   edges.append(sorted([[round(p.ToMM(a.x),4),round(-p.ToMM(a.y),4)],[round(p.ToMM(z.x),4),round(-p.ToMM(z.y),4)]]))
 out[key]={'name':name,'copper_layers':b.GetCopperLayerCount(),'pads':pads,'holes':holes,'edges':edges,'outline_stroke_mm':max(p.ToMM(x.GetWidth()) for x in b.GetDrawings() if x.GetLayer()==p.Edge_Cuts),'min_track_mm':min(widths),'via_drills_mm':sorted(set(drills))}
(root/'artifacts'/key/'native-geometry.json').write_text(json.dumps(out,indent=2)+'\n')
print('Extracted',[(k,len(v['holes']['PTH']),len(v['holes']['NPTH'])) for k,v in out.items()])
