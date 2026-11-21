# SPDX-License-Identifier: MIT
import json
import pcbnew as P
mm=lambda v:[P.ToMM(v.x),P.ToMM(v.y)]
def geometry(b):
 r=dict(footprints=[],tracks=[],edges=[],zones=[],copper_graphics=[],layers=b.GetCopperLayerCount())
 for f in b.GetFootprints():
  pads=[dict(number=p.GetNumber(),net=p.GetNetname(),pos=mm(p.GetPosition()),size=mm(p.GetSize()),angle=p.GetOrientationDegrees(),drill=mm(p.GetDrillSize()),shape=int(p.GetShape()),attr=int(p.GetAttribute()),layers=[int(x) for x in p.GetLayerSet().Seq()]) for p in f.Pads()]
  r['footprints'].append(dict(ref=f.GetReference(),value=f.GetValue(),fpid=str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName()),pos=mm(f.GetPosition()),angle=f.GetOrientationDegrees(),layer=f.GetLayer(),pads=sorted(pads,key=lambda p:(p['number'],p['pos']))))
 for t in b.GetTracks():
  if isinstance(t,P.PCB_VIA):v=dict(type='via',pos=mm(t.GetPosition()),width=P.ToMM(t.GetWidth(P.F_Cu)),drill=P.ToMM(t.GetDrillValue()),layers=[int(x) for x in t.GetLayerSet().Seq()],net=t.GetNetname())
  else:v=dict(type='track',start=mm(t.GetStart()),end=mm(t.GetEnd()),width=P.ToMM(t.GetWidth()),layer=t.GetLayer(),net=t.GetNetname())
  r['tracks'].append(v)
 for d in b.GetDrawings():
  if d.GetLayer()==P.Edge_Cuts:r['edges'].append(dict(shape=int(d.GetShape()),start=mm(d.GetStart()),end=mm(d.GetEnd()),width=P.ToMM(d.GetWidth())))
 for z in b.Zones():
  outlines=[]
  for i in range(z.Outline().OutlineCount()):
   a=z.Outline().COutline(i);outlines.append([mm(a.CPoint(j)) for j in range(a.PointCount())])
  r['zones'].append(dict(uuid=z.m_Uuid.AsString(),net=z.GetNetname(),layers=[int(x) for x in z.GetLayerSet().Seq()],rule_area=z.GetIsRuleArea(),outline=outlines))
 for d in list(b.GetDrawings())+[x for f in b.GetFootprints() for x in f.GraphicalItems()]:
  if isinstance(d,P.PCB_SHAPE) and d.GetLayer() in [P.F_Cu,P.In1_Cu,P.In2_Cu,P.B_Cu]:
   box=d.GetBoundingBox();r['copper_graphics'].append(dict(shape=int(d.GetShape()),start=mm(d.GetStart()),end=mm(d.GetEnd()),width=P.ToMM(d.GetWidth()),layer=d.GetLayer(),bounds=[P.ToMM(x) for x in [box.GetLeft(),box.GetTop(),box.GetRight(),box.GetBottom()]]))
 for k in ['footprints','tracks','edges','zones','copper_graphics']:r[k]=sorted(r[k],key=lambda v:json.dumps(v,sort_keys=True))
 return r
