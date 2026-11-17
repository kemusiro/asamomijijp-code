# SPDX-License-Identifier: MIT
"""Final decoupling placement and physical envelopes, after SES import."""
import json,pcbnew as P
from pathlib import Path
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))
def apply(b):
 f=next(f for f in b.GetFootprints() if f.GetReference()=='C19');g=next(p for p in f.Pads() if p.GetNetname()=='GND');old=(P.ToMM(g.GetPosition().x),P.ToMM(g.GetPosition().y))
 f.SetOrientationDegrees(0);f.SetPosition(V(120,115.26));f.Reference().SetPosition(V(120,113.5))
 new=next(p for p in f.Pads() if p.GetNetname()=='GND');return [old,(P.ToMM(new.GetPosition().x),P.ToMM(new.GetPosition().y))]
def record(b,out):
 fps={f.GetReference():f for f in b.GetFootprints() if not f.GetReference().startswith('H')};places={r:dict(x_mm=P.ToMM(f.GetPosition().x),y_mm=P.ToMM(f.GetPosition().y),rotation_deg=f.GetOrientationDegrees()) for r,f in fps.items()}
 bounds={}
 for f in b.GetFootprints():
  if f.GetReference().startswith('H'):
   x,y=P.ToMM(f.GetPosition().x),P.ToMM(f.GetPosition().y);r=1.75 if f.GetReference()=='H3' else 2.5;bounds[f.GetReference()]=[x-r,y-r,x+r,y+r]
 for ref,f in fps.items():
  if ref.startswith('JUNO'):
   xx=[P.ToMM(p.GetPosition().x) for p in f.Pads()];yy=[P.ToMM(p.GetPosition().y) for p in f.Pads()];bb=[min(xx)-1.4,min(yy)-1.4,max(xx)+1.4,max(yy)+1.4]
  elif ref=='MPGA':bb=[94.73,24.73,120.13,50.13]
  else:
   z=f.GetBoundingBox(False,False);bb=[P.ToMM(z.GetLeft()),P.ToMM(z.GetTop()),P.ToMM(z.GetRight()),P.ToMM(z.GetBottom())]
  bounds[ref]=bb
 (out/'placement-refs.json').write_text(json.dumps(places,indent=2)+'\n');(out/'body-clearances.json').write_text(json.dumps({'model':'Actual final native body/fab extents plus socket envelopes and mounting reserves;0.25mm separation','count':len(bounds),'bounds':bounds},indent=2)+'\n')
