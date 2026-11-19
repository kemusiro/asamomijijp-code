#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent all-pin/geometry checks; run with the KiCad Python environment."""
from pathlib import Path
import pcbnew as P,json,hashlib,math,re,os
H=Path(__file__).resolve().parents[1];ROOT=Path(os.environ.get('P2_REFERENCE_ROOT',str(H.parent)));result=dict(date='2026-11-20',kicad_version=P.GetBuildVersion(),boards={},gpio_changed=False,firmware_implemented=False,hardware_accepted=False);boards={};parts={}
for B in ['base','module','panel']:
 D=H/B;N='p2-'+('ym2203' if B=='module' else B)+'-lc-k';b=P.LoadBoard(str(D/(N+'.kicad_pcb')));boards[B]=b;d=json.loads((D/'circuit.json').read_text());old=json.loads((ROOT/'low-cost-ym3014-pcb-review-f'/B/'circuit.json').read_text());parts[B]={p['ref']:p for p in d['parts']};previous={p['ref']:p for p in old['parts']}
 assert set(parts[B])==set(previous)-({'Y1'} if B=='base' else set())
 for ref,c in parts[B].items():
  a=previous[ref]
  if B=='base' and ref=='U13':
   expect={'1':('VDDO','V3V3'),'2':('SCL','SERVICE_SCL'),'3':('SDA','SERVICE_SDA'),'4':('GND','GND'),'5':('CLK0','SI_YM'),'6':('CLK1','SI_CLK1'),'7':('CLK2','SI_CLK2'),'8':('VDD','V3V3')}
   assert {p['num']:(p['name'],p['net']) for p in c['pins']}==expect
   assert c['footprint']=='P2LC:AE_Si5351A_B_10x10mm' and c['value']=='AE-Si5351A-B (110679)'
  elif B=='module' and ref in ('U16','ULINK0','ULINK1','UTXOR'):
   assert a['pins']==c['pins'] and a['footprint']==c['footprint']
   assert c['value']==('SN74LVC1G32DBVRE4' if ref=='UTXOR' else 'SN74LV4T125QPWRQ1')
  else:assert a==c,(B,ref)
 fps={f.GetReference():f for f in b.GetFootprints()};assert set(parts[B]).issubset(fps)
 for ref,p in parts[B].items():
  f=fps[ref];expected={str(q['num']):q['net'] for q in p['pins']};actual={q.GetNumber():q.GetNetname() for q in f.Pads() if q.GetNumber() in expected}
  assert set(actual)==set(expected),(B,ref)
  if B=='base' and ref=='U13':
   xy={q.GetNumber():(round(P.ToMM(q.GetPosition().x),5),round(P.ToMM(q.GetPosition().y),5)) for q in f.Pads()}
   assert xy=={str(n):(round(40+x,5),round(38+y,5)) for n,x,y in [(1,-3.81,-3.81),(2,-3.81,-1.27),(3,-3.81,1.27),(4,-3.81,3.81),(5,3.81,3.81),(6,3.81,1.27),(7,3.81,-1.27),(8,3.81,-3.81)]}
   assert all(abs(P.ToMM(q.GetDrillSize().x)-1.0)<1e-6 for q in f.Pads())
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
for B,b in boards.items():
 name='p2-'+('ym2203' if B=='module' else B)+'-lc-k'
 oldloc=json.loads((ROOT/'low-cost-ym3014-pcb-review-f'/B/'placement.json').read_text())
 loc={}
 for f in b.GetFootprints():
  ref=f.GetReference()
  if ref not in parts[B]:continue
  point=f.GetPosition();box=f.GetBoundingBox(False,False)
  loc[ref]=dict(origin_mm=[P.ToMM(point.x),P.ToMM(point.y)],rotation_deg=f.GetOrientationDegrees(),layer=f.GetLayerName(),bounds_mm=[P.ToMM(box.GetLeft()),P.ToMM(box.GetTop()),P.ToMM(box.GetRight()),P.ToMM(box.GetBottom())])
  if ref!='U13' or B!='base':
   for key in ['origin_mm','rotation_deg','layer']:assert loc[ref][key]==oldloc[ref][key],(B,ref,key)
 (H/B/'placement.json').write_text(json.dumps(loc,indent=2)+'\n')
# Independent projected module courtyard check, excluding its own footprint.
clockrect=[34.5,32.5,45.5,43.5]
for f in boards['base'].GetFootprints():
 if f.GetReference()=='U13':continue
 box=f.GetBoundingBox(False,False);rect=[P.ToMM(box.GetLeft()),P.ToMM(box.GetTop()),P.ToMM(box.GetRight()),P.ToMM(box.GetBottom())]
 assert not (clockrect[0]<rect[2] and clockrect[2]>rect[0] and clockrect[1]<rect[3] and clockrect[3]>rect[1]),f.GetReference()
profile=json.loads((H/'clock-profile.json').read_text())
assert profile['address_7bit']==0x60 and profile['reference_hz']==25000000 and profile['xtal_load_pf']==8
assert profile['full_register_value_if_written']==0x92 and profile['crystal_load_mask']==0xC0
assert profile['default_ym_hz']==4000000 and not profile['public_command_changes'] and not profile['gpio_changes']
result['clock_module_projected_overlap_count']=0;result['clock_profile_25MHz_8pF_0x60_verified']=True
result['all_other_footprint_origins_and_layers_preserved']=True
result['clock_module_body_bounds_mm']=[35,33,45,43]
result['clock_module_pitch_mm']=2.54;result['clock_module_row_spacing_mm']=7.62
# All40 mating coordinates, not just connector origin or one corner.
headers={B:next(f for f in boards[B].GetFootprints() if f.GetReference()=='JMOD') for B in ['base','module']}
positions={B:{p.GetNumber():(p.GetPosition().x,p.GetPosition().y) for p in f.Pads()} for B,f in headers.items()}
assert positions['base']==positions['module'];assert headers['base'].GetLayer()==P.F_Cu and headers['module'].GetLayer()==P.B_Cu
assert set(positions['base'])==set(map(str,range(1,41)));result['g40_all_40_mating_coordinates_match']=True
for n,h in json.loads((H/'preservation.json').read_text())['files'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
c=ROOT/'low-cost-schematic-review-c';p=json.loads((c/'preservation.json').read_text())
for n,h in p['files'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
result['drc_exclusions']=0;result['base_in1_gnd_plane_with_local_control_escape']=True
result['assembly_model_mm']=dict(base_source_gap=12,source_trimmed_leads_max=2.5,low_component_height_max=6,low_component_gap_min=3.5,lcd_standoffs=12,panel_feet=20,physical_fit_accepted=False)
result['installed_refs']=sum(len(v) for v in parts.values());result['preserved_prior_snapshot_files']=len(json.loads((H/'preservation.json').read_text())['files']);result['preserved_prior_files']=len(p['files']);result['result']='PASS';result['scope']='Native ERC/DRC, all276 refs, module8-pin manual mapping, G40 and MCU pin preservation; no hardware or firmware acceptance'
for board,name in [('base','p2-base-lc-k'),('module','p2-ym2203-lc-k'),('panel','p2-panel-lc-k')]:result['boards'][board]['pcb_sha256']=hashlib.sha256((H/board/(name+'.kicad_pcb')).read_bytes()).hexdigest()
(H/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
