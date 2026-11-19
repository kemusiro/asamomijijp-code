#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Seed K from preserved F, change only clock module and procurement J values.
Final routed PCB is authoritative; rerunning overwrites its local routing.
"""
import pcbnew as P,json,re,xml.etree.ElementTree as ET,os
from pathlib import Path
H=Path(__file__).resolve().parents[1];REF=Path(os.environ.get('P2_REFERENCE_ROOT',str(H.parent)))/'low-cost-ym3014-pcb-review-f'
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))
for board,stem in [('base','p2-base'),('module','p2-ym2203'),('panel','p2-panel')]:
 d=H/board;name=stem+'-lc-k';b=P.LoadBoard(str(REF/board/(stem+'-lc-f.kicad_pcb')))
 parts={p['ref']:p for p in json.loads((d/'circuit.json').read_text())['parts']}
 new_clock=P.FootprintLoad(str(H/'P2LC.pretty'),'AE_Si5351A_B_10x10mm') if board=='base' else None
 removed_fps=[]
 if board=='base':
  for f in list(b.GetFootprints()):
   if f.GetReference() in ('U13','Y1'):b.Remove(f);removed_fps.append(f)
  f=new_clock;f.SetReference('U13');f.SetValue(parts['U13']['value']);b.Add(f);f.SetPosition(V(40,38));f.SetFPID(P.LIB_ID('P2LC','AE_Si5351A_B_10x10mm'));f.SetLocked(True);f.Reference().SetVisible(False);f.Value().SetVisible(False)
  for p in f.Pads():
   net=next(x['net'] for x in parts['U13']['pins'] if x['num']==p.GetNumber());p.SetNet(b.FindNet(net))
  # Interior no-top-copper strip, preserving PTH solder lands on both edges.
  poly=P.SHAPE_POLY_SET();poly.NewOutline()
  for x,y in [(37.35,33),(42.65,33),(42.65,43),(37.35,43)]:v=V(x,y);poly.Append(v.x,v.y)
  z=P.ZONE(b);z.SetIsRuleArea(True);z.SetLayer(P.F_Cu);z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(False);z.Outline().AddOutline(poly.COutline(0));b.Add(z)
  removed=[]
  for t in list(b.GetTracks()):
   if t.GetNetname() in ['XTAL_A','XTAL_B','SI_CLK1','SI_CLK2','SI_YM'] or (t.GetLayer()==P.F_Cu and t.GetEffectiveShape(P.F_Cu).Collide(P.SHAPE_RECT(V(3735/100,33),P.FromMM(5.3),P.FromMM(10)),0)):
    b.Remove(t);removed.append(t)
  # Keep all existing service bus branches; native cleanup prunes only obsolete clock stubs.
  print('Removed clock/keepout tracks',len(removed))
  text=P.PCB_TEXT(b);text.SetText('U13 CLK 3V3');text.SetPosition(V(40,30));text.SetLayer(P.F_SilkS);text.SetTextSize(V(.85,.85));text.SetTextThickness(P.FromMM(.12));b.Add(text)
  (d/(name+'.kicad_dru')).unlink(missing_ok=True)
 for f in b.GetFootprints():
  if f.GetReference() in parts:f.SetValue(parts[f.GetReference()]['value'])
 comps={c.get('ref'):c for c in ET.parse(d/'netlist.xml').findall('.//components/comp')};rootid=re.search(r'\(uuid ([0-9a-f-]+)\)',(d/(name+'.kicad_sch')).read_text())[1]
 for f in b.GetFootprints():
  if f.GetReference() not in comps:continue
  c=comps[f.GetReference()];path=P.KIID_PATH()
  for u in [rootid]+c.find('sheetpath').get('tstamps').strip('/').split('/')+[c.findtext('tstamps')]:path.push_back(P.KIID(u))
  f.SetPath(path)
 for t in b.GetDrawings():
  if isinstance(t,P.PCB_TEXT) and 'LC-F' in t.GetText():t.SetText(t.GetText().replace('LC-F','LC-K'))
 title=b.GetTitleBlock();title.SetRevision('LC-K');title.SetDate('2026-11-20');title.SetTitle('P2 LC review K / '+board+' / Akizuki clock module');b.SetTitleBlock(title)
 P.SaveBoard(str(d/(name+'.kicad_pcb')),b)
 pro=json.loads((d/(name+'.kicad_pro')).read_text());pro['meta']['filename']=name+'.kicad_pro';pro['board']['design_settings']['drc_exclusions']=[];(d/(name+'.kicad_pro')).write_text(json.dumps(pro,indent=2)+'\n')
