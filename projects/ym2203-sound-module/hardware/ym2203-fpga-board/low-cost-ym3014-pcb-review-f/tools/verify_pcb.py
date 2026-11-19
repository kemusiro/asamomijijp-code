#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent all-pin/geometry checks; run with the KiCad Python environment."""
from pathlib import Path
import pcbnew as P,json,hashlib,math,re,os
H=Path(__file__).resolve().parents[1];ROOT=Path(os.environ.get('P2_REFERENCE_ROOT',str(H.parent)));result=dict(date='2026-11-19',kicad_version=P.GetBuildVersion(),boards={},gpio_changed=False,firmware_implemented=False,hardware_accepted=False);boards={};parts={}
for B in ['base','module','panel']:
 D=H/B;N='p2-'+('ym2203' if B=='module' else B)+'-lc-f';b=P.LoadBoard(str(D/(N+'.kicad_pcb')));boards[B]=b;d=json.loads((D/'circuit.json').read_text());old=json.loads((ROOT/'low-cost-ym3014-schematic-review-e'/B/'circuit.json').read_text());parts[B]={p['ref']:p for p in d['parts']};assert len(d['parts'])==len(old['parts'])
 for a,c in zip(d['parts'],old['parts']):assert {k:v for k,v in a.items() if k!='footprint'}=={k:v for k,v in c.items() if k!='footprint'},a['ref']
 fps={f.GetReference():f for f in b.GetFootprints()};assert set(parts[B]).issubset(fps)
 for ref,p in parts[B].items():
  f=fps[ref];expected={str(q['num']):q['net'] for q in p['pins']};actual={q.GetNumber():q.GetNetname() for q in f.Pads() if q.GetNumber() in expected}
  assert set(actual)==set(expected),(B,ref)
  for n,net in expected.items():assert actual[n]==net if net else actual[n].startswith('unconnected-'),(B,ref,n,net,actual[n])
 sizes={'base':(100,100),'module':(100,80),'panel':(100,76)};edge=b.GetBoardEdgesBoundingBox();assert abs(P.ToMM(edge.GetWidth())-sizes[B][0])<.1 and abs(P.ToMM(edge.GetHeight())-sizes[B][1])<.1
 vias=[t for t in b.GetTracks() if isinstance(t,P.PCB_VIA)];tracks=[t for t in b.GetTracks() if not isinstance(t,P.PCB_VIA)]
 assert all(abs(P.ToMM(v.GetDrillValue())-.3)<1e-6 and abs(P.ToMM(v.GetWidth(P.F_Cu))-.6)<1e-6 for v in vias)
 assert all(P.ToMM(t.GetWidth())>=.1999 for t in tracks)
 pro=json.loads((D/(N+'.kicad_pro')).read_text());assert not pro['board']['design_settings'].get('drc_exclusions'),B
 if B=='base':
  inner=[t for t in tracks if t.GetLayer()==P.In1_Cu and t.GetNetname()!='GND'];assert {t.GetNetname() for t in inner}<={'L_MOD_CTL1'};assert sum(P.ToMM(t.GetLength()) for t in inner)<20
  result['base_inner1_signal_escape_mm']=round(sum(P.ToMM(t.GetLength()) for t in inner),3)
  assert any(not z.GetIsRuleArea() and z.GetLayer()==P.In2_Cu and z.GetNetname()=='V5_CARRIER' for z in b.Zones())
  assert any(not z.GetIsRuleArea() and z.GetLayer()==P.In1_Cu and z.GetNetname()=='GND' for z in b.Zones())
  for xy in [(92,15),(92,21),(88,12),(88,27)]:assert any(v.GetNetname()=='V3_AUX' and abs(P.ToMM(v.GetPosition().x)-xy[0])<1e-5 and abs(P.ToMM(v.GetPosition().y)-xy[1])<1e-5 for v in vias)
  result['base_power_planes_and_four_aux_heat_vias_verified']=True
 assert b.GetCopperLayerCount()==(4 if B=='base' else 2)
 drc=json.loads((D/'drc.json').read_text());counts={k:len(drc[k]) for k in ['violations','unconnected_items','schematic_parity']};assert not any(counts.values()),(B,counts)
 erc=json.loads((D/'erc.json').read_text());assert not [v for s in erc['sheets'] for v in s['violations']]
 result['boards'][B]=dict(parts=len(parts[B]),layers=b.GetCopperLayerCount(),size_mm=sizes[B],tracks=len(tracks),vias=len(vias),drc=counts,erc_violations=0,ignored_checks=[v['key'] for v in drc.get('ignored_checks',[])])
# All40 mating coordinates, not just connector origin or one corner.
headers={B:next(f for f in boards[B].GetFootprints() if f.GetReference()=='JMOD') for B in ['base','module']}
positions={B:{p.GetNumber():(p.GetPosition().x,p.GetPosition().y) for p in f.Pads()} for B,f in headers.items()}
assert positions['base']==positions['module'];assert headers['base'].GetLayer()==P.F_Cu and headers['module'].GetLayer()==P.B_Cu
assert set(positions['base'])==set(map(str,range(1,41)));result['g40_all_40_mating_coordinates_match']=True
for n,h in json.loads((H/'preservation.json').read_text())['files'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
c=ROOT/'low-cost-schematic-review-c';p=json.loads((c/'preservation.json').read_text())
for n,h in p['files'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
result['drc_exclusions']=0;result['base_in1_gnd_plane_with_local_control_escape']=True
result['assembly_model_mm']=dict(base_source_gap=12,source_trimmed_leads_max=2.5,low_component_height_max=5,low_component_gap_min=4.5,lcd_standoffs=12,panel_feet=20,physical_fit_accepted=False)
result['installed_refs']=sum(len(v) for v in parts.values());result['preserved_review_e_files']=len(json.loads((H/'preservation.json').read_text())['files']);result['preserved_prior_files']=len(p['files']);result['result']='PASS';result['scope']='Native ERC/DRC, every pin/net, G40 geometry and preservation; no hardware or firmware acceptance'
(H/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
