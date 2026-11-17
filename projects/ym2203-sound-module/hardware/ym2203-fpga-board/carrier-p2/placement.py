#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run with KiCad's Python (pcbnew). Unrouted header/module placement fixture only."""
import json,sys,math
from pathlib import Path
import pcbnew as P
HERE=Path(__file__).resolve().parent

def make(output,library):
 out=Path(output);library=Path(library);data=json.loads((out/'circuit.json').read_text());parts={p['ref']:p for p in data['parts']};board=P.BOARD()
 def vec(x,y):return P.VECTOR2I(P.FromMM(x),P.FromMM(y))
 nets={}
 for p in parts.values():
  for pin in p['pins']:
   n=pin['net']
   if n and n not in nets:nets[n]=P.NETINFO_ITEM(board,n);board.Add(nets[n])
 # Verify each schematic logical pin set against selected native/custom physical pads.
 checked=[]
 for ref,part in parts.items():
  lib,fp=part['footprint'].split(':');path=out/'P2C.pretty' if lib=='P2C' else library/(lib+'.pretty')
  f=P.FootprintLoad(str(path),fp)
  assert f is not None,(ref,part['footprint'])
  expected={pin['num'] for pin in part['pins']};actual={pad.GetNumber() for pad in f.Pads() if pad.GetNumber()}
  assert expected==actual,(ref,expected,actual)
  checked.append(dict(ref=ref,footprint=part['footprint'],logical_pins=len(expected),physical_pads=len(list(f.Pads()))))
 (out/'footprint-pin-check.json').write_text(json.dumps({'scope':'Pad number membership only; MPN drawing and dimensions require final selection','parts_checked':len(checked),'parts':checked},indent=2)+'\n')
 def footprint(ref,x,y,angle=0):
  part=parts[ref];lib,fp=part['footprint'].split(':');path=out/'P2C.pretty' if lib=='P2C' else library/(lib+'.pretty')
  f=P.FootprintLoad(str(path),fp)
  if f is None:raise ValueError('Missing footprint '+str(path/fp))
  f.SetReference(ref);f.SetValue(part['value']);f.SetPosition(vec(x,y));f.SetOrientationDegrees(angle)
  pd={pin['num']:pin['net'] for pin in part['pins']}
  assert set(pd)=={p.GetNumber() for p in f.Pads() if p.GetNumber()}, (ref,'physical symbol/footprint pin mismatch',set(pd),{p.GetNumber() for p in f.Pads() if p.GetNumber()})
  for pad in f.Pads():
   if pad.GetNumber() and pd[pad.GetNumber()]:pad.SetNet(nets[pd[pad.GetNumber()]])
  board.Add(f)
  return f
 def line(x,y,xx,yy,layer=P.Dwgs_User):
  sh=P.PCB_SHAPE();sh.SetShape(P.SHAPE_T_SEGMENT);sh.SetStart(vec(x,y));sh.SetEnd(vec(xx,yy));sh.SetLayer(layer);sh.SetWidth(P.FromMM(.15));board.Add(sh)
 def rect(x,y,w,h,layer=P.Dwgs_User):
  for a,b,c,d in [(x,y,x+w,y),(x+w,y,x+w,y+h),(x+w,y+h,x,y+h),(x,y+h,x,y)]:line(a,b,c,d,layer)
 def text(s,x,y,size=1.1):
  t=P.PCB_TEXT(board);t.SetText(s);t.SetPosition(vec(x,y));t.SetTextSize(vec(size,size));t.SetTextThickness(P.FromMM(.15));t.SetLayer(P.Dwgs_User);board.Add(t)
 for ref in ['JUNO_D0','JUNO_D8','JUNO_A','JUNO_PWR','JUNO_SPI']:footprint(ref,10,10)
 footprint('MPGA',95,20);footprint('U12',95,65)
 # Four UNO standoffs: mounting-coordinate facts only; no borrowed outline or copper.
 holes=[(66.04,17.78),(66.04,45.72),(15.24,2.54),(13.97,50.8)]
 for i,(x,y) in enumerate(holes):
  f=P.FootprintLoad(str(library/'MountingHole.pretty'),'MountingHole_3.2mm_M3');f.SetReference('H'+str(i+1));f.SetPosition(vec(x+10,y+10));board.Add(f)
 rect(0,0,160,120,P.Edge_Cuts);rect(10,10,68.58,53.34)
 text('UNO R3 SHIELD ENVELOPE / 3.3V ONLY',44,34)
 text('AREF / VIN NC; 5V jumper OPEN',43,39)
 rect(92,17,31.4,31.4);text('PGA2350 socket zone',108,52)
 rect(124,64,31,47);text('DAC / analog / line out',139.5,86);text('PLACEMENT RESERVED',139.5,90)
 rect(12,78,65,30);text('DIP / STOP / TEST / RX + 6 LEDs',44,90)
 text('HARD RESET / BOOTSEL near USB',43,98)
 text('USB-C near PGA top / external5V separate',108,8)
 text('Bus shifters + Si5351 near YM',109,116)
 text('P2 rev2.1 REVIEW A - UNROUTED FIXTURE / NOT FOR FABRICATION',80,3,1)
 assert not list(board.GetTracks())
 P.SaveBoard(str(out/'p2-header-placement.kicad_pcb'),board)
 geometry={'board_outline_mm':[160,120],'status':'unrouted fixture, 7 functional footprints +4 mounting holes; remaining circuitry is reserved zones only','uno_anchor_mm':[10,10],'pga_a1_mm':[95,20],'ym_pin1_mm':[95,65],'uno_standoffs_mm':[[x+10,y+10] for x,y in holes],'shield_envelope_mm':[10,10,78.58,63.34],'pga_zone_mm':[92,17,123.4,48.4],'header_module_clearance_x_mm':13.42,'tracks':0,'fabrication_ready':False,'full_board_drc_pass_claimed':False}
 (out/'placement.json').write_text(json.dumps(geometry,indent=2)+'\n');print('PASS fixture:38 UNO contacts,64 module contacts,40 YM socket contacts; zero tracks')
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--output',type=Path,default=HERE/'schematic');a.add_argument('--footprints',type=Path,required=True);x=a.parse_args();make(x.output,x.footprints)
