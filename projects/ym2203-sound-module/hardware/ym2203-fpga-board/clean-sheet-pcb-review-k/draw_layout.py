#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Assembly overview derived from native PCB origins. Detailed copper stays in CAD."""
from pathlib import Path
from html import escape
import json,pcbnew as P
H=Path(__file__).resolve().parent
b=P.LoadBoard(str(H/'base/p2-base-k.kicad_pcb'));s=P.LoadBoard(str(H/'module/p2-ym2203-k.kicad_pcb'))
by={f.GetReference():f for f in b.GetFootprints()};sy={f.GetReference():f for f in s.GetFootprints()}
from stack_checks import rect,mm
out=['<svg xmlns="http://www.w3.org/2000/svg" width="1240" height="1050" viewBox="0 0 248 210">','<rect width="248" height="210" fill="#f7f9fb"/>','<style>text{font-family:sans-serif;fill:#183147} .title{font-weight:bold} .body{fill:#f9fcfd;stroke:#526c7e;stroke-width:.18}</style>']
def text(x,y,t,size=2.7,anchor='start',color=None):out.append(f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}"'+(f' style="fill:{color}"' if color else '')+'>'+escape(t)+'</text>')
def box(a,fill,stroke='#526c7e',width=.3,opacity=1):
 x,y,xx,yy=a;out.append(f'<rect x="{x}" y="{y}" width="{xx-x}" height="{yy-y}" fill="{fill}" stroke="{stroke}" stroke-width="{width}" opacity="{opacity}"/>')
def circle(x,y,r,fill,stroke='#526c7e'):out.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{fill}" stroke="{stroke}" stroke-width=".25"/>')
text(14,10,'P2 review K / 220 × 142 mm',5)
text(14,17,'Opening-free shield + two-layer sound card + exposed right-side controls',3.1)
text(14,23,'Native CAD placement / conditional assembly model / not measured acceptance',2.7)
out.append('<g transform="translate(14 30)">')
box([0,0,220,142],'#e5efeb','#345e50',.6)
box([190,0,220,142],'#d8eadd','#90af98',.2)
# Actual base footprint fabrication/courtyard extents, unobscured by stack outlines.
for r,f in by.items():
 if r.startswith('H') or r.startswith('JUNO') or r in ['MPGA']:continue
 a=rect(f)
 box(a,'#fcfdfb','#93a99d',.12)
for r in ['SWCLOCK','SWSTOP','SWTEST']:
 box(rect(by[r]),'#fff3cb','#b7731f',.5)
for r,f in by.items():
 if r.startswith('H'):
  x,y=mm(f.GetPosition());circle(x,y,1.6,'#ffffff');text(x+2,y+.9,r,1.6)
# UNO shield rectangular projection; no windows.
box([7,7,83,107],'#c4def0','#33729a',.5,.94)
text(45,60,'EDITOR SHIELD',3.4,'middle')
text(45,65,'76 × 100 mm / no cutouts',2.5,'middle')
box([9,16,52.72,48],'#284f70','#203c57',.4)
text(30.8,30,'1.54 inch LCD',2.7,'middle','#fff')
text(30.8,35,'12 mm supports',2.3,'middle','#fff')
for x in [16,35,54,73]:circle(x,97,8,'#516982');circle(x,97,1,'#f2e5c4')
for x,y in [[62.5,33],[62,48],[76,48]]:circle(x,y,3,'#ffffff')
# Source projection and major native bodies.
box([90,38,190,138],'#fff0d7','#b17425',.5,.96)
text(140,46,'YM2203 × 1 SOUND CARD',3.1,'middle')
text(140,51,'100 × 100 mm / 2 layers',2.6,'middle')
for r in ['U12','U8','U9','U16']:
 f=sy[r];a=rect(f);a=[a[0]+90,a[1]+38,a[2]+90,a[3]+38];box(a,'#ecdfcc','#836541',.3);text((a[0]+a[2])/2,(a[1]+a[3])/2,r,2.2,'middle')
box([106.73,102.73,132.13,128.13],'#306c73','#234f55',.4)
text(119.43,113,'Core2350B0',2.4,'middle','#fff')
text(119.43,118,'socketed',2.2,'middle','#fff')
box([97,50,102.54,100.8],'#607682','#294350',.3);text(104,98,'G40',2.4)
box([96.73,6.73,122.13,32.13],'#306c73','#234f55',.4)
text(109.43,17,'PGA2350',2.5,'middle','#fff');text(109.43,22,'socketed',2.2,'middle','#fff')
for r,label in [('JUSB','USB'),('JPOWER','5V IN'),('JHOST','HOST')]:
 x,y=mm(by[r].GetPosition());text(x,y+5,label,2.2,'middle')
text(205,36,'CLOCK',2.7,'middle');text(205,40,'reset-latched',1.9,'middle')
text(206,77,'STOP',2.8,'middle');text(206,100,'TEST',2.8,'middle')
text(20,137,'BASE / 2 layers / 220 × 142 mm',3)
text(84.8,80,'7 mm',2,'middle')
out.append('</g>')
text(14,181,'Source–shield gap: 7 mm',3.1)
text(14,187,'Controls–source: ≥11.225 mm after 0.25 mm body allowance',3.1)
text(14,193,'UNO / G40 / sockets unchanged. 13 resistors moved for two-layer fanout.',3.1)
text(14,199,'ERC / DRC / unrouted / schematic parity: 0. Physical fit & P2 firmware pending.',2.8)
text(14,205,'No change to existing HOST / USB-MIDI / STOP / lease interface requirements.',2.8)
out.append('</svg>');(H/'layout.svg').write_text('\n'.join(out)+'\n')
