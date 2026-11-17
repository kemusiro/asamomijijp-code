#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original vector panel/layout proposal; no vendor image copied."""
from pathlib import Path
from html import escape
out=[]
def add(s):out.append(s)
def text(x,y,s,size=16,fill='#dbe5ee',anchor='start'):
    add(f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" text-anchor="{anchor}">{escape(s)}</text>')
def rect(x,y,w,h,c,stroke='none',radius=0):add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{radius}" fill="{c}" stroke="{stroke}"/>')
def circle(x,y,r,c,stroke='none'):add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{c}" stroke="{stroke}"/>')
add('<svg xmlns="http://www.w3.org/2000/svg" width="1100" height="790" viewBox="0 0 1100 790"><style>text{font-family:Arial,Helvetica,sans-serif} .dash{stroke-dasharray:6 5}</style>')
rect(0,0,1100,790,'#111e2b');text(40,42,'P2 YM2203 VOICE EDITOR SHIELD — REVIEW A',26);text(40,68,'3.3 V / UNO R3 contacts / schematic + panel proposal; not a routed PCB',15,'#9fb2c6')
X=lambda x:50+(x+3)*6;Y=lambda y:92+(y+3)*6
rect(50,92,456,576,'#1c6757','#85b3a4',10)
# shield header contact coordinates, top view
import json
geom=json.loads((Path(__file__).parent/'geometry/uno.json').read_text())['derived_board_header_facts']
for p in geom:
    if p['ref']=='JUNO_SPI':continue
    circle(X(p['x_mm']),Y(p['y_mm']),3,'#d1b45b','#182a25')
# concept display envelope and sample visible LCD
rect(X(-1),Y(6),240,240,'#0a1018','#7b8b96',5)
text(X(2),Y(11),'LCD 40 x 40 mm envelope',11,'#aeb9c5')
rect(X(2),Y(14),204,175,'#0c2332',radius=3)
text(X(4),Y(19),'P07  /  Brass edit *',12,'#6ce6bd')
text(X(4),Y(25),'OP 2  :  ENVELOPE',13)
text(X(4),Y(31),'AR 31      DR 12',16)
text(X(4),Y(37),'SR 04      RR 08',16)
text(X(4),Y(42),'PICKUP  ^     v',12,'#ffd279')
# encoder
circle(X(52),Y(16),48,'#1b2532','#9eb3c4');circle(X(52),Y(16),29,'#4f6173');text(X(52),Y(28),'MENU / FINE',12,anchor='middle')
for x,label,col in [(50,'NOTE','#5ea1f1'),(66,'STOP','#df6d67')]:
    rect(X(x)-18,Y(36)-18,36,36,col,'#c9d4de',5);text(X(x),Y(43),label,13,anchor='middle')
# ICSP must remain clear on the underside
add(f'<rect x="{X(61)}" y="{Y(20)}" width="48" height="66" fill="none" stroke="#efc36b" class="dash"/>')
for x,y in [(66.04,17.78),(66.04,45.72),(13.97,50.8)]:circle(X(x),Y(y),9,'#c3d2ca','#24382c');circle(X(x),Y(y),4,'#172c23')
for i,x in enumerate((5,17,29,41),1):
    rect(X(x)-18,Y(60)-18,36,36,'#404e5d','#d3dbe3',4);text(X(x),Y(55),'OP'+str(i),12,anchor='middle')
# Candidate DIP access cutout, verify actual board before release
rect(X(50),Y(62),102,90,'#111e2b','#99b3a4',3);text(X(58.5),Y(68),'CLOCK',12,anchor='middle');text(X(58.5),Y(73),'ACCESS',12,anchor='middle')
for i,x in enumerate((6,25,44,63),1):
    circle(X(x),Y(85),36,'#1c2835','#b7c5d1');circle(X(x),Y(85),25,'#3e5468');add(f'<path d="M{X(x)} {Y(85)-23}v12" stroke="#eef5fa" stroke-width="3"/>');text(X(x),Y(78.5),'K'+str(i),13,anchor='middle')
text(50,697,'76 x 96 mm enlarged shield / 32 male contacts on underside',15)
text(50,721,'CLOCK window + LCD mounts: final dimensions after sample fit.',13,'#c4d1dc')
text(50,744,'Base STOP is covered; shield STOP uses the same global stop path.',13,'#efc36b')
# enlarged display concept
text(555,111,'COLOR DISPLAY / 240 x 240',20)
rect(555,130,485,340,'#06121e','#577286',10)
rect(569,145,457,38,'#153a4c',radius=4);text(584,171,'07  Brass edit *',21,'#5ce0b4');text(1004,171,'LOCAL',15,'#ffc86d',anchor='end')
text(584,213,'OP 2 / ENVELOPE',24)
for i,(name,value,arrow) in enumerate([('AR','31',''),('DR','12','^'),('SR','04','v'),('RR','08','')]):
    x=584+i*110;rect(x,235,94,74,'#163045',radius=4);text(x+47,258,name,15,'#a2bad1','middle');text(x+47,294,value+arrow,26,anchor='middle')
add('<path d="M590 389 L612 337 L672 364 L750 378 L840 378 L877 413 L1000 413" fill="none" stroke="#65dcb4" stroke-width="3"/>')
text(584,444,'Knobs catch current value before editing.',17,'#efc36b')
text(555,516,'OP1–4     Select operator',19)
text(555,548,'ENCODER   Page / fine edit / hold to SAVE',19)
text(555,580,'NOTE      Audition while held; STOP always wins',19)
text(555,612,'FRAM      64 presets / dual copy / CRC32',19)
text(555,644,'USB CDC   Export and import .voice.json',19)
text(555,696,'Firmware + routed PCB + bench acceptance remain pending.',15,'#9fb2c6')
text(555,724,'No added MCU, USB connector or SD card.',16,'#6ce6bd')
add('</svg>');(Path(__file__).parent/'panel.svg').write_text('\n'.join(out)+'\n')
