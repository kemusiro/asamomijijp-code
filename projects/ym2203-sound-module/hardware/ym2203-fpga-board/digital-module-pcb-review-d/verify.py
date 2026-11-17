#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify native placed/routed PCBs against immutable review-C electrical and manufacturer geometry."""
from pathlib import Path
import argparse,json,math,hashlib,xml.etree.ElementTree as E,copy
import pcbnew as P
HERE=Path(__file__).resolve().parent
mm=lambda p:[round(P.ToMM(p.x),5),round(P.ToMM(p.y),5)]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def require(ok,msg):
 if not ok:raise AssertionError(msg)
def contract(s):
 require(s['connector_error_mm']<.0001,'connector mating coordinates')
 require(s['mount_error_mm']<.0001,'source support holes')
 require(s['uno_error_mm']<.0001,'UNO contact geometry')
 require(s['core_error_mm']<.0001,'Core manufacturer header coordinates')
 require(s['electrical_mismatches']==0,'electrical pin/net contract')
 require(s['ground_signal_segments']==0,'reserved ground plane')
 require(s['tall_base_parts_under_source']==[],'stack body clearance')
 require(s['wrong_socket_geometry']==0,'socket annulus/hole')
 require(s['native_drc_failures']==0,'native DRC, parity and unconnected')
 require(s['native_erc_failures']==0,'native ERC')
 require(s['drc_exclusions']==0,'no per-item DRC exclusions')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--reference',type=Path,default=HERE.parent/'digital-module-review-c');args=ap.parse_args();ref=args.reference
 boards={};stats={};placements={};allroutes={};padsite=[];electrical=0;wrong=0;groundsegments=0;tall=[];native=erc=exclusions=0
 for side,name in [('base','p2-base-d'),('module','p2-ym2203-d')]:
  o=HERE/side;file=o/(name+'.kicad_pcb');b=P.LoadBoard(str(file));boards[side]=b
  circuit=json.loads((o/'circuit.json').read_text());prior=json.loads((ref/side/'circuit.json').read_text());parts={q['ref']:q for q in circuit['parts']};old={q['ref']:q for q in prior['parts']}
  require(set(parts)==set(old),'reviewC ref set')
  for r,q in parts.items():require(q['pins']==old[r]['pins'] and q['value']==old[r]['value'],'immutable C circuit '+r)
  fps={f.GetReference():f for f in b.GetFootprints()};byref={};padcount=0
  for r,q in parts.items():
   require(r in fps,'missing footprint '+r);f=fps[r];pp={p.GetNumber():p for p in f.Pads() if p.GetNumber()};require(set(pp)=={p['num'] for p in q['pins']},'physical pad set '+r)
   byref[r]={}
   for p in q['pins']:
    pad=pp[p['num']];padcount+=1;actual=pad.GetNetname();electrical+=int(actual!=p['net']) if p['net'] else int(not actual.startswith('unconnected-'))
    byref[r][p['num']]=dict(xy=mm(pad.GetPosition()),net=p['net'])
    if r=='MPGA' or r.startswith('JCORE'):wrong+=int(abs(P.ToMM(pad.GetDrillSize().x)-1.2)>.0001 or abs(P.ToMM(pad.GetSize().x)-1.9)>.0001)
   f.Reference().SetVisible(False) # In-memory inspection only; no save.
  placements[side]={r:dict(xy=mm(f.GetPosition()),angle=f.GetOrientationDegrees(),layer=f.GetLayerName()) for r,f in fps.items()}
  if side=='base':
   for r,f in fps.items():
    if r.startswith('H') or r=='JMOD':continue
    if any(p.GetDrillSize().x for p in f.Pads()):
     if r=='MPGA':bb=[96.48,6.48,122.38,32.38]
     elif r.startswith('JUNO'):continue
     else:
      z=f.GetBoundingBox(False,False);bb=[P.ToMM(z.GetLeft()),P.ToMM(z.GetTop()),P.ToMM(z.GetRight()),P.ToMM(z.GetBottom())]
     if bb[0]<190 and bb[2]>90 and bb[1]<138 and bb[3]>38:tall.append(r)
  route={};vias=[]
  for t in b.GetTracks():
   n=t.GetNetname();r=route.setdefault(n,dict(length_mm=0,segments=0,layers=set(),vias=0,min_width_mm=99))
   if isinstance(t,P.PCB_VIA):r['vias']+=1;vias.append(t)
   else:
    groundsegments+=int(t.GetLayer()==P.In1_Cu);r['length_mm']+=P.ToMM(t.GetLength());r['segments']+=1;r['layers'].add(t.GetLayerName());r['min_width_mm']=min(r['min_width_mm'],P.ToMM(t.GetWidth()))
  for r in route.values():r['length_mm']=round(r['length_mm'],4);r['layers']=sorted(r['layers']);r['min_width_mm']=round(r['min_width_mm'],4)
  allroutes[side]=route
  # Via drills meeting SMT copper require prefill/flat tinning before hand assembly.
  for v in vias:
   circle=P.SHAPE_CIRCLE(v.GetPosition(),v.GetDrillValue()//2+P.FromMM(.05))
   for r,f in fps.items():
    for pad in f.Pads():
     if pad.GetDrillSize().x or pad.GetNetname()!=v.GetNetname():continue
     for layer in [P.F_Cu,P.B_Cu]:
      if pad.IsOnLayer(layer) and pad.GetEffectiveShape(layer).Collide(circle,0):padsite.append(dict(board=side,ref=r,pin=pad.GetNumber(),net=v.GetNetname(),via_mm=mm(v.GetPosition()),drill_mm=P.ToMM(v.GetDrillValue())));break
  report=json.loads((o/'drc.json').read_text());drc=sum(len(report[k]) for k in ['violations','unconnected_items','schematic_parity']);native+=drc
  ercreport=json.loads((o/'erc.json').read_text());erccount=sum(len(v['violations']) for v in ercreport['sheets']);erc+=erccount
  proj=json.loads((o/(name+'.kicad_pro')).read_text());exclusions+=len(proj['board']['design_settings']['drc_exclusions'])
  stats[side]=dict(electrical_components=len(parts),footprints=len(fps),physical_pad_pin_checks=padcount,segments=sum(not isinstance(t,P.PCB_VIA) for t in b.GetTracks()),vias=len(vias),layers=b.GetCopperLayerCount(),drc_violations=len(report['violations']),unconnected=len(report['unconnected_items']),parity=len(report['schematic_parity']),erc=erccount,ignored_checks=report['ignored_checks'],pcb_sha256=sha(file),schematic_sha256=sha(o/(name+'.kicad_sch')),pins=byref)
 # Connector sex and mirror are verified by actual native pad coordinates.
 bp=stats['base']['pins'];mp=stats['module']['pins'];connector=max(math.dist(bp['JMOD'][str(n)]['xy'],[mp['JMOD'][str(n)]['xy'][0]+90,mp['JMOD'][str(n)]['xy'][1]+38]) for n in range(1,33))
 require(placements['base']['JMOD']['layer']=='F.Cu' and placements['module']['JMOD']['layer']=='B.Cu','connector mating sides')
 mount=max(math.dist(placements['base']['H'+str(n+4)]['xy'],[placements['module']['H'+str(n)]['xy'][0]+90,placements['module']['H'+str(n)]['xy'][1]+38]) for n in range(1,5))
 geom=json.loads((ref.parent/'carrier-p2/header-geometry.json').read_text())['derived_board_header_facts'];uno=max(math.dist(bp[p['ref']][str(p['pin'])]['xy'],[p['x_mm']+10,p['y_mm']+10]) for p in geom)
 core=json.loads((HERE/'core-pad-coordinates.json').read_text())['pins'];coreerr=max(math.dist(mp['JCORE'+p['header'][-1]][str(p['pin'])]['xy'],[p['x_mm']+13,p['y_mm']+60]) for p in core)
 s=dict(connector_error_mm=connector,mount_error_mm=mount,uno_error_mm=uno,core_error_mm=coreerr,electrical_mismatches=electrical,ground_signal_segments=groundsegments,tall_base_parts_under_source=tall,wrong_socket_geometry=wrong,native_drc_failures=native,native_erc_failures=erc,drc_exclusions=exclusions);contract(s)
 mutants={'connector_error_mm':2.54,'mount_error_mm':2,'uno_error_mm':.1,'core_error_mm':2.54,'electrical_mismatches':1,'ground_signal_segments':1,'tall_base_parts_under_source':['C1'],'wrong_socket_geometry':1,'native_drc_failures':1,'native_erc_failures':1,'drc_exclusions':1}
 for k,v in mutants.items():
  bad=copy.deepcopy(s);bad[k]=v
  try:contract(bad)
  except AssertionError:pass
  else:raise AssertionError('regression mutation accepted '+k)
 for side,d in stats.items():
  (HERE/side/'placement-final.json').write_text(json.dumps(placements[side],indent=2)+'\n')
  del d['pins']
 (HERE/'routing-review.json').write_text(json.dumps(dict(scope='sum of native routed segments, including branches; not delay/impedance or audio measurement',nets=allroutes),indent=2)+'\n')
 (HERE/'hand-assembly-vias.json').write_text(json.dumps(dict(policy='SMT drill overlap: bottom tenting; solder-prefill then flatten before fitting IC; alternatively manufacturing filled/capped vias. See ASSEMBLY.md.',count=len(padsite),sites=padsite),indent=2)+'\n')
 result=dict(schema_version=1,date='2026-11-16',tool='KiCad/pcbnew10.0.5',scope='static PCB/net/fit constraints, not P2 firmware or bench acceptance',boards=stats,contract=s,positive_contract_checks=len(s),negative_regression_mutations=len(mutants),uno_contacts=len(geom),core_contacts=len(core),mating_contacts=32,assembly_via_sites=len(padsite),hardware_accepted=False)
 (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:dict(parts=v['electrical_components'],pads=v['physical_pad_pin_checks'],segments=v['segments'],vias=v['vias'],drc=v['drc_violations'],unconnected=v['unconnected'],parity=v['parity'],erc=v['erc']) for k,v in stats.items()}));print('PASS:11 contracts,11 rejection mutations;32 mating pads,38 UNO contacts,64 Core contacts;assembly via sites',len(padsite))
if __name__=='__main__':main()
