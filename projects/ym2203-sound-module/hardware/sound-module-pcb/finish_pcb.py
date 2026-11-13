"""Import a local Specctra session, fill ground planes, and emit QA geometry.

Run using KiCad's Python: finish_pcb.py base path/to/base.ses
This command modifies the generated PCB in place and preserves the DSN input.
"""
from pathlib import Path
import json, sys, os, re, csv, xml.etree.ElementTree as ET
import pcbnew as p

ROOT=Path(__file__).resolve().parent
name=sys.argv[1];session=Path(sys.argv[2]).resolve();folder=ROOT/'rev-a'/name
target=folder/(name+'.kicad_pcb')
# Remove obsolete prototype pin-1 bars before loading (reference fields remain).
raw=target.read_text();blocks=[]
for m in re.finditer(r'\(fp_line\b',raw):
    depth=0;quoted=False;escaped=False;end=None
    for i in range(m.start(),len(raw)):
        ch=raw[i]
        if escaped:escaped=False;continue
        if ch=='\\' and quoted:escaped=True;continue
        if ch=='"':quoted=not quoted
        if not quoted:
            if ch=='(':depth+=1
            elif ch==')':
                depth-=1
                if depth==0:end=i+1;break
    chunk=raw[m.start():end]
    if '(layer "F.SilkS")' in chunk or '(layer "B.SilkS")' in chunk:blocks.append((m.start(),end))
for a,b in reversed(blocks):raw=raw[:a]+raw[b:]
target.write_text(raw)
board=p.LoadBoard(str(target))
assert p.ImportSpecctraSES(board,str(session)), 'SES import failed'
design=json.loads((ROOT/'rev-a/design.json').read_text())['boards'][name]
w,h=design['size_mm']
for t in board.GetTracks():
    if not isinstance(t,p.PCB_VIA) and t.GetWidth()<p.FromMM(.18):t.SetWidth(p.FromMM(.18))
for item in board.GetDrawings():
    if isinstance(item,p.PCB_TEXT) and item.GetText()=='1  +5V':
        item.SetPosition(p.VECTOR2I(p.FromMM(w-12),p.FromMM(10.5)))
if name=='base':
    for fp in board.GetFootprints():
        if fp.GetReference()=='JMOD':fp.Reference().SetPosition(p.VECTOR2I(p.FromMM(160),p.FromMM(12)))
gnd=board.FindNet('/GND')
assert gnd is not None
# Preserve KiCad's individual no-connect net identities for schematic parity.
fps={f.GetReference():f for f in board.GetFootprints()}
for net in ET.parse(folder/'netlist.xml').findall('./nets/net'):
    n=net.attrib['name']
    if not n.startswith('unconnected-'):continue
    ni=p.NETINFO_ITEM(board,n);board.Add(ni)
    for node in net.findall('node'):
        fp=fps[node.attrib['ref']]
        for pad in fp.Pads():
            if pad.GetNumber()==node.attrib['pin']:pad.SetNet(ni)
# The reference field and rectangular pin-1 pad are retained; remove pin-1
# bars that can collide with relocated reference text in a dense placement.
for z in list(board.Zones()):board.Remove(z)
for layer in [p.F_Cu,p.B_Cu]:
    z=p.ZONE(board);z.SetLayer(layer);z.SetNet(gnd)
    z.SetLocalClearance(p.FromMM(.3));z.SetThermalReliefGap(p.FromMM(.3));z.SetThermalReliefSpokeWidth(p.FromMM(.3))
    z.SetPadConnection(p.ZONE_CONNECTION_FULL);z.SetMinThickness(p.FromMM(.25))
    poly=z.Outline();poly.NewOutline()
    for x,y in [(1,1),(w-1,1),(w-1,h-1),(1,h-1)]:poly.Append(p.FromMM(x),p.FromMM(y))
    board.Add(z)
board.BuildConnectivity();filler=p.ZONE_FILLER(board);filler.Fill(board.Zones())
p.SaveBoard(str(target),board)
# Store the actual original footprint geometry as its project-local library.
# Saving an underside footprint with a board parent lets KiCad normalize its flip.
plugin=p.PCB_IO_KICAD_SEXPR()
for fp in board.GetFootprints():plugin.FootprintSave(str(folder/'SOUNDPCB.pretty'),fp)

geom=dict(board=name,size_mm=[w,h],tracks=[],vias=[],pads=[],footprints=[])
for t in board.GetTracks():
    if isinstance(t,p.PCB_VIA):
        v=t.GetPosition();geom['vias'].append(dict(x=p.ToMM(v.x),y=p.ToMM(v.y),size=p.ToMM(t.GetWidth(p.F_Cu)),net=t.GetNetname()))
    else:
        a,b=t.GetStart(),t.GetEnd()
        geom['tracks'].append(dict(a=[p.ToMM(a.x),p.ToMM(a.y)],b=[p.ToMM(b.x),p.ToMM(b.y)],
                                   width=p.ToMM(t.GetWidth()),layer='top' if t.GetLayer()==p.F_Cu else 'bottom',net=t.GetNetname()))
for fp in board.GetFootprints():
    pos=fp.GetPosition();text=fp.Reference().GetPosition()
    geom['footprints'].append(dict(ref=fp.GetReference(),value=fp.GetValue(),x=p.ToMM(pos.x),y=p.ToMM(pos.y),
                                  text=[p.ToMM(text.x),p.ToMM(text.y)],side='bottom' if fp.GetLayer()==p.B_Cu else 'top'))
    for pad in fp.Pads():
        pos,size=pad.GetPosition(),pad.GetSize()
        geom['pads'].append(dict(ref=fp.GetReference(),num=pad.GetNumber(),net=pad.GetNetname(),
                                x=p.ToMM(pos.x),y=p.ToMM(pos.y),sx=p.ToMM(size.x),sy=p.ToMM(size.y),
                                drill=p.ToMM(pad.GetDrillSize().x),rect=pad.GetShape()==p.PAD_SHAPE_RECT))
(folder/'geometry.json').write_text(json.dumps(geom,indent=2)+'\n')
with (folder/'bom.csv').open(encoding='utf-8-sig',newline='') as f:rows=list(csv.DictReader(f))
positions={fp['ref']:fp for fp in geom['footprints']}
for row in rows:
    row['x_mm']=positions[row['reference']]['x'];row['y_mm']=positions[row['reference']]['y']
with (folder/'bom.csv').open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
print(name,'SES imported;',len(geom['tracks']),'track segments;',len(geom['vias']),'vias',flush=True)
sys.stdout.flush();sys.stderr.flush();os._exit(0)
