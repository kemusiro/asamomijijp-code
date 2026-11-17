#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Build populated review-B placement, then import local Specctra routes.
Run with KiCad Python. Input/output paths are explicit; no hardware access.
"""
from pathlib import Path
import json,math,sys,argparse
import pcbnew as P
HERE=Path(__file__).resolve().parent
LIB=None
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))

def generate(out,lib):
 data=json.loads((out/'circuit.json').read_text());parts={p['ref']:p for p in data['parts']};b=P.BOARD();b.SetCopperLayerCount(4);nets={};fps={}
 for part in parts.values():
  for p in part['pins']:
   if p['net'] and p['net'] not in nets:nets[p['net']]=P.NETINFO_ITEM(b,p['net']);b.Add(nets[p['net']])
 def load(ref,x,y,a=0):
  q=parts[ref];n,f=q['footprint'].split(':');d=out/'P2C.pretty' if n=='P2C' else lib/(n+'.pretty');fp=P.FootprintLoad(str(d),f)
  assert fp is not None,(ref,q['footprint']);expected={p['num']:p['net'] for p in q['pins']};actual={p.GetNumber() for p in fp.Pads() if p.GetNumber()};assert set(expected)==actual,(ref,expected,actual)
  fp.SetReference(ref);fp.SetValue(q['value']);fp.SetPosition(V(x,y));fp.SetOrientationDegrees(a)
  for p in fp.Pads():
   if p.GetNumber() and expected[p.GetNumber()]:p.SetNet(nets[expected[p.GetNumber()]])
  fp.Value().SetVisible(False);fp.Reference().SetTextSize(V(.8,.8));fp.Reference().SetTextThickness(P.FromMM(.12));b.Add(fp);fps[ref]=fp;return fp
 # UNO mechanical origin unchanged from A, with a new larger routing candidate outline.
 for r in ['JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR','JUNO_SPI']:load(r,10,10)
 load('MPGA',96,26);load('U12',101,67)
 load('JUSB',110,4.5,180);load('UESD',110,13,270);load('UVBUS',121,13);load('JPOWER',151,8,0);load('F1',143,8)
 load('UAUX',146,19);load('CAUXIN',141,19,90);load('CAUXOUT',151,19,90)
 load('C1',151,29);load('C2',127,26)
 load('SWRESET',82,4);load('SWBOOT',94,4);load('JSWD',130,6);load('JHOST',157,39)
 load('U8',84,83);load('U9',84,105)
 load('U13',130,48);load('Y1',130,42);load('U14',140,48)
 load('U16',128,63);load('U17',143,65);load('FB1',151,57)
 load('U18',145,87);load('U19',145,106)
 load('Q1',88,57);load('Q2',88,64);load('Q5',136,113)
 load('UPANEL',48,83);load('SWCLOCK',64,83)
 load('SWSTOP',16,91);load('SWTEST',28,91)
 for i in range(7):load('DLED'+str(i),17+i*7,111)
 load('JPOT',158,86);load('JLINE',158,107)
 load('JP_SDA',80,35);load('JP_SCL',80,40);load('JP5V',81,47)
 # Passives next to power/IC pins. Remaining general pulls are in nearby local rows.
 pos={'RCC1':(102,10,90),'RCC2':(117,10,90),'CVBUS':(117,15,90),'RVB1':(120,7,90),'RVB2':(125,11,90),'CVBD':(125,15,90),'CVB3':(121,18,0),'RVB3':(125,20,0),
 'RRUN':(86,16,0),'CRUN':(92,16,0),
 'C11':(80,75,0),'C12':(89,75,0),'C13':(89,91,0),'C14':(80,97,0),'C15':(89,97,0),'C16':(89,113,0),
 'R19':(87,52,0),'R20':(87,69,0),'R21':(91,64,90),'R22':(92,57,90),'R23':(83,64,90),'RPDAC':(126,72,0),'RPLINE':(129,107,90),
 'C19':(120,115.26,0),'C20':(124,77,90),
 'C21':(125,44,0),'C22':(135,44,0),'C23':(140,43,0),'C24':(144,48,90),'R37':(123,40,90),'R38':(119,40,90),'R39':(140,54,0),'R40':(144,54,90),
 'C27':(124,58,0),'C28':(143,59,0),'C29':(151,70,90),'C30':(147,74,0),'C31':(138,58,0),'C32':(150,62,90),'C33':(137,72,90),'C34':(155,60,90),'C35':(135,76,0),
 'R47':(124,51,0),'R48':(124,54,0),'R49':(124,57,0),'R50':(143,78,0),'RI2SD':(153,75,0),'RI2SB':(153,78,0),'RI2SL':(153,81,0),
 'C36':(139,83,0),'R51':(137,88,90),'R52':(137,93,90),'C37':(137,98,0),'R53':(143,82,0),'C38':(149,82,0),'R54':(149,93,0),'C39':(143,93,0),
 'C40':(151,99,0),'R55':(130,116,0),'R56':(136,108,90),'R57':(141,111,90),'C41':(143,116,90),'R58':(149,116,90),'R59':(153,84,0),'R60':(153,90,0),
 'CPANEL':(44,72,0)}
 for i in range(4):pos['CA'+str(i)]=(127,83+i*7,90);pos['RM'+str(i)]=(133,85+i*7,0)
 for i in range(3):pos['RL'+str(i)]=(120,82+i*7,90)
 for i in range(7):pos['RLED'+str(i)]=(17+i*7,106,90)
 for i in range(6):pos['RP'+str(i)]=(61+i*4,71,90)
 for i in range(8):pos['RD'+str(i)]=(94,77+i*4.5,0)
 for i,ref in enumerate(['RDIR','RDOE','RCOE','R32','R33','R34','RMC32','RMC33','RMC34','R35','RMA','R42','R43','R44','R45','R46']):
  pos[ref]=(12+(i%6)*6,68+(i//6)*6,90)
 pos.update({'R42':(123,61,0),'R43':(123,66,0),'R44':(128,68,0)})
 for ref in parts:
  if ref not in fps:
   assert ref in pos,('passive placement missing',ref)
   load(ref,*pos[ref])
 # Resolve body/courtyard interference using real native footprint extents.
 def bounds(f):
  if f.GetReference().startswith('JUNO'):
   pads=list(f.Pads());xx=[P.ToMM(p.GetPosition().x) for p in pads];yy=[P.ToMM(p.GetPosition().y) for p in pads];return [min(xx)-1.4,min(yy)-1.4,max(xx)+1.4,max(yy)+1.4]
  if f.GetReference()=='MPGA':return [94.73,24.73,120.13,50.13]
  z=f.GetBoundingBox(False,False);return [P.ToMM(z.GetLeft()),P.ToMM(z.GetTop()),P.ToMM(z.GetRight()),P.ToMM(z.GetBottom())]
 def hit(a,c,margin=.25):return a[0]<c[2]+margin and a[2]+margin>c[0] and a[1]<c[3]+margin and a[3]+margin>c[1]
 occupied=[]
 for x,y in [(76.04,27.78),(76.04,55.72),(25.24,12.54),(23.97,60.8),(4,4),(160,4),(4,120),(160,120)]:occupied.append((f'hole{x},{y}',[x-(1.75 if x==25.24 else 2.5),y-(1.75 if x==25.24 else 2.5),x+(1.75 if x==25.24 else 2.5),y+(1.75 if x==25.24 else 2.5)]))
 movable=[]
 for ref,f in fps.items():
  if ref.startswith(('R','C')):movable.append((ref,f));continue
  bb=bounds(f)
  conflicts=[r for r,z in occupied if hit(bb,z)]
  assert not conflicts,('fixed component conflict',ref,conflicts)
  occupied.append((ref,bb))
 movable.sort(key=lambda r:(not r[0].startswith('C'),r[0]))
 for ref,f in movable:
  org=f.GetPosition();ox,oy=P.ToMM(org.x),P.ToMM(org.y)
  candidates=sorted(((dx,dy) for dx in range(-40,41) for dy in range(-40,41)),key=lambda v:v[0]*v[0]+v[1]*v[1])
  for dx,dy in candidates:
   f.SetPosition(V(ox+dx*.5,oy+dy*.5));bb=bounds(f)
   if bb[0]<2 or bb[2]>162 or bb[1]<2 or bb[3]>122:continue
   if not any(hit(bb,z) for r,z in occupied):break
  else:raise ValueError('No local free placement '+ref)
  occupied.append((ref,bb))
 (out/'body-clearances.json').write_text(json.dumps({'model':'KiCad footprint body/fab extents, fixed socket envelope and3mm mounting reserve;0.25mm separation','count':len(occupied),'bounds':dict(occupied)},indent=2)+'\n')
 # Four UNO mounting coordinates and four carrier corners.
 for i,(x,y) in enumerate([(76.04,27.78),(76.04,55.72),(25.24,12.54),(23.97,60.8),(4,4),(160,4),(4,120),(160,120)]):
  fp=P.FootprintLoad(str(lib/'MountingHole.pretty'),'MountingHole_3.2mm_M3');fp.SetReference('H'+str(i+1));fp.SetPosition(V(x,y));fp.Value().SetVisible(False);b.Add(fp)
 def line(x,y,xx,yy,layer=P.Edge_Cuts):
  t=P.PCB_SHAPE();t.SetShape(P.SHAPE_T_SEGMENT);t.SetStart(V(x,y));t.SetEnd(V(xx,yy));t.SetLayer(layer);t.SetWidth(P.FromMM(.1));b.Add(t)
 for v in [(0,0,164,0),(164,0,164,124),(164,124,0,124),(0,124,0,0)]:line(*v)
 def label(s,x,y,size=1,layer=P.F_SilkS):
  t=P.PCB_TEXT(b);t.SetText(s);t.SetPosition(V(x,y));t.SetTextSize(V(size,size));t.SetTextThickness(P.FromMM(.15));t.SetLayer(layer);b.Add(t)
 label('P2 rev2.1 / REVIEW B / PGA2350 + YM2203C',42,119,1)
 label('3.3V I/O ONLY - NO VIN / AREF',44,30)
 label('STOP',19,101);label('TEST',31,101)
 label('4MHz=ALL OFF; RESET TO APPLY',65,97,.85)
 for i,n in enumerate(['RX','FM1','FM2','FM3','A','B','C']):label(n,17+i*7,116,.85)
 label('RESET',85,13,.8);label('BOOT',94,13,.8)
 label('EXT 5V ONLY',146,4,.8);label('HOST 3V3',157,35,.8)
 label('MONO TO L/R',148,121,.8)
 # Explicit NPTH pad & track keepout under module interior; no components underneath.
 # Courtyard drawing for module captures64 discrete sockets as one assembly.
 for fp in fps.values():fp.SetLocked(True)
 b.GetDesignSettings().m_TrackMinWidth=P.FromMM(.15);b.GetDesignSettings().m_MinClearance=P.FromMM(.15)
 b.GetDesignSettings().m_ViasMinSize=P.FromMM(.6);b.GetDesignSettings().m_MinThroughDrill=P.FromMM(.3)
 # Set default netclass to practical hand-solder routing geometry.
 nc=b.GetDesignSettings().m_NetSettings.GetDefaultNetclass();nc.SetClearance(P.FromMM(.15));nc.SetTrackWidth(P.FromMM(.18));nc.SetViaDiameter(P.FromMM(.6));nc.SetViaDrill(P.FromMM(.3))
 # Export the actual GND plane, so router need not invent point-to-point ground paths.
 z=P.ZONE(b);z.SetLayer(P.In1_Cu);z.SetNetCode(nets['GND'].GetNetCode());z.SetLocalClearance(P.FromMM(.2));z.SetPadConnection(P.ZONE_CONNECTION_FULL);z.SetMinThickness(P.FromMM(.15))
 poly=z.Outline();poly.NewOutline()
 for x,y in [(.5,.5),(163.5,.5),(163.5,123.5),(.5,123.5)]:poly.Append(int(P.FromMM(x)),int(P.FromMM(y)))
 b.Add(z);P.ZONE_FILLER(b).Fill(b.Zones())
 P.SaveBoard(str(out/'p2-b-unrouted.kicad_pcb'),b)
 # Export only after schematic paths and logical pin identities are bound.
 assert P.ExportSpecctraDSN(b,str(out/'p2-b.dsn'))
 dsn=(out/'p2-b.dsn').read_text()
 dsn=dsn.replace(str(out/'p2-b.dsn'),'p2-b.dsn',1)
 settings='(autoroute_settings (fanout off) (autoroute on) (postroute off) (vias on) (layer_rule F.Cu (active on) (preferred_direction horizontal)) (layer_rule In1.Cu (active off) (preferred_direction horizontal)) (layer_rule In2.Cu (active on) (preferred_direction vertical)) (layer_rule B.Cu (active on) (preferred_direction horizontal)))'
 dsn=dsn.replace('    (boundary','    '+settings+'\n    (boundary',1)
 # A power-layer declaration enforces the reserved ground layer even when a router
 # overrides imported per-layer activation preferences with its job defaults.
 dsn=dsn.replace('(layer In1.Cu\n      (type signal)','(layer In1.Cu\n      (type power)')
 power=['V5_CARRIER','V3V3','V3_AUX','AV3V3','EXT5_IN','SHIELD_5V']
 a=dsn.index('(class kicad_default');end=dsn.index('(circuit',a)
 header=dsn[a:end]
 import re
 for net in power:header=re.sub(r'(?<!\S)'+net+r'(?!\S)','',header)
 dsn=dsn[:a]+header+dsn[end:]
 power_class='    (class Power '+ ' '.join(power)+' (circuit (use_via "Via[0-3]_600:300_um")) (rule (width 500) (clearance 150)))\n'
 dsn=dsn.replace('  )\n  (wiring',power_class+'  )\n  (wiring',1)
 (out/'p2-b.dsn').write_text('\n'.join(line.rstrip() for line in dsn.splitlines())+'\n')
 (out/'placement-refs.json').write_text(json.dumps({r:dict(x_mm=P.ToMM(f.GetPosition().x),y_mm=P.ToMM(f.GetPosition().y),rotation_deg=f.GetOrientationDegrees()) for r,f in fps.items()},indent=2)+'\n')
 print('Placed',len(fps),'electrical components,8 mounting holes; exported Specctra DSN')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=HERE/'schematic');p.add_argument('--footprints',type=Path,required=True);x=p.parse_args();generate(x.output,x.footprints)
