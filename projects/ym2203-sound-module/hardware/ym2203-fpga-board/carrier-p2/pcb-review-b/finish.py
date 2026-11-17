# SPDX-License-Identifier: MIT
"""Import reviewed routes and add solid inner GND plane; preserve schematic identity."""
from pathlib import Path
import json,re,xml.etree.ElementTree as E
import pcbnew as P
HERE=Path(__file__).resolve().parent;O=HERE/'schematic'
V=lambda x,y:P.VECTOR2I(P.FromMM(x),P.FromMM(y))
b=P.LoadBoard(str(O/'p2-b-unrouted.kicad_pcb'))
ses=O/'p2-b.ses';ses.write_text('\n'.join(line.rstrip() for line in ses.read_text().splitlines())+'\n')
assert P.ImportSpecctraSES(b,str(ses))
# Router's abstract 3-layer model must use ordinary plated through vias on physical4layers.
for track in b.GetTracks():
 if isinstance(track,P.PCB_VIA):
  track.SetViaType(P.VIATYPE_THROUGH);track.SetLayerPair(P.F_Cu,P.B_Cu);track.SetDrill(P.FromMM(.3))
# Bind complete schematic instance paths for independent native parity verification.
roottext=(O/'p2-carrier-b.kicad_sch').read_text();root=re.search(r'\(uuid ([0-9a-f-]+)\)',roottext).group(1)
comp={p.get('ref'):p for p in E.parse(O/'netlist.xml').findall('.//components/comp')}
for f in b.GetFootprints():
 if f.GetReference() in comp:
  c=comp[f.GetReference()];path=P.KIID_PATH()
  f.SetFPID(P.LIB_ID(*c.findtext('footprint').split(':')))
  f.SetAttributes(f.GetAttributes() & ~P.FP_EXCLUDE_FROM_BOM)
  uu=[root]+c.find('sheetpath').get('tstamps').strip('/').split('/')+[c.findtext('tstamps')]
  for u in uu:path.push_back(P.KIID(u))
  f.SetPath(path)
 else:
  # Mounting holes have no schematic electrical function.
  f.SetAttributes(f.GetAttributes()|P.FP_EXCLUDE_FROM_BOM|P.FP_EXCLUDE_FROM_POS_FILES|P.FP_BOARD_ONLY)
 if f.GetReference()=='MPGA':
  for pad in f.Pads():pad.SetDrillSize(V(1.2,1.2))
 # H3: bare UNO compatibility hole, intentionally no screw/standoff (header end interference).
 if f.GetReference()=='H3':
  for it in list(f.GraphicalItems()):
   if it.GetLayer()==P.F_CrtYd:f.Remove(it)
  ring=P.PCB_SHAPE(f);ring.SetShape(P.SHAPE_T_CIRCLE);ring.SetCenter(f.GetPosition());ring.SetEnd(f.GetPosition()+V(1.75,0));ring.SetWidth(P.FromMM(.05));ring.SetLayer(P.F_CrtYd);f.Add(ring)
 # Keep reference labels for corner mounts inside board edges.
 if f.GetReference() in ['H5','H6']:f.Reference().SetPosition(f.GetPosition()+V(0,3.5))
# KiCad parity includes isolated NC nets. Preserve those single-pad identities too.
netxml=E.parse(O/'netlist.xml')
for net in netxml.findall('.//nets/net'):
 name=net.get('name')
 if not name.startswith('unconnected-'):continue
 n=P.NETINFO_ITEM(b,name);b.Add(n)
 for node in net.findall('node'):
  for fp in b.GetFootprints():
   if fp.GetReference()==node.get('ref'):
    for pad in fp.Pads():
     if pad.GetNumber()==node.get('pin'):pad.SetNet(n)
# Explicit silkscreen placements after native collision review.
for f in b.GetFootprints():
 loc={'UVBUS':(123,23),'R38':(123,36),'R21':(94,62),'C24':(147,48),'JUNO_SPI':(72,41.5)}.get(f.GetReference())
 if loc:f.Reference().SetPosition(V(*loc))
# Retain an uninterrupted In1.Cu reference plane. Routing there is forbidden by DSN.
assert not any(t.GetLayer()==P.In1_Cu for t in b.GetTracks() if not isinstance(t,P.PCB_VIA))
for oldzone in list(b.Zones()):b.Remove(oldzone)
gnd=b.FindNet('GND')
z=P.ZONE(b);z.SetLayer(P.In1_Cu);z.SetNetCode(gnd.GetNetCode());z.SetLocalClearance(P.FromMM(.2));z.SetThermalReliefGap(P.FromMM(.25));z.SetThermalReliefSpokeWidth(P.FromMM(.3));z.SetMinThickness(P.FromMM(.15));z.SetPadConnection(P.ZONE_CONNECTION_THT_THERMAL)
p=z.Outline();p.NewOutline()
for x,y in [(0.5,.5),(163.5,.5),(163.5,123.5),(.5,123.5)]:p.Append(int(P.FromMM(x)),int(P.FromMM(y)))
b.Add(z);P.ZONE_FILLER(b).Fill(b.Zones())
from local_routes import apply as local_apply
local_apply(b)
from local_layout import apply as layout_apply,record
ground_fanouts=layout_apply(b)
from power_routes import apply
fanouts=apply(b,ground_fanouts)
(O/'power-fanouts.json').write_text(json.dumps(fanouts,indent=2)+'\n')
title=P.TITLE_BLOCK();title.SetTitle('P2 revision2.1 / routed PCB review B');title.SetRevision('2.1-B');title.SetDate('2026-11-16');title.SetCompany('YM2203 sound module');title.SetComment(0,'Prototype candidate; fitted sockets, power/USB tests and firmware pending');b.SetTitleBlock(title)
# Matching project name is required for parity, netclasses and DRC configuration.
# Native design rules must match the documented/router geometry, not KiCad defaults.
project=json.loads((HERE/'design-rules.json').read_text())
base=project['net_settings']['classes'][0];power=dict(base);power.update(name='Power',priority=0,track_width=.5)
project['net_settings']['classes']=[base,power]
project['net_settings']['netclass_patterns']=[{'netclass':'Power','pattern':name} for name in ['V5_CARRIER','V3V3','V3_AUX','AV3V3','EXT5_IN','SHIELD_5V']]
(O/'p2-carrier-b.kicad_pro').write_text(json.dumps(project,indent=2)+'\n')
record(b,O)
P.SaveBoard(str(O/'p2-carrier-b.kicad_pcb'),b)
stats=dict(electrical_components=len(comp),footprints=len(list(b.GetFootprints())),segments=sum(not isinstance(t,P.PCB_VIA) for t in b.GetTracks()),vias=sum(isinstance(t,P.PCB_VIA) for t in b.GetTracks()),layers=b.GetCopperLayerCount(),reserved_ground_plane='In1.Cu',native_pin_changes=False,hardware_accepted=False)
(O/'pcb-stats.json').write_text(json.dumps(stats,indent=2)+'\n');print(stats)
