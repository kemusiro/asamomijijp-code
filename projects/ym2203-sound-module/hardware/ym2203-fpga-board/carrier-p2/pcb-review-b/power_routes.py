# SPDX-License-Identifier: MIT
"""Native power pours and clearance-checked VDD fanouts at fine-pitch ICs."""
import pcbnew as P
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))
def apply(b,ground_fanouts=()):
 def zone(layer,net):
  z=P.ZONE(b);z.SetLayer(layer);z.SetNetCode(b.FindNet(net).GetNetCode());z.SetLocalClearance(P.FromMM(.15));z.SetPadConnection(P.ZONE_CONNECTION_THT_THERMAL);z.SetThermalReliefGap(P.FromMM(.25));z.SetThermalReliefSpokeWidth(P.FromMM(.3));z.SetMinThickness(P.FromMM(.15));poly=z.Outline();poly.NewOutline()
  for x,y in [(.5,.5),(163.5,.5),(163.5,123.5),(.5,123.5)]:poly.Append(int(P.FromMM(x)),int(P.FromMM(y)))
  b.Add(z)
 def stub(a,net='V3V3'):
  n=b.FindNet(net);clear=int(P.FromMM(.16));obstacles=[];front=[];holes=[]
  for fp in b.GetFootprints():
   for p in fp.Pads():
    if p.GetDrillSize().x:holes.append((p.GetPosition(),P.ToMM(p.GetDrillSize().x)/2))
    if p.GetNetname()==net:continue
    for layer in [P.F_Cu,P.In1_Cu,P.In2_Cu,P.B_Cu]:
     if p.IsOnLayer(layer):
      shape=p.GetEffectiveShape(layer);obstacles.append(shape)
      if layer==P.F_Cu:front.append(shape)
  for q in b.GetTracks():
   if isinstance(q,P.PCB_VIA):holes.append((q.GetPosition(),P.ToMM(q.GetDrill())/2))
   if q.GetNetname()==net:continue
   shape=q.GetEffectiveShape();obstacles.append(shape)
   if q.IsOnLayer(P.F_Cu):front.append(shape)
  candidates=sorted(((i,j) for i in range(-40,41) for j in range(-40,41) if i*i+j*j>=64),key=lambda v:v[0]*v[0]+v[1]*v[1])
  for dx,dy in candidates:
   c=(round(a[0]+dx*.1,4),round(a[1]+dy*.1,4));pos=V(*c)
   if any((P.ToMM(pos.x-h.x))**2+(P.ToMM(pos.y-h.y))**2<(.15+r+.26)**2 for h,r in holes):continue
   circle=P.SHAPE_CIRCLE(pos,int(P.FromMM(.3)))
   if any(s.Collide(circle,clear) for s in obstacles):continue
   line=P.SHAPE_SEGMENT(V(*a),pos,int(P.FromMM(.18)))
   if any(s.Collide(line,clear) for s in front):continue
   break
  else:raise ValueError('No clear power fanout '+str(a))
  via=P.PCB_VIA(b);via.SetPosition(pos);via.SetWidth(P.FromMM(.6));via.SetDrill(P.FromMM(.3));via.SetViaType(P.VIATYPE_THROUGH);via.SetLayerPair(P.F_Cu,P.B_Cu);via.SetNetCode(n.GetNetCode());b.Add(via)
  q=P.PCB_TRACK(b);q.SetStart(V(*a));q.SetEnd(pos);q.SetWidth(P.FromMM(.18));q.SetLayer(P.F_Cu);q.SetNetCode(n.GetNetCode());b.Add(q)
  return dict(net=net,start=list(a),via=list(c),width_mm=.18)
 zone(P.F_Cu,'V5_CARRIER');zone(P.In2_Cu,'V3V3');zone(P.B_Cu,'V3V3')
 # Two PGA supply pads need solid pours: dense neighbouring socket pads starve
 # thermal spokes. Other through-hole pads keep thermal relief for hand soldering.
 for fp in b.GetFootprints():
  if fp.GetReference()=='MPGA':
   for pad in fp.Pads():
    if pad.GetNumber() in ['A3','B4']:pad.SetLocalZoneConnection(P.ZONE_CONNECTION_FULL)
 routes=[stub(a) for a in [(127.9,47),(132.1,48.5),(134.05,44),(139.05,43),(121.5,35.0875)]]
 routes += [stub(a,'GND') for a in ground_fanouts]
 # Adjacent ground pins need direct local straps, avoiding unnecessary long ground loops.
 fps={f.GetReference():f for f in b.GetFootprints()}
 for ref,aa,bb in [('U9','11','12'),('U19','7','8')]:
  pp={p.GetNumber():p for p in fps[ref].Pads()};a,c=pp[aa],pp[bb];assert a.GetNetname()==c.GetNetname()=='GND'
  q=P.PCB_TRACK(b);q.SetStart(a.GetPosition());q.SetEnd(c.GetPosition());q.SetLayer(P.F_Cu);q.SetWidth(P.FromMM(.18));q.SetNetCode(a.GetNetCode());b.Add(q)
 P.ZONE_FILLER(b).Fill(b.Zones());return routes
