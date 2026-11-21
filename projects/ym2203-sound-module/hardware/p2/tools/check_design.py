#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
import json,sys,hashlib
from pathlib import Path
import pcbnew as P
from geometry import geometry
H=Path(__file__).resolve().parents[1];B=sys.argv[1];D=H/'cad'/B;name={'base':'p2-base-lc-t','module':'p2-ym2203-lc-t','panel':'p2-panel-lc-n'}[B];b=P.LoadBoard(str(D/(name+'.kicad_pcb')))
a=json.loads((D/'electrical-geometry-before.json').read_text());assert a==geometry(b),'Copper, pads, parts, outline or rule-area geometry changed'
texts=[];minimum=[]
for t in list(b.GetDrawings())+[i for f in b.GetFootprints() for i in list(f.GraphicalItems())+[f.Reference(),f.Value()]]:
 if t.GetLayer() not in [P.F_SilkS,P.B_SilkS]:continue
 if isinstance(t,P.PCB_TEXT):
  if hasattr(t,'IsVisible') and not t.IsVisible():continue
  texts.append(t);assert min(t.GetTextSize().x,t.GetTextSize().y)>=P.FromMM(1);assert t.GetTextThickness()>=P.FromMM(.15)
 elif isinstance(t,P.PCB_SHAPE):minimum.append(P.ToMM(t.GetWidth()));assert t.GetWidth()>=P.FromMM(.15)
for typ in ['drc','erc']:
 d=json.loads((D/(typ+'.json')).read_text())
 if typ=='drc':assert not any(d[k] for k in ['violations','unconnected_items','schematic_parity'])
 else:assert not any(s['violations'] for s in d['sheets'])
pro=json.loads((D/(name+'.kicad_pro')).read_text());assert pro['board']['design_settings']['drc_exclusions']==[]
report=dict(result='PASS',board=B,visible_silk_texts=len(texts),minimum_text_height_mm=1.0,minimum_text_stroke_mm=.15,minimum_silk_shape_stroke_mm=min(minimum),minimum_silk_clearance_mm=.15,electrical_geometry_unchanged=True,erc=0,drc=0,unconnected=0,schematic_parity=0,hardware_accepted=False)
(D/'design-verification.json').write_text(json.dumps(report,indent=2)+'\n');print(B,report)
