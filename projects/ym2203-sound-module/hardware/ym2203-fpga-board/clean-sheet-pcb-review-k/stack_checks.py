# SPDX-License-Identifier: MIT
"""Actual native coordinates plus conditional assembly envelopes, never bench acceptance."""
import hashlib,json,math,copy
from pathlib import Path
import pcbnew as P
CONTROL_NETS={'DIP1_N','DIP2_N','DIP3_N','DIP4_N','STOP_N','TEST_N'}
TARGETS={'SWCLOCK':[203,50],'SWSTOP':[203,82],'SWTEST':[203,105],'H2':[216,4],'H3':[216,138]}
mm=lambda v:[round(P.ToMM(v.x),6),round(P.ToMM(v.y),6)]
def require(c,m):
 if not c:raise AssertionError(m)
def rect(f):
 q=f.GetBoundingBox(False,False)
 return [P.ToMM(q.GetLeft()),P.ToMM(q.GetTop()),P.ToMM(q.GetRight()),P.ToMM(q.GetBottom())]
def hit(a,b,margin=0):return a[0]<b[2]+margin and a[2]+margin>b[0] and a[1]<b[3]+margin and a[3]+margin>b[1]
def gap(a,b):return math.hypot(max(a[0]-b[2],b[0]-a[2],0),max(a[1]-b[3],b[1]-a[3],0))
def pads(f):return sorted((p.GetNumber(),mm(p.GetPosition()),mm(p.GetDrillSize()),p.GetNetname()) for p in f.Pads())
def signature(t):
 if isinstance(t,P.PCB_VIA):return ('via',tuple(mm(t.GetPosition())),t.GetWidth(P.F_Cu),t.GetDrillValue(),t.GetNetname())
 return ('track',tuple(mm(t.GetStart())),tuple(mm(t.GetEnd())),t.GetLayer(),t.GetWidth(),t.GetNetname())
def contract(d):
 require(d['unintended_placement_changes']==0,'unintended placement change')
 require(d['electrical_and_pin_changes']==0,'electrical change')
 require(d['shield_mates']==32 and d['shield_mate_error_mm']<1e-5,'shield mate')
 require(d['shield_mount_errors']==0,'shield mounts')
 require(d['shield_edge_segments']==4 and d['shield_openings']==0,'rectangular shield')
 require(d['source_xy_gap_mm']>=7,'shield/source gap')
 require(d['control_source_gap_mm']>=10,'right control/source gap')
 require(d['control_edge_gap_mm']>=2,'control/board edge')
 require(d['control_conflicts']==0,'control/component interference')
 require(d['shield_tall_part_conflicts']==0,'tall part under shield')
 require(d['shield_smt_cavity_mm']>=4.5,'shield cavity')
 require(d['icsp_tht_collisions']==0 and d['icsp_face_clearance_mm']>=1.9,'ICSP underside clearance')
 require(d['front_ground_zone_right_mm']>=219.5,'GND extension')

def inspect(base,source,hw,here):
 old=P.LoadBoard(str(hw/'clean-sheet-pcb-review-j/base/p2-base-j.kicad_pcb'))
 shield_dir=hw/'editor-shield-review-b/pcb-review-b'
 shield=P.LoadBoard(str(shield_dir/'p2-editor-b.kicad_pcb'))
 bf={f.GetReference():f for f in base.GetFootprints()};of={f.GetReference():f for f in old.GetFootprints()};sf={f.GetReference():f for f in shield.GetFootprints()}
 require(set(bf)==set(of),'reference set changed')
 for ref,d in json.loads((here/'base/placement-changes.json').read_text())['changes'].items():
  of[ref].SetPosition(P.VECTOR2I(P.FromMM(d['to_mm'][0]),P.FromMM(d['to_mm'][1])));of[ref].SetOrientationDegrees(d['to_degrees'])
 moved=electrical=0
 for r,f in bf.items():
  q=of[r];pos=mm(f.GetPosition());want=TARGETS.get(r,mm(q.GetPosition()))
  moved+=int(pos!=want or abs(math.remainder(f.GetOrientationDegrees()-q.GetOrientationDegrees(),360))>1e-6 or f.GetLayer()!=q.GetLayer())
  electrical+=int(f.GetValue()!=q.GetValue() or (str(f.GetFPID().GetLibNickname()),str(f.GetFPID().GetLibItemName()))!=(str(q.GetFPID().GetLibNickname()),str(q.GetFPID().GetLibItemName())))
  a,b=pads(f),pads(q)
  if r in TARGETS:
   dx,dy=[x-y for x,y in zip(pos,mm(q.GetPosition()))]
   b=sorted((n,[round(x+dx,6),round(y+dy,6)],drill,net) for n,(x,y),drill,net in b)
  electrical+=int(a!=b)
 errors=[];mates=0
 for sr,br in [('J1','JUNO_D0'),('J2','JUNO_D8'),('J3','JUNO_A'),('J4','JUNO_PWR')]:
  want={p.GetNumber():mm(p.GetPosition()) for p in bf[br].Pads()}
  require(sf[sr].GetLayer()==P.B_Cu,'shield male face')
  for p in sf[sr].Pads():errors.append(math.dist(mm(p.GetPosition()),want[p.GetNumber()]));mates+=1
 mounts=sum(mm(sf[a].GetPosition())!=mm(bf[b].GetPosition()) for a,b in [('H1','H9'),('H2','H10'),('H3','H12')])
 edges=[t for t in shield.GetDrawings() if isinstance(t,P.PCB_SHAPE) and t.GetLayer()==P.Edge_Cuts]
 segments={tuple(sorted((tuple(mm(t.GetStart())),tuple(mm(t.GetEnd()))))) for t in edges}
 corners=[[7,7],[83,7],[83,107],[7,107]]
 want={tuple(sorted((tuple(corners[i]),tuple(corners[(i+1)%4])))) for i in range(4)}
 require(segments==want and all(t.GetShape()==P.SHAPE_T_SEGMENT for t in edges),'shield outline')
 box=[7,7,83,107];src=[90,38,190,138];controls=[];conflicts=[]
 for r in ['SWCLOCK','SWSTOP','SWTEST']:
  b=rect(bf[r]);margin=.25;a=[b[0]-margin,b[1]-margin,b[2]+margin,b[3]+margin]
  near=[]
  for n,f in bf.items():
   if n==r:continue
   c=rect(f)
   if hit(a,c,.5):conflicts.append([r,n])
   near.append((gap(a,c),n))
  require(not hit(a,box) and not hit(a,src),'control under stacked board')
  controls.append(dict(ref=r,origin_mm=mm(bf[r].GetPosition()),occupied_bounds_mm=b,xy_allowance_mm=margin,source_gap_after_allowance_mm=round(gap(a,src),6),edge_gap_after_allowance_mm=round(min(a[0],220-a[2],a[1],142-a[3]),6),nearest_parts=sorted(near)[:3]))
 # Actual PTH body projection; documented intended headers/support holes are exempt.
 shieldtall=[];source_under=[]
 for r,f in bf.items():
  if r.startswith('H') or r.startswith('JUNO'):continue
  if any(p.GetDrillSize().x for p in f.Pads()):
   a=rect(f)
   if hit(a,box):shieldtall.append(r)
 # The ICSP header is intentionally below bare shield, no mating header on shield.
 shieldtall=[r for r in shieldtall if r!='JUNO_SPI']
 inp=json.loads((shield_dir/'mechanical-inputs.json').read_text());icsp=[x+10 for x in inp['base_icsp_bounds_local_mm']];intrusions=[]
 for r,f in sf.items():
  if r.startswith('H') or r in ['J1','J2','J3','J4']:continue
  for p in f.Pads():
   if not p.GetDrillSize().x:continue
   x,y=mm(p.GetPosition());dx,dy=mm(p.GetDrillSize())
   if hit([x-dx/2-.25,y-dy/2-.25,x+dx/2+.25,y+dy/2+.25],icsp):intrusions.append([r,p.GetNumber()])
 gnd=[]
 for z in base.Zones():
  if z.GetNetname()=='GND' and z.IsOnLayer(P.F_Cu):
   gnd += [P.ToMM(z.Outline().CVertex(i).x) for i in range(z.Outline().VertexCount())]
 d=dict(unintended_placement_changes=moved,electrical_and_pin_changes=electrical,shield_mates=mates,shield_mate_error_mm=max(errors),shield_mount_errors=mounts,shield_edge_segments=len(edges),shield_openings=0,source_xy_gap_mm=gap(box,src),control_source_gap_mm=min(q['source_gap_after_allowance_mm'] for q in controls),control_edge_gap_mm=min(q['edge_gap_after_allowance_mm'] for q in controls),control_conflicts=len(conflicts),shield_tall_part_conflicts=len(shieldtall),shield_smt_cavity_mm=inp['uno_face_gap_analysis_min_mm']-inp['shield_underside_protrusion_limit_mm']-inp['base_smt_admission_mm'],icsp_tht_collisions=len(intrusions),icsp_face_clearance_mm=inp['uno_face_gap_analysis_min_mm']-inp['base_icsp_top_admission_mm'],front_ground_zone_right_mm=max(gnd))
 contract(d)
 mutants={k:(False if isinstance(v,bool) else 0 if k in ['shield_mates','shield_edge_segments','front_ground_zone_right_mm'] or 'gap_mm' in k or 'clearance_mm' in k or 'cavity_mm' in k else 1) for k,v in d.items()}
 for k,v in mutants.items():
  bad=copy.deepcopy(d);bad[k]=v
  try:contract(bad)
  except AssertionError:pass
  else:raise AssertionError('invalid stack accepted: '+k)
 return dict(scope='native placement/pin equivalence and conditional body/lead/height envelopes; two-layer copper rerouted; physical fit not accepted',contracts=d,rejection_mutations=len(mutants),controls=controls,source_origin_on_base_mm=[90,38],shield_origin_on_base_mm=[10,10],shield_bounds_mm=box,source_bounds_mm=src,moved_refs={r:d['to_mm'] for r,d in json.loads((here/'base/placement-changes.json').read_text())['changes'].items()},shield_reference='../editor-shield-review-b/pcb-review-b',source_revision='3.8-pcb-review-k two-layer reroute',shield_standoffs_mm={'nominal_face_gap':11.01,'analysis_min_face_gap':10.5,'underside_leads_max':3,'lcd_standoff':12},mcu_under_gap_mm=5.9,source_cavity_mm=3.5,physical_fit_accepted=False)
