#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Place review-H circuits as two four-layer PCB review-J base candidate (source review I reused) (KiCad Python)."""
from pathlib import Path
import json,math,re,sys,xml.etree.ElementTree as E
import pcbnew as P
HERE=Path(__file__).resolve().parent
LIB=Path('/Applications/KiCad/KiCad.app/Contents/SharedSupport/footprints')
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))

def make(side):
 out=HERE/side;name='p2-base-j' if side=='base' else 'p2-ym2203-i'
 parts={q['ref']:q for q in json.loads((out/'circuit.json').read_text())['parts']}
 b=P.BOARD();b.SetCopperLayerCount(4);nets={};fps={}
 for q in parts.values():
  for p in q['pins']:
   if p['net'] and p['net'] not in nets:nets[p['net']]=P.NETINFO_ITEM(b,p['net']);b.Add(nets[p['net']])
 W,H=(220,142) if side=='base' else (100,100)
 holes=([(4,4),(216,4),(216,138),(4,138),(94,42),(186,42),(184,132),(94,134)]+[(76.04,27.78),(76.04,55.72),(25.24,12.54),(23.97,60.8)]) if side=='base' else [(4,4),(96,4),(94,94),(4,96)]
 def load(ref,x,y,a=0):
  q=parts[ref];lib,fpname=q['footprint'].split(':');path=HERE/'P2H.pretty' if lib=='P2H' else LIB/(lib+'.pretty')
  fp=P.FootprintLoad(str(path),fpname);assert fp is not None,(ref,q['footprint'])
  fp.SetReference(ref);fp.SetValue(q['value']);b.Add(fp)
  if side=='module' and ref=='JMOD':fp.Flip(V(0,0),True)
  fp.SetPosition(V(x,y));fp.SetOrientationDegrees(a)
  pp={p['num']:p['net'] for p in q['pins']};assert set(pp)=={p.GetNumber() for p in fp.Pads() if p.GetNumber()},ref
  for pad in fp.Pads():
   if pad.GetNumber() and pp[pad.GetNumber()]:pad.SetNet(nets[pp[pad.GetNumber()]])
  fp.SetFPID(P.LIB_ID(lib,fpname));fp.Value().SetVisible(False);fp.Reference().SetVisible(False);fps[ref]=fp
  return fp
 fixed={}
 if side=='base':
  for r in ['JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR','JUNO_SPI']:fixed[r]=(10,10,0)
  fixed.update({'MPGA':(98,8,0),'JMOD':(97,50,0),'JUSB':(133,4.5,180),'UESD':(133,13,270),'UVBUS':(143,15,0),'JPOWER':(179,8,0),'F1':(169,8,0),'C1':(181,25,0),'UAUX':(160,22,0),'SWRESET':(85,5,0),'SWBOOT':(85,19,0),'JSWD':(152,7,0),'JHOST':(188,17,0),'U13':(145,54,0),'Y1':(145,47,0),'U17':(42,100,0),'UADC':(74,112,0),'FB1':(56,96,0),'UMUTE':(53,109,0),'URXDATA':(109,88,0),'JPOT':(20,118,0),'JLINE':(35,132,90),'UPANEL':(43,76,90),'SWCLOCK':(203,50,0),'SWSTOP':(203,82,0),'SWTEST':(203,105,0),'JP_SDA':(86,40,0),'JP_SCL':(86,45,0),'JP5V':(86,50,0),'DCLAMPL':(85,105,0),'DCLAMPR':(85,115,0)})
  for i in range(7):fixed['DLED'+str(i)]=(125+i*8,33,0)
 else:
  fixed.update({'JMOD':(7,12,180),'U12':(72,17,0),'U8':(54,47,0),'U9':(62,77,0),'U16':(89,76,0),'ULINK0':(20,27,0),'ULINK1':(20,42,0),'UTXOR':(32,51,0),'URUNOD':(15,59,0),'UALERT':(32,57,0),'JSWD':(55,90,90)})
  for i in range(1,5):fixed['JCORE'+str(i)]=(18,66,0)
 for r,loc in fixed.items():load(r,*loc)
 # Body-only extents, not text; composite MCU pad groups are mechanically one module.
 def bounds(fp):
  r=fp.GetReference()
  if r.startswith('JUNO'):
   ps=list(fp.Pads());xx=[P.ToMM(p.GetPosition().x) for p in ps];yy=[P.ToMM(p.GetPosition().y) for p in ps];return [min(xx)-1.5,min(yy)-1.5,max(xx)+1.5,max(yy)+1.5]
  if r=='MPGA':return[96.48,6.48,122.38,32.38]
  if r.startswith('JCORE'):return[16.48,64.48,42.38,90.38]
  bb=fp.GetBoundingBox(False,False);return[P.ToMM(bb.GetLeft()),P.ToMM(bb.GetTop()),P.ToMM(bb.GetRight()),P.ToMM(bb.GetBottom())]
 def hit(a,c,m=.3):return a[0]<c[2]+m and a[2]+m>c[0] and a[1]<c[3]+m and a[3]+m>c[1]
 occupied=[]
 if side=='base':occupied.append(('UNO shield exclusion',[7,7,83,67]))
 # H11 is an UNO bare hole only, no screw head. Preserve all official hole centers.
 for i,(x,y) in enumerate(holes):
  rad=1.75 if side=='base' and i==10 else 3
  occupied.append(('H'+str(i+1),[x-rad,y-rad,x+rad,y+rad]))
 for r,f in fps.items():
  if r.startswith('JUNO'):continue
  if r.startswith('JCORE') and r!='JCORE1':continue
  bb=bounds(f);conf=[s for s,c in occupied if hit(bb,c)]
  if conf:print('fixed conflict',side,r,conf,bb);raise ValueError('fixed placement')
  occupied.append((r,bb))
 # Place local bypass capacitors/pulls by non-rail net affinity, then resolve 0.30mm body gaps.
 rail={'GND','V5_CARRIER','V3V3','V3_AUX','AV3V3','V5_MODULE','MCU_3V3','ADC_3V3','EXT5_IN','USB_VBUS'}
 netanchors={}
 for r,f in fps.items():
  for p in f.Pads():
   if p.GetNetname() not in rail:netanchors.setdefault(p.GetNetname(),[]).append((P.ToMM(p.GetPosition().x),P.ToMM(p.GetPosition().y)))
 # Explicit critical passives by associated IC pad, including all converter decouplers.
 associated={}
 for r in parts:
  if r in fps:continue
  stem=r[1:] if r.startswith('C') else ''
  if stem in fps:associated[r]=stem
 if side=='base':
  associated.update({**{r:'U13' for r in ['C21','C22']},**{r:'U17' for r in ['C28','C29','C30','C31','C32','C33','C34','C35']},'C2':'MPGA','CAUXIN':'UAUX','CAUXOUT':'UAUX','CVBUS':'UESD','CVB3':'UVBUS','RCC1':'JUSB','RCC2':'JUSB','CUMUTE':'UMUTE','CURXDATA':'URXDATA'})
  for r in parts:
   if r.startswith('CADC'):associated[r]='UADC'
 else:
  associated.update({**{r:'U8' for r in ['C11','C12','C13']},**{r:'U9' for r in ['C14','C15','C16']},'C19':'U12','C20':'U12','C27':'U16','CCORE':'JCORE2','CCOREB':'JCORE2','CMOD5':'JMOD'})
 overrides=({'RCLK0':(146,60),'RCLK1':(150,60),'RCLK2':(154,60),'CPANEL':(43,69),
 'RATTL':(92,96),'RSHUNTL':(88,96),'CACL':(84,96),'RLIMITL':(78,106),'CAAFL':(80,106),
 'RATTR':(92,100),'RSHUNTR':(88,100),'CACR':(84,100),'RLIMITR':(78,108),'CAAFR':(80,108),
 'R53':(35,108),'C38':(31,108),'R53R':(46,108),'C38R':(46,111)} if side=='base' else
 {'C19':(89,63),'C20':(94,63),'RS3':(85,72),'RS6':(85,76),'RS8':(85,80),
 'R39':(66,14),'RSMIXA':(66,59),'RSMIXB':(66,62),'RSMIXC':(66,65)})
 items=[r for r in parts if r not in fps];items.sort(key=lambda r:(r not in overrides,r not in associated,not r.startswith('C'),r))
 candidates=sorted(((dx*.5,dy*.5) for dx in range(-80,81) for dy in range(-80,81)),key=lambda q:q[0]**2+q[1]**2)
 for r in items:
  q=parts[r];pts=[]
  for p in q['pins']:
   if p['net'] not in rail:pts+=netanchors.get(p['net'],[])
  if r in overrides:ox,oy=overrides[r]
  elif r in associated:
   target=fps[associated[r]]
   relevant=[p for p in target.Pads() if p.GetNetname() in {t['net'] for t in q['pins']} and p.GetNetname()!='GND']
   pp=relevant[0].GetPosition() if relevant else target.GetPosition();ox,oy=P.ToMM(pp.x),P.ToMM(pp.y)
  elif pts:ox,oy= sum(p[0] for p in pts)/len(pts),sum(p[1] for p in pts)/len(pts)
  else:ox,oy=(150,25) if side=='base' else (45,40)
  f=load(r,ox,oy)
  for dx,dy in candidates:
   f.SetPosition(V(round(ox*2)/2+dx,round(oy*2)/2+dy));bb=bounds(f)
   if bb[0]<2 or bb[1]<2 or bb[2]>W-2 or bb[3]>H-2:continue
   if not any(hit(bb,c) for s,c in occupied):break
  else:raise ValueError('No place '+r)
  occupied.append((r,bb))
 # Native schematic identities, including NC pads, for parity verification.
 comps={c.get('ref'):c for c in E.parse(out/'netlist.xml').findall('.//components/comp')}
 root=re.search(r'\(uuid ([0-9a-f-]+)\)',(out/(name+'.kicad_sch')).read_text())[1]
 for r,f in fps.items():
  c=comps[r];path=P.KIID_PATH()
  for u in [root]+c.find('sheetpath').get('tstamps').strip('/').split('/')+[c.findtext('tstamps')]:path.push_back(P.KIID(u))
  f.SetPath(path)
 for n in E.parse(out/'netlist.xml').findall('.//nets/net'):
  if n.get('name').startswith('unconnected-'):
   net=P.NETINFO_ITEM(b,n.get('name'));b.Add(net)
   for node in n.findall('node'):
    for p in fps[node.get('ref')].Pads():
     if p.GetNumber()==node.get('pin'):p.SetNet(net)
 for i,(x,y) in enumerate(holes):
  fp=P.FootprintLoad(str(LIB/'MountingHole.pretty'),'MountingHole_3.2mm_M3');fp.SetReference('H'+str(i+1));fp.SetPosition(V(x,y));b.Add(fp);fp.Reference().SetVisible(False);fp.Value().SetVisible(False);fp.SetAttributes(fp.GetAttributes()|P.FP_BOARD_ONLY|P.FP_EXCLUDE_FROM_BOM|P.FP_EXCLUDE_FROM_POS_FILES)
  if side=='base' and i==10:
   for it in list(fp.GraphicalItems()):
    if it.GetLayer()==P.F_CrtYd:fp.Remove(it)
   c=P.PCB_SHAPE(fp);c.SetShape(P.SHAPE_T_CIRCLE);c.SetCenter(fp.GetPosition());c.SetEnd(fp.GetPosition()+V(1.75,0));c.SetLayer(P.F_CrtYd);c.SetWidth(P.FromMM(.05));fp.Add(c)
 def line(x,y,xx,yy,layer=P.Edge_Cuts):
  t=P.PCB_SHAPE();t.SetShape(P.SHAPE_T_SEGMENT);t.SetStart(V(x,y));t.SetEnd(V(xx,yy));t.SetLayer(layer);t.SetWidth(P.FromMM(.1));b.Add(t)
 for v in [(0,0,W,0),(W,0,W,H),(W,H,0,H),(0,H,0,0)]:line(*v)
 def label(s,x,y,size=1,layer=P.F_SilkS):
  t=P.PCB_TEXT(b);t.SetText(s);t.SetPosition(V(x,y));t.SetTextSize(V(size,size));t.SetTextThickness(P.FromMM(.12));t.SetLayer(layer);b.Add(t)
 label('P2 / PCB REVIEW J / '+side.upper(),W/2,H-2.5,1)
 if side=='base':
  label('UNO R3 / 3V3 ONLY',44,30,1.2)
  for v in [(90,38,190,38),(190,38,190,138),(190,138,90,138),(90,138,90,38)]:line(*v,layer=P.Dwgs_User)
  label('SOURCE MODULE ABOVE / z=11.05 nominal',140,132,.9,layer=P.Dwgs_User)
 else:
  for v in [(16.73,64.73,42.13,64.73),(42.13,64.73,42.13,90.13),(42.13,90.13,16.73,90.13),(16.73,90.13,16.73,64.73)]:line(*v,layer=P.Dwgs_User)
  label('Core2350B0 - NOT PGA2350',29,62,.8)
  label('JMOD ON BACK / PIN6 KEY',25,4,.8)
 # Hide legacy per-footprint silk graphics only where dense labels/pads make them misleading;
 # retain native body fabrication/courtyard layers, and use generated assembly map for designators.
 for fp in b.GetFootprints():
  fp.SetLocked(True)

 settings=b.GetDesignSettings();settings.m_TrackMinWidth=P.FromMM(.15);settings.m_MinClearance=P.FromMM(.15)
 nc=settings.m_NetSettings.GetDefaultNetclass();nc.SetClearance(P.FromMM(.15));nc.SetTrackWidth(P.FromMM(.18));nc.SetViaDiameter(P.FromMM(.45));nc.SetViaDrill(P.FromMM(.2))
 (out/'placement.json').write_text(json.dumps({r:dict(x_mm=P.ToMM(f.GetPosition().x),y_mm=P.ToMM(f.GetPosition().y),rotation_deg=f.GetOrientationDegrees(),layer=f.GetLayerName(),bounds_mm=bounds(f)) for r,f in fps.items()},indent=2)+'\n')
 (out/'body-clearances.json').write_text(json.dumps(dict(clearance_mm=.3,board_mm=[W,H],bounds=dict(occupied)),indent=2)+'\n')
 P.SaveBoard(str(out/'placed.kicad_pcb'),b)
 project=json.loads((HERE/'design-rules.json').read_text());project['net_settings']['netclass_patterns']=[]
 (out/(name+'.kicad_pro')).write_text(json.dumps(project,indent=2)+'\n')
 print(side,'placed',len(parts),'board',W,H,flush=True)
 return b
if __name__=='__main__':make(sys.argv[1])
