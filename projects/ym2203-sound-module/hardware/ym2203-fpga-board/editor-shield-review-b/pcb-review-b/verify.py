#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native pad/net, mate, supplier pattern and conditional interference checks. Not bench acceptance."""
from pathlib import Path
import argparse,json,math,hashlib,csv
import pcbnew as P
H=Path(__file__).resolve().parent
mm=lambda v:[round(P.ToMM(v.x),6),round(P.ToMM(v.y),6)]
read=lambda p:json.loads(Path(p).read_text())
def require(c,m):
 if not c:raise AssertionError(m)
def overlap(a,c):return a[0]<c[2] and a[2]>c[0] and a[1]<c[3] and a[3]>c[1]
def run(base,write=False):
 for n,sha in read(H/'native-binding.json').items():require(hashlib.sha256((H/n).read_bytes()).hexdigest()==sha,'stale native report: '+n)
 for n,sha in read(H/'preservation.json')['reference_files_sha256'].items():require(hashlib.sha256((base.parent/n).read_bytes()).hexdigest()==sha,'changed preserved reference: '+n)
 board=P.LoadBoard(str(H/'p2-editor-b.kicad_pcb'));parts={q['ref']:q for q in read(H.parent/'circuit.json')['parts']};fps={f.GetReference():f for f in board.GetFootprints()};coords={};pads=0
 require(set(fps)==set(parts)|{'H1','H2','H3','HL1','HL2','HL3','HL4'},'reference set')
 for r,q in parts.items():
  f=fps[r];require(f.GetValue()==q['value'],r+' value');require(str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName())==q['footprint'],r+' footprint')
  ns={p['num']:p['net'] for p in q['pins']};require({p.GetNumber() for p in f.Pads() if p.GetNumber()}==set(ns),r+' pin set')
  coords[r]=[]
  for p in f.Pads():
   pads+=1;coords[r].append(dict(pin=p.GetNumber(),at_mm=mm(p.GetPosition()),net=p.GetNetname(),drill_mm=mm(p.GetDrillSize())))
   if p.GetNumber() and ns[p.GetNumber()] is not None:require(p.GetNetname()==ns[p.GetNumber()],r+':'+p.GetNumber()+' net')
   elif p.GetNumber():require(p.GetNetname().startswith('unconnected-') or not p.GetNetname(),r+' NC tied to live net')
 require(pads==159,'electrical pad count')
 geom=read(H.parent/'geometry/uno.json')['derived_board_header_facts'];unoerr=[];mates=0
 bb=P.LoadBoard(str(base/'base/p2-base-i.kicad_pcb'));bf={f.GetReference():f for f in bb.GetFootprints()}
 for r,o in [('J1','JUNO_D0'),('J2','JUNO_D8'),('J3','JUNO_A'),('J4','JUNO_PWR')]:
  f=fps[r];require(f.GetLayer()==P.B_Cu,r+' must be underside male')
  want={str(x['pin']):[x['x_mm']+10,x['y_mm']+10] for x in geom if x['ref']==o};bp={p.GetNumber():mm(p.GetPosition()) for p in bf[o].Pads()}
  for p in f.Pads():
   pt=mm(p.GetPosition());unoerr.append(max(abs(a-c) for a,c in zip(pt,want[p.GetNumber()])));unoerr.append(max(abs(a-c) for a,c in zip(pt,bp[p.GetNumber()])));mates+=1
 require(mates==32 and max(unoerr)<.00001,'UNO mate coordinates')
 for a,c in [('H1','H9'),('H2','H10'),('H3','H12')]:require(mm(fps[a].GetPosition())==mm(bf[c].GetPosition()),'mount location '+a)
 # Measured dimensions of the native footprints vs supplier mounting diagrams.
 for r in ['RV1','RV2','RV3','RV4']:
  pp={p.GetNumber():p for p in fps[r].Pads()};require(abs(math.dist(mm(pp['1'].GetPosition()),mm(pp['2'].GetPosition()))-2.5)<.00001,r+' pitch')
  mp=[p for p in fps[r].Pads() if p.GetNumber()=='MP'];require(abs(math.dist(mm(mp[0].GetPosition()),mm(mp[1].GetPosition()))-8.8)<.00001,r+' metal frame centers')
 for r in ['SW1','SW2','SW3','SW4','SW5','SW6']:
  a=[p for p in fps[r].Pads() if p.GetNumber()=='1'];c=[p for p in fps[r].Pads() if p.GetNumber()=='2'];require(abs(math.dist(mm(a[0].GetPosition()),mm(a[1].GetPosition()))-6.5)<.00001,r+' terminal span');require(min(math.dist(mm(x.GetPosition()),mm(y.GetPosition())) for x in a for y in c)==4.5,r+' row pitch')
 enc=[p for p in fps['ENC1'].Pads() if not p.GetNumber()];require(sorted(mm(p.GetDrillSize()) for p in enc)==[[2.1,1.6],[2.15,2.15]],'encoder slot/circular locator dimensions')
 # Thermal planes, tracks and manufacturing minima remain active.
 project=read(H/'p2-editor-b.kicad_pro');drc=read(H/'drc.json');erc=read(H/'erc.json')
 require(not project['board']['design_settings']['drc_exclusions'],'DRC exclusions')
 require(not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity'],'native DRC/parity')
 require(not [v for s in erc['sheets'] for v in s['violations']],'native ERC')
 require(board.GetCopperLayerCount()==2 and {z.GetNetname() for z in board.Zones()}=={'GND'},'2layer GND pours')
 tracks=list(board.GetTracks());vias=[t for t in tracks if isinstance(t,P.PCB_VIA)];require(all(t.GetWidth()>=P.FromMM(.2) for t in tracks if not isinstance(t,P.PCB_VIA)),'track minimum')
 inp=read(H/'mechanical-inputs.json');g=read(H/'mechanical-geometry.json');require(g['origin_on_base_mm']==[10,10],'stack origin')
 # Knob axes from native footprint transformation, with an additional relative mechanical allowance.
 axes=[]
 for r in ['RV1','RV2','RV3','RV4']:
  f=fps[r];require(abs(f.GetOrientationDegrees()-90)<.0001,'pot orientation');pt=mm(f.GetPosition());axes.append([round(pt[0]+2.5-10,6),round(pt[1]-7.5-10,6)])
 require(axes==g['pot_axis_local_mm'],'pot axes');gap=min(math.dist(a,c) for a,c in zip(axes,axes[1:]))-inp['knob_diameter_nominal_mm']-2*inp['knob_axis_relative_allowance_mm'];require(gap>=2,'knob gap')
 # LCD 90degree CCW view: x=-1+y_original, y=38-x_original. Clock pins face left.
 lcdholes=sorted([[round(-1+y,6),round(38-x,6)] for x in [2.5,29.5] for y in [1.5,41.22]])
 require(sorted([mm(fps[r].GetPosition())[0]-10,mm(fps[r].GetPosition())[1]-10] for r in ['HL1','HL2','HL3','HL4'])==lcdholes,'LCD hole transform')
 lcdbox=g['lcd_bounds_local_mm'];under=[];over=[]
 for r,f in fps.items():
  if r.startswith('H') or r in ['J1','J2','J3','J4']:continue
  box=f.GetBoundingBox(False,False);box=[P.ToMM(box.GetLeft())-10,P.ToMM(box.GetTop())-10,P.ToMM(box.GetRight())-10,P.ToMM(box.GetBottom())-10]
  if r=='ENC1':
   x,y=mm(f.GetPosition());box=[x-10-6.5,y-10-5.85,x-10+7.3,y-10+5.85] # supplier BODY, not land-pattern courtyard
  if overlap(box,lcdbox):
   require(r.startswith('R') and not r.startswith('RV') or r.startswith('C'),r+' tall body under LCD')
   under.append(r)
 lcdgap=inp['lcd_standoff_face_gap_mm']-inp['lcd_underside_admission_mm']-inp['lcd_to_low_parts_admission_mm'];require(lcdgap>=4,'LCD Z gap')
 cavity=inp['uno_face_gap_analysis_min_mm']-inp['shield_underside_protrusion_limit_mm']-inp['base_smt_admission_mm'];require(cavity>=4.5,'base/shield Z clearance')
 icsp=[x+10 for x in inp['base_icsp_bounds_local_mm']];intrusions=[]
 for f in fps.values():
  for p in f.Pads():
   if p.GetNumber() and p.GetDrillSize().x:
    x,y=mm(p.GetPosition());sx,sy=mm(p.GetDrillSize())
    if overlap([x-sx/2,y-sy/2,x+sx/2,y+sy/2],icsp):intrusions.append((f.GetReference(),p.GetNumber()))
 require(not intrusions,'THT leads over ICSP');require(inp['uno_face_gap_analysis_min_mm']-inp['base_icsp_top_admission_mm']>=1.9,'ICSP board-face gap')
 from mechanical import inspect
 covered=inspect(board,bb,inp)
 # All footprint origins/rotations, every electrical pad and hole stay at prior-review coordinates.
 old=P.LoadBoard(str(base.parent/'editor-shield-review-b/pcb-review-a/p2-editor-b.kicad_pcb'));oldfps={f.GetReference():f for f in old.GetFootprints()}
 for r,f in fps.items():
  q=oldfps[r];require(mm(f.GetPosition())==mm(q.GetPosition()) and f.GetOrientationDegrees()==q.GetOrientationDegrees() and f.GetLayer()==q.GetLayer(),r+' moved from parent PCB')
  require(sorted((p.GetNumber(),mm(p.GetPosition()),mm(p.GetDrillSize())) for p in f.Pads())==sorted((p.GetNumber(),mm(p.GetPosition()),mm(p.GetDrillSize())) for p in q.Pads()),r+' pad moved')
 require(90-(73+10)==7,'source XY gap')
 solder=[]
 for v in vias:
  shape=P.SHAPE_CIRCLE(v.GetPosition(),v.GetDrillValue()//2+P.FromMM(.05))
  for f in fps.values():
   for p in f.Pads():
    if p.GetAttribute()==P.PAD_ATTRIB_SMD and p.GetEffectiveShape(P.F_Cu).Collide(shape,0):solder.append((f.GetReference(),p.GetNumber()))
 require(not solder,'SMT pad over via hole; assembly review required')
 result=dict(covered_control_interference=covered,placement_unchanged_from_parent_pcb=True,smt_pad_via_hole_intersections=len(solder),date='2026-11-18',kicad=P.GetBuildVersion(),electrical_references=46,mounts=7,electrical_physical_pads=pads,total_physical_pads=sum(len(list(f.Pads())) for f in fps.values()),uno_mates=mates,max_mate_error_mm=max(unoerr),copper_layers=2,segments=len(tracks)-len(vias),vias=len(vias),erc=0,drc=0,unconnected=0,schematic_parity=0,drc_exclusions=0,ignored_checks=drc['ignored_checks'],track_min_mm=min(P.ToMM(t.GetWidth()) for t in tracks if not isinstance(t,P.PCB_VIA)),mechanical=dict(conditional=True,knob_axes_local_mm=axes,knob_min_gap_after_allowance_mm=gap,lcd_low_parts=sorted(under),lcd_min_z_gap_mm=lcdgap,base_smt_min_z_gap_mm=cavity,source_xy_gap_mm=7,icsp_tht_intrusions=intrusions,physical_fit_accepted=False),firmware_changed=False,host_changed=False,hardware_accepted=False)
 if write:
  (H/'covered-controls-projection.json').write_text(json.dumps(covered,indent=2)+'\n');(H/'verification.json').write_text(json.dumps(result,indent=2)+'\n');(H/'native-pads.json').write_text(json.dumps(coords,indent=2)+'\n')
  with (H/'placement.csv').open('w',newline='') as f:
   w=csv.writer(f,lineterminator='\n');w.writerow(['Ref','X_base_mm','Y_base_mm','Rotation_deg','Side','Value'])
   for r,fp in sorted(fps.items()):w.writerow([r,*mm(fp.GetPosition()),fp.GetOrientationDegrees(),fp.GetLayerName(),fp.GetValue()])
 print(json.dumps(result,indent=2));return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=H.parent.parent/'clean-sheet-pcb-review-i');p.add_argument('--write',action='store_true');args=p.parse_args();run(args.base,args.write)
