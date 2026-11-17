#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original vector assembly view from native-pad and mechanical reports."""
from pathlib import Path
from html import escape
import json
H=Path(__file__).resolve().parent;g=json.loads((H/'mechanical-geometry.json').read_text());out=[]
def add(s):out.append(s)
def text(x,y,s,size=16,col='#d7e2ef',anchor='start'):add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{col}" text-anchor="{anchor}">{escape(s)}</text>')
def rect(x,y,w,h,col,stroke='#82a8a0',dash=False):add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" fill="{col}" stroke="{stroke}"'+(' stroke-dasharray="5 4"' if dash else '')+'/>')
def circle(x,y,r,col,stroke='#9aabbc'):add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{col}" stroke="{stroke}"/>')
add('<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="950" viewBox="0 0 1400 950"><style>text{font-family:Arial,Helvetica,sans-serif}</style>')
rect(0,0,1400,950,'#11202e',stroke='none');text(40,43,'P2 YM2203 EDITOR B / ROUTED PCB REVIEW A',26);text(40,70,'76 x 100 mm / 2 copper layers / prototype CAD; physical fit and firmware acceptance pending',17,'#9cb4c9')
X=lambda x:100+(x+3)*5;Y=lambda y:108+(y+3)*5
poly=' '.join(f'{X(x)},{Y(y)}' for x,y in g['outline_local_mm']);add(f'<polygon points="{poly}" fill="#1d6757" stroke="#96bdae" stroke-width="2"/>')
poly=' '.join(f'{X(x)},{Y(y)}' for x,y in g['clock_window_local_mm']);add(f'<polygon points="{poly}" fill="#11202e" stroke="#a6c7b8"/>')
# Native UNO contact coordinates, actual top view of underside male rows.
pads=json.loads((H/'native-pads.json').read_text())
for r in ['J1','J2','J3','J4']:
 for p in pads[r]:circle(X(p['at_mm'][0]-10),Y(p['at_mm'][1]-10),3.1,'#d3bc69')
for r,x,y,d in g['holes_local_mm']:circle(X(x),Y(y),d*2.5,'#11202e')
# LCD in landscape CCW; header faces left, no shaft/cable overlap.
rect(X(-1),Y(6),43.72*5,32*5,'#0c1724');rect(X(3),Y(10),28*5,24*5,'#10364a',stroke='#316078');text(X(5),Y(15),'07 / Brass *',13,'#7ce6bd');text(X(5),Y(21),'OP2 ENVELOPE',12);text(X(5),Y(27),'AR31 DR12',13);text(X(5),Y(32),'SR04 RR08',13)
for r,x,y,d in g['holes_local_mm']:
 if r.startswith('HL'):circle(X(x),Y(y),5,'#11202e')
for y in [13.11+i*2.54 for i in range(8)]:circle(X(.5),Y(y),2,'#c2ac62')
add(f'<path d="M{X(.5)} {Y(22)} H{X(-12)} V{Y(44)} H{X(42)}" fill="none" stroke="#92c9ed" stroke-width="6" stroke-dasharray="6 4"/>');text(45,Y(47),'LCD cable exits LEFT',13,'#92c9ed')
circle(X(52.5),Y(23),31,'#34485a');circle(X(52.5),Y(23),11,'#acbdcc');text(X(52.5),Y(15),'ENC',12,anchor='middle')
for i,x in enumerate([5,18,31,44],1):rect(X(x)-15,Y(59)-15,30,30,'#354b60');text(X(x),Y(65),'OP'+str(i),12,anchor='middle')
for x,name,col in [(52,'NOTE','#548fd6'),(66,'STOP','#d36260')]:rect(X(x)-15,Y(38)-15,30,30,col);text(X(x),Y(33),name,12,anchor='middle')
rect(X(25),Y(68),10*5,11*5,'#283a4b');text(X(30),Y(74),'EEPROM',10,anchor='middle')
text(X(59),Y(68),'CLOCK',12,anchor='middle');text(X(59),Y(73),'ACCESS',12,anchor='middle')
for i,(x,y) in enumerate(g['pot_axis_local_mm'],1):circle(X(x),Y(y),40,'#233546');circle(X(x),Y(y),23,'#61778b');text(X(x),Y(y)-44,'K'+str(i),13,anchor='middle')
text(100,650,'Top view; LCD shown installed. Copper and hidden parts: native PCB.',14,'#9cb4c9');text(100,675,'19 mm knob pitch / 16 mm knobs / backside male UNO contacts',14)
text(100,710,'Left cutout: base STOP access',16);text(100,735,'Small lower-left notch: base TEST access',16);text(100,760,'Window: base clock DIP; change clock while stopped',16);text(100,795,'LCD: 4 insulating 12 mm supports; detach for solder repair',15,'#92c9ed')
# Base stack footprint plan.
text(650,116,'ON BASE REVIEW I / SAME XY FRAME',20)
BX=lambda x:650+x*3;BY=lambda y:145+y*3
rect(BX(0),BY(0),194*3,142*3,'#243849');rect(BX(90),BY(38),100*3,100*3,'#3b4352');text(BX(140),BY(80),'YM2203 SOURCE',17,anchor='middle')
rect(BX(108),BY(104),25.4*3,25.4*3,'#59677a');text(BX(108),BY(101),'Waveshare Core2350B0',13)
rect(BX(96.48),BY(6.48),25.9*3,25.9*3,'#4c6675');text(BX(125),BY(20),'PGA2350',13)
poly=' '.join(f'{BX(x+10)},{BY(y+10)}' for x,y in g['outline_local_mm']);add(f'<polygon points="{poly}" fill="#1d6757" stroke="#9bc8b7" stroke-width="1.5"/>')
poly=' '.join(f'{BX(x+10)},{BY(y+10)}' for x,y in g['clock_window_local_mm']);add(f'<polygon points="{poly}" fill="#243849" stroke="#9bc8b7"/>')
text(BX(42),BY(43),'EDITOR',20,anchor='middle');text(BX(86.5),BY(30),'7 mm',13,anchor='middle');text(650,600,'USB, source module and its MCU retain base-I positions.',15,'#9cb4c9')
# Conditional vertical envelopes, deliberately labels rather than a case guarantee.
text(650,650,'CONDITIONAL STACK / NOT MEASURED',20)
rect(650,820,650,8,'#436d80');text(1310,828,'BASE',13)
rect(650,735,650,8,'#287964');text(1310,743,'SHIELD',13)
rect(695,685,300,6,'#385775');text(1010,691,'LCD +12 mm',15)
rect(720,798,80,22,'#778da1');text(720,855,'base SMT <=3 mm',15)
rect(860,743,12,25,'#d1b063');text(890,775,'leads <=3 mm',15)
text(650,888,'Base/shield face gap >=10.5 mm; remaining SMT cavity >=4.5 mm.',15,'#a9d8c6');text(650,916,'No automatic replay; HOST/MIDI/STOP firmware contracts unchanged.',15,'#a9d8c6')
add('</svg>');(H/'assembly.svg').write_text('\n'.join(out)+'\n')
