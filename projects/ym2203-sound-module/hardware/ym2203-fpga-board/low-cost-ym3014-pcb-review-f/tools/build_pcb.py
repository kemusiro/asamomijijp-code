#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Initial F placement. Routed .kicad_pcb is authoritative after routing/review."""
from pathlib import Path
import os,sys,json,math,re,xml.etree.ElementTree as ET
import pcbnew as P
H=Path(__file__).resolve().parents[1];B=sys.argv[1];D=H/B;NAME={'base':'p2-base-lc-f','module':'p2-ym2203-lc-f','panel':'p2-panel-lc-f'}[B]
LIB=Path(os.environ.get('KICAD10_FOOTPRINT_DIR','/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints' if sys.platform=='darwin' else '/usr/share/kicad/footprints'))
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y));MM=lambda v: [P.ToMM(v.x),P.ToMM(v.y)]
parts={p['ref']:p for p in json.loads((D/'circuit.json').read_text())['parts']};size={'base':(100,100),'module':(100,80),'panel':(100,76)}[B]
b=P.BOARD();b.SetCopperLayerCount(4 if B=='base' else 2);nets={};fps={}
if B=='base':b.SetLayerType(P.In1_Cu,P.LT_POWER)
for q in parts.values():
 for p in q['pins']:
  n=p['net']
  if n and n not in nets:nets[n]=P.NETINFO_ITEM(b,n);b.Add(nets[n])
def load(ref,x,y,a=0,back=False):
 q=parts[ref];lib,name=q['footprint'].split(':');f=P.FootprintLoad(str(H/'P2LC.pretty' if lib=='P2LC' else LIB/(lib+'.pretty')),name);assert f,(ref,name)
 f.SetReference(ref);f.SetValue(q['value']);b.Add(f)
 if back:f.Flip(V(0,0),True)
 f.SetPosition(V(x,y));f.SetOrientationDegrees(a);f.SetFPID(P.LIB_ID(lib,name));f.Reference().SetVisible(False);f.Value().SetVisible(False)
 ns={p['num']:p['net'] for p in q['pins']}
 physical={p.GetNumber() for p in f.Pads() if p.GetNumber() and (p.GetNumber()!='MP' or 'MP' in ns)}
 assert physical==set(ns),(ref,physical,set(ns))
 for p in f.Pads():
  if p.GetNumber() in ns and ns[p.GetNumber()]:p.SetNet(nets[ns[p.GetNumber()]])
 fps[ref]=f;return f
# Both physical header tops coincide in assembly coordinates; source male is on underside.
fixed={'base':{
 'JMOD':(25,72,90,False),'UBASE':(64,54,-90,False),'JUSB':(84,86,180,False),'JEDIT':(93,62,-90,False),
 'JPOWER':(4,85,0,False),'JHOST':(65,82,90,False),'JSWD':(83,77,90,False),'JPOT':(7,63,90,False),'JLINE':(68,97,90,False),
 'SWCLOCK':(10,88,90,False),'SWSTOP':(25,82,0,False),'SWTEST':(37,82,0,False),'SWRESET':(49,82,0,False),
 'UAUX':(86,18,0,False),'U13':(40,51,0,False),'Y1':(39,44,0,False),'U17':(42,64,0,False),
 'UADC':(86,48,90,False),'UPANEL':(20,26,0,False),'UESD':(80,81,0,False),'UVBUS':(78,71,0,False),'UMUTE':(44,77,0,False),
 'URXDATA':(81,64,0,False),'CACL':(56,92,0,False),'CACR':(63,92,0,False),'C1':(8,71,0,False),
 },'module':{
 'JMOD':(25,72,-90,True),'USOURCE':(26,30,0,False),'U12':(64,10,0,False),'U8':(48,20,0,False),'U9':(48,38,0,False),
 'UDAC':(88,28,0,False),'UAF':(97,50,180,False),'CRB':(94,37,0,False),'U16':(85,16,0,False),
 'ULINK0':(22,57,0,False),'ULINK1':(55,57,0,False),'URUNOD':(11,26,0,False),'UTXOR':(43,58,0,False),'UALERT':(34,58,0,False),'JSWD':(6,56,0,False),
 },'panel':{
 'UPICO':(32,6,180,True),'JUPLINK':(61,7,0,False),'U1':(83,8,0,False),'UMUX':(40,12,0,False),'ENC1':(70,23,0,False),'J5':(52,6,0,False),'R12':(36,39,0,False),
 }}[B]
if B=='base':
 for i,x in enumerate([9,16,23,30,37,44,51]):fixed['DLED'+str(i)]=(x,96,90,False)
if B=='panel':
 for i,x in enumerate([12,36,60,84],1):fixed['RV'+str(i)]=(x-2.5,71.5,90,False)
 for i,x in enumerate([7,43,60,77],1):fixed['SW'+str(i)]=(x-3.25,43-2.25,0,False)
 fixed['SW5']=(90-3.25,35-2.25,0,False);fixed['SW6']=(92-3.25,43-2.25,0,False)
# Physical courtyards are constraints. Fixed through-hole anchors are never moved silently.
def bb(f):
 r=f.GetBoundingBox(False,False);return [P.ToMM(r.GetLeft()),P.ToMM(r.GetTop()),P.ToMM(r.GetRight()),P.ToMM(r.GetBottom())]
def hit(a,c,g=.3):return a[0]<c[2]+g and a[2]+g>c[0] and a[1]<c[3]+g and a[3]+g>c[1]
def fp_rect(f):
 # Front/back bodies can overlap only with explicit vertical clearance, but drilled pads never can.
 return bb(f)
occupied=[]
for r,pos in fixed.items():
 f=load(r,*pos);a=fp_rect(f)
 occupied.append((r,a,f.GetLayer()))
# Mounting holes. Raised module uses four12mm spacers; base extra feet keep exposed controls supported.
holes=[(3.5,3.5,3.2),(96.5,3.5,3.2),(3.5,76.5,3.2),(96.5,76.5,3.2)] if B!='panel' else [(3.5,18,3.2),(96.5,3.5,3.2),(3.5,53,3.2),(96.5,72.5,3.2)]
if B=='base':holes.extend([(3.5,96.5,3.2),(96.5,96.5,3.2)])
if B=='panel':holes.extend([(6.5,7.5,2.2),(46.22,7.5,2.2),(6.5,34.5,2.2),(46.22,34.5,2.2)])
for i,(x,y,d) in enumerate(holes,1):
 f=P.FOOTPRINT(b);f.SetReference('H'+str(i));f.SetValue('M2 LCD 12mm' if d==2.2 else 'M3 support');f.SetAttributes(P.FP_BOARD_ONLY|P.FP_EXCLUDE_FROM_BOM|P.FP_EXCLUDE_FROM_POS_FILES);f.SetPosition(V(x,y));b.Add(f)
 p=P.PAD(f);p.SetAttribute(P.PAD_ATTRIB_NPTH);p.SetShape(P.PAD_SHAPE_CIRCLE);p.SetSize(V(d,d));p.SetDrillSize(V(d,d));p.SetLayerSet(P.LSET.AllCuMask());p.SetPosition(V(x,y));f.Add(p);f.Reference().SetVisible(False);f.Value().SetVisible(False)
 radius=2.5 if d==2.2 else 3.2
 for layer in [P.F_CrtYd,P.B_CrtYd]:
  c=P.PCB_SHAPE(f);c.SetShape(P.SHAPE_T_CIRCLE);c.SetCenter(V(x,y));c.SetEnd(V(x+radius,y));c.SetLayer(layer);c.SetWidth(P.FromMM(.05));f.Add(c)
 occupied.append((f.GetReference(),[x-radius,y-radius,x+radius,y+radius],None))
# Small parts use nearest functional pin, with explicit decoupling anchors instead of a global power centroid.
owners={'base':{'C21':('U13','1'),'C22':('U13','7'),'C28':('U17','2'),'C29':('U17','5'),'C30':('U17','18'),'C31':('U17','1'),'C32':('U17','8'),'C33':('U17','20'),'C34':('U17','8'),'C35':('U17','20'),'CPANEL':('UPANEL','9'),'CAUXIN':('UAUX','3'),'CAUXOUT':('UAUX','2'),'CUMUTE':('UMUTE','5'),'CADCAV0':('UADC','8'),'CADCAV1':('UADC','8'),'CADCDV0':('UADC','13'),'CADCDV1':('UADC','13'),'CADCIO0':('UADC','14'),'CADCIO1':('UADC','14'),'CADCLDO0':('UADC','11'),'CADCLDO1':('UADC','11'),'CADCVREF':('UADC','6'),'CURXDATA':('URXDATA','5'),'CPANELPORT':('JEDIT','3'),'CVBUS':('UESD','5'),'CVB3':('UVBUS','5'),'C2':('UBASE','J1.1')},
 'module':{'C11':('U8','1'),'C12':('U8','23'),'C13':('U9','23'),'C14':('U9','1'),'C15':('U8','24'),'C16':('U9','24'),'C19':('U12','21'),'C20':('U12','21'),'C27':('U16','14'),'CCORE':('USOURCE','J1.1'),'CCOREB':('USOURCE','J1.1'),'CURUNOD':('URUNOD','5'),'CUTXOR':('UTXOR','5'),'CULINK0':('ULINK0','14'),'CULINK1':('ULINK1','14'),'CUALERT':('UALERT','5'),'CFMDAC':('UDAC','1'),'COPAMP':('UAF','8'),'CANABULK':('UAF','8'),'RFMSD':('UDAC','7'),'RFMCLK':('UDAC','10'),'RFMSH':('UDAC','4'),'RFMOUT':('UAF','7')},
 'panel':{'C1':('UPICO','36'),'C2':('U1','8'),'C3':('J5','2'),'C4':('J5','2'),'CPIN':('UPICO','39'),'CMUX':('UMUX','16')}}[B]
rails={'GND','V3V3','AV3V3','V5_CARRIER','MCU_3V3','V5_MODULE','V3_AUX','PANEL_3V3','UPLINK_3V3','PANEL_VSYS'}
# Cache metal pad obstacles on opposite side; bodies can overlap with raised Pico only.
def padbox(p):
 r=p.GetBoundingBox();return [P.ToMM(r.GetLeft()),P.ToMM(r.GetTop()),P.ToMM(r.GetRight()),P.ToMM(r.GetBottom())]
# Search near anchor first, then widen; .5mm placement grid, rotations checked for good pad escape.
remaining=[r for r in parts if r not in fps]
remaining.sort(key=lambda r:(0 if r in owners else 1,0 if r.startswith('C') else 1,parts[r]['sheet'],r))
for ref in remaining:
 q=parts[ref]
 if ref in owners:
  r,n=owners[ref];point=next(p.GetPosition() for p in fps[r].Pads() if p.GetNumber()==n);ox,oy=MM(point)
 else:
  ns={p['net'] for p in q['pins'] if p['net'] not in rails and p['net']}
  pts=[p.GetPosition() for r,f in fps.items() for p in f.Pads() if p.GetNetname() in ns and r in fixed]
  if pts:ox=sum(P.ToMM(p.x) for p in pts)/len(pts);oy=sum(P.ToMM(p.y) for p in pts)/len(pts)
  else:ox,oy={'base':(30,38),'module':(46,46),'panel':(27,31)}[B]
 f=load(ref,ox,oy);found=False
 candidates=sorted(((dx*.5,dy*.5) for dx in range(-70,71) for dy in range(-70,71)),key=lambda z:z[0]**2+z[1]**2)
 for dx,dy in candidates:
  if found:break
  for ang in [0,90]:
   f.SetOrientationDegrees(ang);f.SetPosition(V(round(ox*2)/2+dx,round(oy*2)/2+dy));a=bb(f)
   if a[0]<1 or a[1]<1 or a[2]>size[0]-1 or a[3]>size[1]-1:continue
   if any(hit(a,c,.3) for _,c,l in occupied if l is None or l==f.GetLayer()):continue
   if any(hit(padbox(p),c,.2) for p in f.Pads() if p.GetAttribute()==P.PAD_ATTRIB_PTH for _,c,l in occupied if l is not None and l!=f.GetLayer()):continue
   if any(hit(padbox(p),padbox(t),.21) for p in f.Pads() for r,other in fps.items() if other!=f and other.GetLayer()!=f.GetLayer() for t in other.Pads() if t.GetAttribute()==P.PAD_ATTRIB_PTH):continue
   found=True;break
 if not found:raise ValueError('No place '+ref)
 occupied.append((ref,bb(f),f.GetLayer()))
# Keep F copper away from unknown underside exposed pads of direct-solder MCU modules.
def keepout(ref,width,length):
 f=fps[ref];poly=P.SHAPE_POLY_SET();poly.NewOutline()
 # Transform a local interior rectangle, 1.4mm inside edge pads.
 for x,y in [(-width/2+1.4,-length/2+.7),(width/2-1.4,-length/2+.7),(width/2-1.4,length/2-.7),(-width/2+1.4,length/2-.7)]:
  theta=math.radians(-f.GetOrientationDegrees());px,py=MM(f.GetPosition());v=V(px+x*math.cos(theta)-y*math.sin(theta),py+x*math.sin(theta)+y*math.cos(theta));poly.Append(v.x,v.y)
 z=P.ZONE(b);z.SetIsRuleArea(True);z.SetLayer(f.GetLayer());z.SetDoNotAllowZoneFills(True);z.SetDoNotAllowTracks(True);z.SetDoNotAllowVias(True);z.SetDoNotAllowPads(False);z.Outline().AddOutline(poly.COutline(0));b.Add(z)
if B=='base':keepout('UBASE',15.24,26.67)
if B=='module':keepout('USOURCE',17.8,36.83)
# Schematic UUID paths + explicit NC nets preserve native schematic parity.
comps={c.get('ref'):c for c in ET.parse(D/'netlist.xml').findall('.//components/comp')}
root=re.search(r'\(uuid ([0-9a-f-]+)\)',(D/(NAME+'.kicad_sch')).read_text())[1]
for ref,f in fps.items():
 c=comps[ref];path=P.KIID_PATH()
 for u in [root]+c.find('sheetpath').get('tstamps').strip('/').split('/')+[c.findtext('tstamps')]:path.push_back(P.KIID(u))
 f.SetPath(path)
for n in ET.parse(D/'netlist.xml').findall('.//nets/net'):
 if n.get('name').startswith('unconnected-'):
  net=P.NETINFO_ITEM(b,n.get('name'));b.Add(net)
  for node in n.findall('node'):
   for p in fps[node.get('ref')].Pads():
    if p.GetNumber()==node.get('pin'):p.SetNet(net)
for a,c in zip([(0,0),(size[0],0),(size[0],size[1]),(0,size[1])],[(size[0],0),(size[0],size[1]),(0,size[1]),(0,0)]):
 t=P.PCB_SHAPE();t.SetShape(P.SHAPE_T_SEGMENT);t.SetStart(V(*a));t.SetEnd(V(*c));t.SetLayer(P.Edge_Cuts);t.SetWidth(P.FromMM(.05));b.Add(t)
# Prototype label, electrical orientation and operator control legends. No branding copied.
def text(s,x,y,layer=P.F_SilkS):
 t=P.PCB_TEXT(b);t.SetText(s);t.SetPosition(V(x,y));t.SetLayer(layer);t.SetTextSize(V(.85,.85));t.SetTextThickness(P.FromMM(.12));b.Add(t)
text('P2 LC-F '+B.upper()+' / 3V3 HOST',50,3 if B=='base' else size[1]-2)
if B=='base':
 for s,x,y in [('STOP',31,86),('TEST',43,86),('RESET',53,86),('HOST 3V3',69,79),('PANEL 3V3',92,54),('5V IN',6,82),('RX  FM1 FM2 FM3  A   B   C',27,99)]:text(s,x,y)
if B=='module':text('37 FM / 39 SSG; I2S reserved',50,65)
if B=='panel':
 for s,x,y in [('OP1',9,48),('OP2',28,48),('OP3',47,48),('OP4',66,48),('NOTE',82,32),('STOP',91,48),('PANEL I2C 3V3 ONLY',82,16)]:text(s,x,y)
# Native design rules: no waiver/exclusion. Only plain through vias, no small filled pad vias.
s=b.GetDesignSettings();s.m_TrackMinWidth=P.FromMM(.2);s.m_MinClearance=P.FromMM(.15);nc=s.m_NetSettings.GetDefaultNetclass();nc.SetClearance(P.FromMM(.15));nc.SetTrackWidth(P.FromMM(.25));nc.SetViaDiameter(P.FromMM(.6));nc.SetViaDrill(P.FromMM(.3))
project=json.loads((H/'tools/design-rules.json').read_text())
rules=project['board']['design_settings']['rules'];rules.update(min_clearance=.15,min_track_width=.2,min_via_diameter=.6,min_through_hole_diameter=.3,min_via_annular_width=.15,min_silk_clearance=.1,min_copper_edge_clearance=.5,min_hole_clearance=.25,min_hole_to_hole=.25)
project['board']['design_settings']['drc_exclusions']=[]
classes=project['net_settings']['classes'];classes[:]=[classes[0]];classes[0].update(clearance=.15,track_width=.25,via_diameter=.6,via_drill=.3)
project['net_settings']['netclass_assignments']=[];project['net_settings']['netclass_patterns']=[];project['meta']['filename']=NAME+'.kicad_pro'
if B=='base':(D/(NAME+'.kicad_dru')).write_text("""(version 1)
(rule \"Si5351 MSOP native pin spacing\" (condition \"A.memberOfFootprint('U13') && B.memberOfFootprint('U13')\") (constraint clearance (min 0.15mm)))
""")
(D/(NAME+'.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
t=P.TITLE_BLOCK();t.SetTitle('P2 LC routed PCB review F / '+B);t.SetRevision('LC-F');t.SetDate('2026-11-19');t.SetComment(0,'Prototype; no firmware or hardware acceptance');b.SetTitleBlock(t)
for f in b.GetFootprints():f.SetLocked(True)
P.SaveBoard(str(D/(NAME+'.kicad_pcb')),b)
assert P.ExportSpecctraDSN(b,str(D/'route.dsn'))
(D/'placement.json').write_text(json.dumps({r:dict(origin_mm=MM(f.GetPosition()),rotation_deg=f.GetOrientationDegrees(),layer=f.GetLayerName(),bounds_mm=bb(f)) for r,f in fps.items()},indent=2)+'\n')
(D/'mounting.json').write_text(json.dumps(dict(size_mm=size,holes_mm=holes,module_gap_mm=12 if B!='panel' else None,lcd_gap_mm=12 if B=='panel' else None),indent=2)+'\n')
print(B,'placed',len(fps),'refs',len(holes),'holes')
