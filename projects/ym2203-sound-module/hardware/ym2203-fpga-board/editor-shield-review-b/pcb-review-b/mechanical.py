# SPDX-License-Identifier: MIT
"""Conditional 3D admission checks on actual native-pad projections, not bench measurements."""
import math
import pcbnew as P
mm=lambda v:[P.ToMM(v.x),P.ToMM(v.y)]
def require(c,m):
 if not c:raise AssertionError(m)
def overlap(a,c):return a[0]<c[2] and a[2]>c[0] and a[1]<c[3] and a[3]>c[1]
def inspect(board,base,inp):
 edges=[x for x in board.GetDrawings() if isinstance(x,P.PCB_SHAPE) and x.GetLayer()==P.Edge_Cuts]
 require(len(edges)==4 and all(x.GetShape()==P.SHAPE_T_SEGMENT for x in edges),'rectangle: four straight outer edges only')
 segments={tuple(sorted((tuple(mm(t.GetStart())),tuple(mm(t.GetEnd()))))) for t in edges}
 want={tuple(sorted((a,c))) for a,c in [((7.,7.),(83.,7.)),((83.,7.),(83.,107.)),((83.,107.),(7.,107.)),((7.,107.),(7.,7.))]}
 require(segments==want,'rectangle outline dimensions or closure')
 by={f.GetReference():f for f in base.GetFootprints()};rows=[];violations=[]
 for ref in inp['controls_covered']:
  f=by[ref];q=f.GetBoundingBox(False,False);m=inp['covered_control_xy_allowance_mm'];rect=[P.ToMM(q.GetLeft())-m,P.ToMM(q.GetTop())-m,P.ToMM(q.GetRight())+m,P.ToMM(q.GetBottom())+m];hits=[];near=[]
  for fp in board.GetFootprints():
   if fp.GetReference() in ['J1','J2','J3','J4'] or fp.GetReference().startswith('H'):continue
   for p in fp.Pads():
    if not p.GetDrillSize().x:continue
    q=p.GetBoundingBox();m=inp['lead_solder_xy_allowance_mm'];a=[P.ToMM(q.GetLeft())-m,P.ToMM(q.GetTop())-m,P.ToMM(q.GetRight())+m,P.ToMM(q.GetBottom())+m]
    dx=max(rect[0]-a[2],a[0]-rect[2],0);dy=max(rect[1]-a[3],a[1]-rect[3],0)
    item=dict(ref=fp.GetReference(),pin=p.GetNumber(),at_mm=mm(p.GetPosition()),solder_envelope_mm=a,xy_gap_mm=math.hypot(dx,dy));near.append(item)
    if overlap(rect,a):hits.append(item)
  require(not hits,'component lead over covered '+ref)
  z=inp['uno_face_gap_analysis_min_mm']-inp['covered_control_height_limit_mm']-inp['flush_via_copper_envelope_mm']-inp['stack_flex_allowance_mm']
  require(z>=1.7-1e-6,'covered control Z clearance <1.7mm')
  rows.append(dict(base_ref=ref,base_occupied_envelope_mm=rect,part_height_admission_mm=inp['covered_control_height_limit_mm'],tht_leads_over=hits,nearest_leads=sorted(near,key=lambda x:x['xy_gap_mm'])[:3],z_clearance_after_flex_mm=round(z,6)))
 return dict(conditional=True,outline_mm=[76,100],edge_segments=4,large_openings=0,edge_notches=0,covered_controls=rows,minimum_z_clearance_after_flex_mm=min(r['z_clearance_after_flex_mm'] for r in rows),physical_fit_accepted=False)
