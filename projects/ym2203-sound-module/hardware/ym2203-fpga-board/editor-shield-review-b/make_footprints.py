#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original dimensional transcriptions; encoder ABC/sample fit remains provisional."""
from pathlib import Path
P=Path(__file__).resolve().parent/'ED2.pretty'
def start(name,desc,attr='through_hole'):
 return [f'(footprint "{name}" (version 20250114) (generator "pcbnew") (layer "F.Cu") (attr {attr}) (descr "{desc}")',f'(property "Reference" "REF**" (at 0 -11 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))',f'(property "Value" "{name}" (at 0 11 0) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))']
def rect(a,x,y,w,h,layer):a.append(f'(fp_rect (start {x} {y}) (end {x+w} {y+h}) (stroke (width .12) (type default)) (fill none) (layer "{layer}"))')
for name,pitch,w,h in [('C_RDE_100n_P2_5',2.5,5,2.5),('C_RDE_10n_P5',5,4,2.5)]:
 a=start(name,'RDE body/pitch from Akizuki specification; nominal drilling candidate');rect(a,pitch/2-w/2,-h/2,w,h,'F.Fab');rect(a,pitch/2-w/2-.5,-h/2-.5,w+1,h+1,'F.CrtYd')
 for n,x in [(1,0),(2,pitch)]:a.append(f'(pad "{n}" thru_hole circle (at {x} 0) (size 1.8 1.8) (drill .8) (layers "*.Cu" "*.Mask"))')
 a.append(')');(P/(name+'.kicad_mod')).write_text('\n'.join(a)+'\n')
name='RE111F_4S1_ReviewB';a=start(name,'RE111F drawing SLH215: original pad transcription; ABC/locator/sample-fit not accepted','smd')
rect(a,-6.9,-5.85,13.8,11.7,'F.Fab');rect(a,-9.8,-8.55,19.6,17.1,'F.CrtYd')
for n,x,y,w,h in [('A',-8.12,-2.5,2.3,1.7),('C',-8.12,0,2.3,1.7),('B',-8.12,2.5,2.3,1.7),('S1',8.255,-2.5,2.05,1.7),('S2',8.255,2.5,2.05,1.7),('MP',0,-6.85,7.4,2.4),('MP',0,6.85,7.4,2.4)]:a.append(f'(pad "{n}" smd rect (at {x} {y}) (size {w} {h}) (layers "F.Cu" "F.Paste" "F.Mask"))')
for x,d in [(-4.5,1.6),(0,2.1)]:a.append(f'(pad "" np_thru_hole circle (at {x} 0) (size {d} {d}) (drill {d}) (layers "*.Cu" "*.Mask"))')
a.append(')');(P/(name+'.kicad_mod')).write_text('\n'.join(a)+'\n')
