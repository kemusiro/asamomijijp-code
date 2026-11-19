#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original footprints drawn from manufacturer dimensions, no vendor library copy."""
from pathlib import Path
HERE=Path(__file__).resolve().parents[1];out=HERE/'P2LC.pretty';out.mkdir(exist_ok=True)
def start(name,desc,kind='through_hole'):
 return f'(footprint "{name}" (version 20241229) (generator pcbnew) (layer "F.Cu") (descr "{desc}") (attr {kind})\n(property "Reference" "REF**" (at 0 -16 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))\n(property "Value" "{name}" (at 0 17 0) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))\n'
def rect(x0,y0,x1,y1,layer='F.CrtYd',width=.05):return f'(fp_rect (start {x0} {y0}) (end {x1} {y1}) (stroke (width {width}) (type default)) (fill none) (layer "{layer}"))\n'
def pad(n,x,y,w,h,drill=None):
 k='thru_hole' if drill else 'smd';layers='"*.Cu" "*.Mask"' if drill else '"F.Cu" "F.Paste" "F.Mask"';shape='rect' if n in ['1','J1.1'] else 'oval' if drill else 'roundrect'
 return f'(pad "{n}" {k} {shape} (at {x:.5f} {y:.5f}) (size {w} {h}) '+(f'(drill {drill}) ' if drill else '')+f'(layers {layers})'+(' (roundrect_rratio .2)' if shape=='roundrect' else '')+')\n'
def save(n,s):(out/(n+'.kicad_mod')).write_text(s+')\n')
# Pad centers are on the castellated edges. GPIO numbering from manufacturer's TOP view.
for typ,width,length in [('A',15.24,26.67),('B',17.8,36.83)]:
 name='Picossci2A_DirectSolder' if typ=='A' else 'Picossci2B_DirectSolder_DebugWire'
 s=start(name,'SwitchScience Picossci2'+typ+';1.27mm edge centers;original project land;three B debug stitching wires and RUN wire require hand assembly','smd')
 y0=-(length/2-1.27)
 if typ=='A':
  left=[('J1.'+str(n),n-1) for n in range(1,21)];right=[('J2.'+str(n),20-n) for n in range(1,21)]
 else:
  left=[('J1.'+str(n),n-1) for n in range(1,21)]+[('JP6.'+str(n),n+19) for n in range(1,9)]
  right=[('J2.'+str(n),20-n) for n in range(1,21)]+[('JP7.'+str(n),28-n) for n in range(1,9)]
 for edge,pins in [(-width/2,left),(width/2,right)]:
  for n,row in pins:s+=pad(n,edge,y0+row*1.27,2.4,.75)
 if typ=='B':
  # Positions from dimensions page2 and pin photograph. Through both PCBs with short wire.
  for n,x,y in [('JP1.1',7.62-width/2,32.51-length/2),('JP1.2',12.70-width/2,32.51-length/2),('JP1.3',10.16-width/2,32.51-length/2)]:s+=pad(n,x,y,1.8,1.8,1.0)
  s+=pad('SW1.S',-11.5,-10,1.8,1.8,.8)
 s+=rect(-width/2,-length/2,width/2,length/2,'F.Fab',.1)
 s+=rect(-width/2-1.6 if typ=='A' else -12.7,-length/2-.5,width/2+1.6,length/2+.5)
 # Wire landing has its own courtyard island; no silent physical module pin assumption.

 s+=f'(fp_text user "TOP 1" (at {-width/2+2} {-length/2+2} 0) (layer "F.Fab") (effects (font (size .8 .8) (thickness .12))))\n'
 save(name,s)
# USB layout TOP view in Neltron5075BR04 drawing: pin1 lowerleft; shell upper row.
n='USB_B_Neltron_5075BR_04_WH';s=start(n,'Neltron2008-12-25;USB-B,opens -Y;pin1=(-1.25,0),pin2=(1.25,0),pin3=(1.25,-2),pin4=(-1.25,-2);shell +/-6.02,-4.71')
for number,x,y in [('1',-1.25,0),('2',1.25,0),('3',1.25,-2),('4',-1.25,-2)]:s+=pad(number,x,y,1.7,1.7,1.0)
for x in [-6.02,6.02]:s+=pad('SH',x,-4.71,3.4,3.4,2.4)
s+=rect(-6,-14.5,6,2,'F.Fab',.1)+rect(-7.9,-14.8,7.9,2.4)
s+=rect(-6.2,-14.6,6.2,-7,'F.Fab',.12)
save(n,s)
# Grove RA: use 1.0mm holes accommodating .5mm square terminals; body opens -Y.
n='Grove_110990037_RA';s=start(n,'Seeed110990037/1125R4P;2mm pitch;1=yellowSCL right when looking into connector,latchup;opens-Y;verify cable color before power')
for num,x in [(1,-3),(2,-1),(3,1),(4,3)]:s+=pad(str(num),x,0,1.5,1.5,1.0)
s+=rect(-5,-6.5,5,1.5,'F.Fab',.1)+rect(-5.4,-6.9,5.4,1.9)+rect(-5,-6.5,5,-1,'F.SilkS',.12)
s+='(fp_text user "1 YEL" (at -4 3 0) (layer "F.Fab") (effects (font (size .8 .8) (thickness .12))))\n';save(n,s)
# Two matable THT profiles. Underside male pad numbering mirrored BEFORE native flip.
for n,flip in [('G40_Female_Top',False),('G40_Male_Underside',True)]:
 s=start(n,'G40 standard2.54mm;pin6 blocked/removed;source underside numbers mirrorX before mounting,check all40 assembly coordinates')
 for row in range(20):
  for col in range(2):s+=pad(str(2*row+col+1),(-1 if flip else 1)*2.54*col,2.54*row,1.7,1.7,1.0)
 a,c=(-4.1,1.6) if flip else (-1.6,4.1)
 s+=rect(a,-1.6,c,49.86,'F.Fab',.1)+rect(a-.25,-1.85,c+.25,50.11)
 s+='(fp_text user "KEY6" (at '+('-5.5' if flip else '5.5')+' 5.08 90) (layer "F.SilkS") (effects (font (size .8 .8) (thickness .12))))\n'
 save(n,s)
print('Created original MCU/USB/Grove/G40 lands')
