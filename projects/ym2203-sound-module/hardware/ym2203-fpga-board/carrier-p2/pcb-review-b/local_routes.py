# SPDX-License-Identifier: MIT
"""Reviewed local route additions to the recorded SES, with physical through vias."""
from pathlib import Path
import json,pcbnew as P
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))
def apply(b):
 O=Path(__file__).resolve().parent/'schematic';layers=[P.F_Cu,P.In2_Cu,P.B_Cu]
 def track(net,a,c,l,width=.18):
  if a==c:return
  t=P.PCB_TRACK(b);t.SetNetCode(b.FindNet(net).GetNetCode());t.SetStart(V(*a));t.SetEnd(V(*c));t.SetLayer(l);t.SetWidth(P.FromMM(width));b.Add(t)
 def via(net,x,y,size=.6,drill=.3):
  q=P.PCB_VIA(b);q.SetPosition(V(x,y));q.SetWidth(P.FromMM(size));q.SetDrill(P.FromMM(drill));q.SetViaType(P.VIATYPE_THROUGH);q.SetLayerPair(P.F_Cu,P.B_Cu);q.SetNetCode(b.FindNet(net).GetNetCode());b.Add(q)
 # Existing two B.Cu segments already meet here; the unnecessary hole had no second-layer connection.
 for t in list(b.GetTracks()):
  if isinstance(t,P.PCB_VIA) and t.GetNetname()=='Y_RD_N' and abs(P.ToMM(t.GetPosition().x)-114.208)<1e-5 and abs(P.ToMM(t.GetPosition().y)-75.1197)<1e-5:b.Remove(t)
 # Short pad fanout to a tented through via underneath U8's plastic body, clear of the solder pad.
 track('M_D1',(81.1375,81.375),(82.0375,81.375),P.F_Cu);via('M_D1',82.0375,81.375,.45,.2)
 # Local ground return for the otherwise isolated U9 ground-pin pair.
 track('GND',(81.1375,108.575),(81.1375,109.575),P.F_Cu);via('GND',81.1375,109.575)
 for r in json.loads((O/'local-routes.json').read_text()):
  pts=r['points'];net=r['net'];track(net,r['exact_start'],pts[0][:2],layers[pts[0][2]])
  for a,c in zip(pts,pts[1:]):
   if a[2]!=c[2]:
    assert a[:2]==c[:2];via(net,*a[:2])
   else:track(net,a[:2],c[:2],layers[a[2]])
  track(net,pts[-1][:2],r['exact_end'],layers[pts[-1][2]])
