# SPDX-License-Identifier: MIT
"""Initial placement generator; final routed native PCB is authoritative."""
from pathlib import Path
import json,re,xml.etree.ElementTree as E,math
import pcbnew as P
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
import os,sys
LIB=Path(os.environ.get('KICAD10_FOOTPRINT_DIR','/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints' if sys.platform=='darwin' else '/usr/share/kicad/footprints'))
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))
parts={q['ref']:q for q in json.loads((ROOT/'circuit.json').read_text())['parts']}
b=P.BOARD();b.SetCopperLayerCount(2);nets={};fps={}
for q in parts.values():
 for p in q['pins']:
  if p['net'] and p['net'] not in nets:nets[p['net']]=P.NETINFO_ITEM(b,p['net']);b.Add(nets[p['net']])
def load(ref,x,y,a=0,back=False):
 q=parts[ref];lib,name=q['footprint'].split(':');f=P.FootprintLoad(str(HERE/'ED2.pretty' if lib=='ED2' else LIB/(lib+'.pretty')),name);assert f
 f.SetReference(ref);f.SetValue(q['value']);b.Add(f)
 if back:f.Flip(V(0,0),True)
 f.SetPosition(V(x+10,y+10));f.SetOrientationDegrees(a)
 ns={p['num']:p['net'] for p in q['pins']}
 for p in f.Pads():
  if p.GetNumber() and ns[p.GetNumber()]:p.SetNet(nets[ns[p.GetNumber()]])
 f.SetFPID(P.LIB_ID(lib,name));f.Reference().SetVisible(False);f.Value().SetVisible(False);fps[ref]=f
 return f
for r in ['J1','J2','J3','J4']:load(r,0,0,back=True)
geom=json.loads((ROOT/'geometry/uno.json').read_text())['derived_board_header_facts']
for r,origin in [('J1','JUNO_D0'),('J2','JUNO_D8'),('J3','JUNO_A'),('J4','JUNO_PWR')]:
 expected={str(t['pin']):(t['x_mm']+10,t['y_mm']+10) for t in geom if t['ref']==origin}
 for p in fps[r].Pads():
  assert max(abs(a-c) for a,c in zip([P.ToMM(p.GetPosition().x),P.ToMM(p.GetPosition().y)],expected[p.GetNumber()]))<.00001,(r,p.GetNumber())

# Pot axis in standard RK09 footprint is (7.5,2.5); rotate90 then position axis explicitly.
for i,x in enumerate([6,25,44,63],1):load('RV'+str(i),x-2.5,87+7.5,90)
load('ENC1',52.5,23)
for i,x in enumerate([5,18,31,44],1):load('SW'+str(i),x-3.25,59-2.25)
load('SW5',52-3.25,38-2.25);load('SW6',66-3.25,38-2.25)
load('U1',25,68)
load('J5',42,44,90)
# Access apertures and mounting holes, all expressed in the same local UNO frame.
outline=[(-3,-3),(73,-3),(73,97),(7,97),(7,96),(-3,96),(-3,81),(12,81),(12,69),(-3,69)]
window=[(50.5,61),(68,61),(68,79),(50.5,79)]
holes=[('H1',66.04,17.78,3.2),('H2',66.04,45.72,3.2),('H3',13.97,50.8,3.2),('HL1',.5,8.5,2.2),('HL2',40.22,8.5,2.2),('HL3',.5,35.5,2.2),('HL4',40.22,35.5,2.2)]
def hole(ref,x,y,d):
 f=P.FOOTPRINT(b);f.SetFPID(P.LIB_ID('ED2','M2_LCD' if d==2.2 else 'M3_UNO'));f.SetReference(ref);f.SetValue('M2 LCD support' if d==2.2 else 'M3 UNO support');f.SetAttributes(P.FP_BOARD_ONLY|P.FP_EXCLUDE_FROM_BOM|P.FP_EXCLUDE_FROM_POS_FILES);b.Add(f);f.SetPosition(V(x+10,y+10));p=P.PAD(f);p.SetAttribute(P.PAD_ATTRIB_NPTH);p.SetShape(P.PAD_SHAPE_CIRCLE);p.SetSize(V(d,d));p.SetDrillSize(V(d,d));p.SetLayerSet(P.LSET.AllCuMask());p.SetPosition(f.GetPosition());f.Add(p);f.Reference().SetVisible(False);f.Value().SetVisible(False)
 # Supports occupy both board faces; clearance checking uses these courtyards.
 for layer in [P.F_CrtYd,P.B_CrtYd]:
  c=P.PCB_SHAPE(f);c.SetShape(P.SHAPE_T_CIRCLE);c.SetCenter(f.GetPosition());c.SetEnd(f.GetPosition()+V(2.5 if d==2.2 else 3.2,0));c.SetLayer(layer);c.SetWidth(P.FromMM(.05));f.Add(c)
 return f
for args in holes:hole(*args)
def bb(f):
 if f.GetReference() in ['J1','J2','J3','J4']:
  pp=list(f.Pads());xx=[P.ToMM(p.GetPosition().x)-10 for p in pp];yy=[P.ToMM(p.GetPosition().y)-10 for p in pp];return[min(xx)-1.4,min(yy)-1.4,max(xx)+1.4,max(yy)+1.4]
 r=f.GetBoundingBox(False,False);return[P.ToMM(r.GetLeft())-10,P.ToMM(r.GetTop())-10,P.ToMM(r.GetRight())-10,P.ToMM(r.GetBottom())-10]
def hit(a,c,m=.5):return a[0]<c[2]+m and a[2]+m>c[0] and a[1]<c[3]+m and a[3]+m>c[1]
occupied=[('DIP access',[49.5,60.5,68.5,79.5]),('STOP notch',[-4,68.5,12.5,81.5]),('TEST notch',[-4,95.5,7.5,98]),('ICSP underside',[61,20,69,31])]
# Native header pads are obstacles even when their bodies are on the back.
for f in b.GetFootprints():occupied.append((f.GetReference(),bb(f)))
rail={'GND','IOREF_3V3','AUX_3V3'}
overrides={'C1':(30,46),'C2':(35,67),'C3':(44,47),'C4':(40,41),'R18':(26,6),'R19':(34,6)}
# ADC RC nearest header; power bypass nearest supply pin.
for r in parts:
 if r in fps:continue
 pts=[p.GetPosition() for f in fps.values() for p in f.Pads() if p.GetNetname() in {n['net'] for n in parts[r]['pins'] if n['net'] not in rail}]
 if r in overrides:ox,oy=overrides[r]
 elif pts:ox=sum(P.ToMM(v.x)-10 for v in pts)/len(pts);oy=sum(P.ToMM(v.y)-10 for v in pts)/len(pts)
 else:ox,oy=(32,45)
 f=load(r,ox,oy)
 candidates=sorted(((dx*.5,dy*.5) for dx in range(-90,91) for dy in range(-90,91)),key=lambda p:p[0]**2+p[1]**2)
 for dx,dy in candidates:
  f.SetPosition(V(round(ox*2)/2+dx+10,round(oy*2)/2+dy+10));a=bb(f)
  if a[0]<-1 or a[1]<-1 or a[2]>71 or a[3]>95:continue
  if any(hit(a,c,.35) for _,c in occupied):continue
  # Keep passive bodies below the raised LCD; elsewhere allow full front courtyard.
  break
 else:raise ValueError('No placement '+r)
 occupied.append((r,a))
# Attach schematic UUID paths, and explicit NC nets to all duplicated mechanical pads.
comps={c.get('ref'):c for c in E.parse(HERE/'netlist.xml').findall('.//components/comp')}
root=re.search(r'\(uuid ([0-9a-f-]+)\)',(HERE/'p2-editor-b.kicad_sch').read_text())[1]
for r,f in fps.items():
 c=comps[r];path=P.KIID_PATH()
 for u in [root]+c.find('sheetpath').get('tstamps').strip('/').split('/')+[c.findtext('tstamps')]:path.push_back(P.KIID(u))
 f.SetPath(path)
for n in E.parse(HERE/'netlist.xml').findall('.//nets/net'):
 if n.get('name').startswith('unconnected-'):
  net=P.NETINFO_ITEM(b,n.get('name'));b.Add(net)
  for node in n.findall('node'):
   for p in fps[node.get('ref')].Pads():
    if p.GetNumber()==node.get('pin'):p.SetNet(net)
def line(a,c,layer=P.Edge_Cuts):
 t=P.PCB_SHAPE();t.SetShape(P.SHAPE_T_SEGMENT);t.SetStart(V(a[0]+10,a[1]+10));t.SetEnd(V(c[0]+10,c[1]+10));t.SetLayer(layer);t.SetWidth(P.FromMM(.1));b.Add(t)
for poly in [outline,window]:
 for a,c in zip(poly,poly[1:]+poly[:1]):line(a,c)
# LCD and knob mechanical envelopes are documentation, not copper keepout: LCD is raised.
for poly in [[(-1,6),(42.72,6),(42.72,38),(-1,38)]]:
 for a,c in zip(poly,poly[1:]+poly[:1]):line(a,c,P.Dwgs_User)
for i,x in enumerate([6,25,44,63],1):
 c=P.PCB_SHAPE();c.SetShape(P.SHAPE_T_CIRCLE);c.SetCenter(V(x+10,97));c.SetEnd(V(x+18,97));c.SetLayer(P.Dwgs_User);c.SetWidth(P.FromMM(.15));b.Add(c)
for text,x,y in [('P2 EDITOR B / PCB A',29,40),('3V3 ONLY / NO 5V SHIELD',31,-.5),('OP1',5,64),('OP2',18,64),('OP3',31,64),('OP4',44,53),('NOTE',52,32),('STOP',66,32),('LCD 1=GND',53,49.5)]:
 t=P.PCB_TEXT(b);t.SetText(text);t.SetPosition(V(x+10,y+10));t.SetLayer(P.F_SilkS);t.SetTextSize(V(.85,.85));t.SetTextThickness(P.FromMM(.12));b.Add(t)
for f in b.GetFootprints():f.SetLocked(True)
s=b.GetDesignSettings();s.m_TrackMinWidth=P.FromMM(.2);s.m_MinClearance=P.FromMM(.2);nc=s.m_NetSettings.GetDefaultNetclass();nc.SetClearance(P.FromMM(.2));nc.SetTrackWidth(P.FromMM(.25));nc.SetViaDiameter(P.FromMM(.6));nc.SetViaDrill(P.FromMM(.3))
t=P.TITLE_BLOCK();t.SetTitle('P2 editor shield B / routed PCB review A');t.SetRevision('B-PCB-A');t.SetDate('2026-11-18');t.SetComment(0,'Prototype CAD; conditional heights, no firmware or hardware acceptance');b.SetTitleBlock(t)
P.SaveBoard(str(HERE/'placed.kicad_pcb'),b)
project=json.loads((HERE/'design-rules.json').read_text());rules=project['board']['design_settings']['rules'];rules.update(min_clearance=.2,min_track_width=.2,min_via_diameter=.6,min_through_hole_diameter=.3,min_silk_clearance=.1)
cl=project['net_settings']['classes'][0];cl.update(clearance=.2,track_width=.25,via_diameter=.6,via_drill=.3);project['meta']['filename']='p2-editor-b.kicad_pro';(HERE/'p2-editor-b.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
(HERE/'placement.json').write_text(json.dumps({r:dict(local_origin_mm=[P.ToMM(f.GetPosition().x)-10,P.ToMM(f.GetPosition().y)-10],rotation_deg=f.GetOrientationDegrees(),layer=f.GetLayerName(),bounds_local_mm=bb(f)) for r,f in fps.items()},indent=2)+'\n')
(HERE/'mechanical-geometry.json').write_text(json.dumps(dict(origin_on_base_mm=[10,10],outline_local_mm=outline,clock_window_local_mm=window,holes_local_mm=holes,lcd_bounds_local_mm=[-1,6,42.72,38],lcd_support_gap_mm=12,pot_axis_local_mm=[[x,87] for x in [6,25,44,63]],knob_diameter_mm=16),indent=2)+'\n')
print('Placed',len(fps),'electrical refs,',len(holes),'mounts; two copper layers')
# Optional placement export; initial routes require separate manual review.
assert P.ExportSpecctraDSN(b,str(HERE/'route.dsn'))
