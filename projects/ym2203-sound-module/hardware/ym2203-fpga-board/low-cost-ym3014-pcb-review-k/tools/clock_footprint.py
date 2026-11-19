#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Original landing from Akizuki AE-Si5351A manual p1 TOP VIEW, mm."""
from pathlib import Path
root=Path(__file__).resolve().parents[1];name='AE_Si5351A_B_10x10mm'
s=f'''(footprint "{name}" (version 20241229) (generator pcbnew) (layer "F.Cu")
(descr "Akizuki110679 10x10mm;TOP view;pitch2.54mm,rows7.62mm;3V3 both rails;CL8pF;direct pin headers 2.54mm standoff;manual1:1 fit required")
(attr through_hole)
(property "Reference" "REF**" (at 0 -6.4 0) (layer "F.SilkS") (effects (font (size 1 1) (thickness .15))))
(property "Value" "AE-Si5351A-B" (at 0 6.4 0) (layer "F.Fab") (effects (font (size 1 1) (thickness .15))))
(fp_rect (start -5 -5) (end 5 5) (stroke (width .1) (type default)) (fill none) (layer "F.Fab"))
(fp_rect (start -5.5 -5.5) (end 5.5 5.5) (stroke (width .05) (type default)) (fill none) (layer "F.CrtYd"))
(fp_text user "1" (at -5.7 -3.81 0) (layer "F.Fab") (effects (font (size .9 .9) (thickness .12))))
'''
for n,x,y in [(1,-3.81,-3.81),(2,-3.81,-1.27),(3,-3.81,1.27),(4,-3.81,3.81),(5,3.81,3.81),(6,3.81,1.27),(7,3.81,-1.27),(8,3.81,-3.81)]:
 s+=f'(pad "{n}" thru_hole {"rect" if n==1 else "oval"} (at {x} {y}) (size 1.8 1.8) (drill 1.0) (layers "*.Cu" "*.Mask"))\n'
s+=')\n';(root/'P2LC.pretty'/(name+'.kicad_mod')).write_text(s)
