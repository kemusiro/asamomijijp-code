#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Create a plot-only native copy with compact assembly indices. Never overwrite PCB sources."""
from pathlib import Path
import sys,json
import pcbnew as P
from sexp import loads,dumps
HERE=Path(__file__).resolve().parent;side=sys.argv[1];target=Path(sys.argv[2]);name='p2-base-d' if side=='base' else 'p2-ym2203-d';source=HERE/side/(name+'.kicad_pcb');d=loads(source.read_text())
for fp in d:
 if isinstance(fp,list) and fp and fp[0]=='footprint':fp[:]=[v for v in fp if not(isinstance(v,list) and v and v[0]=='fp_text')]
d[:]=[v for v in d if not(isinstance(v,list) and v and v[0]=='gr_text' and any(['layer',l] in v for l in ['"Dwgs.User"','"F.Fab"']))]
target.write_text(dumps(d)+'\n');b=P.LoadBoard(str(target));fps={f.GetReference():f for f in b.GetFootprints()};parts=sorted(json.loads((HERE/side/'circuit.json').read_text())['parts'],key=lambda p:p['ref'])
for i,q in enumerate(parts,1):
 f=fps[q['ref']];pads=list(f.Pads());x=sum(p.GetPosition().x for p in pads)//len(pads);y=sum(p.GetPosition().y for p in pads)//len(pads)
 # UNO and logical Core groups use contact centroid; all other part centers are pad centroids.
 t=P.PCB_TEXT(b);t.SetText(str(i));t.SetPosition(P.VECTOR2I(x,y));t.SetLayer(P.F_Fab);t.SetTextSize(P.VECTOR2I(P.FromMM(.55),P.FromMM(.55)));t.SetTextThickness(P.FromMM(.09));b.Add(t)
P.SaveBoard(str(target),b)
