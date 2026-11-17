#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Export local router continuation, preserving placements and existing wide power trunks.
Only missing connections use0.18mm defaults; final native power pours carry supply current.
"""
import pcbnew as P
from pathlib import Path
O=Path(__file__).resolve().parent/'schematic'
b=P.LoadBoard(str(O/'p2-b-unrouted.kicad_pcb'))
assert P.ImportSpecctraSES(b,str(O/'p2-b.ses'))
for z in list(b.Zones()):b.Remove(z)
for t in b.GetTracks():
 if isinstance(t,P.PCB_VIA):t.SetViaType(P.VIATYPE_THROUGH);t.SetLayerPair(P.F_Cu,P.B_Cu);t.SetDrill(P.FromMM(.3))
assert P.ExportSpecctraDSN(b,str(O/'p2-resume.dsn'))
p=O/'p2-resume.dsn';p.write_text(p.read_text().replace(str(p),'p2-resume.dsn',1))
