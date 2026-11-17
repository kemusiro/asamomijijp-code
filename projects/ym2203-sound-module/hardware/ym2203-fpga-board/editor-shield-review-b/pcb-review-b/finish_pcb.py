# SPDX-License-Identifier: MIT
"""Import local route candidate, add thermal ground planes, retain all DRC checks."""
from pathlib import Path
import sys,pcbnew as P
H=Path(__file__).resolve().parent;b=P.LoadBoard(str(H/'placed.kicad_pcb'))
assert P.ImportSpecctraSES(b,sys.argv[1])
for t in b.GetTracks():
 if isinstance(t,P.PCB_VIA):t.SetViaType(P.VIATYPE_THROUGH);t.SetLayerPair(P.F_Cu,P.B_Cu)
for z in list(b.Zones()):b.Remove(z)
for layer in [P.F_Cu,P.B_Cu]:
 z=P.ZONE(b);z.SetLayer(layer);z.SetNetCode(b.FindNet('GND').GetNetCode());z.SetLocalClearance(P.FromMM(.25));z.SetMinThickness(P.FromMM(.2));z.SetPadConnection(P.ZONE_CONNECTION_THT_THERMAL);z.SetThermalReliefGap(P.FromMM(.25));z.SetThermalReliefSpokeWidth(P.FromMM(.3));z.SetIslandRemovalMode(P.ISLAND_REMOVAL_MODE_ALWAYS)
 poly=z.Outline();poly.NewOutline()
 for x,y in [(7.5,7.5),(82.5,7.5),(82.5,106.5),(7.5,106.5)]:poly.Append(P.FromMM(x),P.FromMM(y))
 b.Add(z)
P.ZONE_FILLER(b).Fill(b.Zones());P.SaveBoard(str(H/'p2-editor-b.kicad_pcb'),b)
print('Copper tracks and vias',len(list(b.GetTracks())))
