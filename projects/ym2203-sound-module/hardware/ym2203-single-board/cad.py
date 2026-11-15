"""Original, reproducible schematics and PCB input for the socketed sound platform.

No third-party symbol or footprint artwork is embedded. Manufacturer documents
are referenced in README.md. This program does not claim hardware verification.
"""
from pathlib import Path
from collections import defaultdict, Counter
import csv
import json
import math
import subprocess
import uuid
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "rev-c"
OUT.mkdir(exist_ok=True)
Q = lambda v: json.dumps(str(v), ensure_ascii=False)
UID = lambda v: str(uuid.uuid5(uuid.NAMESPACE_URL, "weblab-ym2203-single-rev-c:" + v))
GND, V3, V5 = "GND", "+3V3", "+5V"
BOARDS = {}

class Board:
    def __init__(self, name, size, title):
        self.name, self.size, self.title = name, size, title
        self.parts = []
        self.counters = Counter()
        self.dir = OUT / name
        self.dir.mkdir(exist_ok=True)
        BOARDS[name] = self

    def part(self, ref, value, pins, footprint, xy, group, source="", **extra):
        # pins: physical pin -> (name, net, electrical type)
        p = dict(ref=ref, value=value,
                 pins=[dict(num=str(n), name=t[0], net=t[1], type=t[2]) for n,t in pins.items()],
                 footprint=footprint, xy=list(xy), group=group, source=source, **extra)
        assert ref not in {a['ref'] for a in self.parts}
        self.parts.append(p)
        return p

    def passive(self, prefix, value, a, b, xy, group, **extra):
        self.counters[prefix] += 1
        ref = prefix + str(self.counters[prefix])
        fp = dict(kind="smd2",pitch=3.2,body=[3.2,1.6])
        if prefix=='F':fp=dict(kind='axial',pitch=7.62,body=[6,3])
        if prefix=='C' and ('BP' in value or extra.get('polar')):
            fp=dict(kind='radial',pitch=2,body=[5,5])
        return self.part(ref,value,{1:('1',a,'passive'),2:('2',b,'passive')},fp,xy,group,**extra)

    def r(self, value,a,b,xy,g,**kw): return self.passive('R',value,a,b,xy,g,**kw)
    def c(self, value,a,b,xy,g,**kw): return self.passive('C',value,a,b,xy,g,**kw)
    def rn(self,ref,n,value,common,signals,xy,g):
        assert len(signals)==n
        pins={1:('COM',common,'passive')}
        pins.update({i+2:(f'R{i+1}',s,'passive') for i,s in enumerate(signals)})
        code={'10k':'103J','4.7k':'472J','1k':'102J'}[value]
        return self.part(ref,f'RKC{n}BD'+code,pins,
                         dict(kind='sip',n=n+1,pitch=2.54),xy,g,
                         source='https://akizukidenshi.com/catalog/g/g113722/' if value=='1k' else 'https://akizukidenshi.com/catalog/g/g111910/' if n==8 else 'https://akizukidenshi.com/catalog/g/g111909/')

    def ic(self,ref,value,pinmap,n,width,xy,g,source='',**kw):
        assert set(pinmap)==set(range(1,n+1)),(ref,set(range(1,n+1))-set(pinmap))
        return self.part(ref,value,pinmap,dict(kind='dip',n=n,width=width),xy,g,source,**kw)

    def tp(self,ref,net,xy,g='test'):
        return self.part(ref,net,{1:(net,net,'passive')},dict(kind='tp'),xy,g)

    def header(self,ref,value,nets,xy,g='io',rows=1,**kw):
        return self.part(ref,value,{i+1:(n or 'NC',n,'passive') for i,n in enumerate(nets)},
                         dict(kind='header',n=len(nets),rows=rows,pitch=2.54),xy,g,**kw)

    def decouple(self,net,xy,g='decoupling',near=None):
        return self.c('100n',net,GND,xy,g,role='Place immediately beside supply pin',near=near)


def powerpins(mapping,n,vcc,gnd):
    p={i:(f'NC{i}',None,'passive') for i in range(1,n+1)}
    p.update(mapping)
    p[vcc]=('VCC',V3,'power_in');p[gnd]=('GND',GND,'power_in')
    return p


def lcx(b,ref,signals,outs,xy,g,oe=GND):
    p={1:('DIR A>B',V3,'input'),10:('GND',GND,'power_in'),19:('OE_N',oe,'input'),20:('VCC',V3,'power_in')}
    for i in range(8):
        p[2+i]=(f'A{i+1}',signals[i] if i<len(signals) else GND,'input')
        p[18-i]=(f'B{i+1}',outs[i] if i<len(outs) else None,'output')
    return b.part(ref,'74LCX245FT / 3.3V',p,dict(kind='tssop',n=20,pitch=.65,width=6.4),xy,g,
                  source='https://akizukidenshi.com/goodsaffix/74LCX245FT_datasheet_ja_20150130.pdf')


def upmodule(b,ref,ins,outs,xy,oe=GND):
    p={1:('VA',V3,'power_in'),24:('VA',V3,'power_in'),23:('VB',V5,'power_in'),
       2:('OE_N',oe,'input'),3:('DIR A>B',V3,'input'),12:('GND',GND,'power_in'),
       13:('GND',GND,'power_in'),22:('GND',GND,'power_in')}
    for i in range(8):
        p[4+i]=(f'A{i+1}',ins[i] if i<len(ins) else GND,'input')
        p[21-i]=(f'B{i+1}',outs[i] if i<len(outs) else None,'tri_state')
    return b.ic(ref,'AE-LLCNV-LVC8T245',p,24,15.24,xy,'bus',
         'https://akizukidenshi.com/catalog/g/g115778/',body_extra=[18,31])


def symbol(p,x,y,boardname):
    """Single-unit, all physical pins, connected labels; no implicit power pins."""
    x=round(round(x/1.27)*1.27,5);y=round(round(y/1.27)*1.27,5)
    ref=p['ref']; pins=p['pins']; count=len(pins)
    kind=p['footprint']['kind']
    passive=count==2 and kind in ('cap','axial','sma','smd2','smd2v','radial')
    hx=25.4 if not passive else 2.54
    cols=[pins[:math.ceil(count/2)], pins[math.ceil(count/2):]]
    if passive: cols=[[pins[0]],[pins[1]]]
    hy=max(5.08,(max(map(len,cols))+1)*2.54/2)
    g=f'(rectangle (start {-hx} {hy}) (end {hx} {-hy}) (stroke (width .25) (type default)) (fill (type background)))'
    def poly(points):
        return '(polyline (pts '+''.join(f'(xy {a} {b})' for a,b in points)+') (stroke (width .25) (type default)) (fill (type none)))'
    if passive and ref.startswith('C'):
        g=poly([(-2.54,0),(-.762,0)])+poly([(.762,0),(2.54,0)])
        g+=poly([(-.762,-2.54),(-.762,2.54)])+poly([(.762,-2.54),(.762,2.54)])
        if p.get('polar'):g+='(text "+" (at -2.54 3.81 0) (effects (font (size 1.27 1.27))))'
    elif passive and ref.startswith('R'):
        g='(rectangle (start -2.54 1.016) (end 2.54 -1.016) (stroke (width .25) (type default)) (fill (type none)))'
    elif passive and ref.startswith('D'):
        g=poly([(-2.54,0),(-1.27,0)])+poly([(-1.27,-2.54),(-1.27,2.54)])
        g+=poly([(-1.27,0),(2.54,2.54),(2.54,-2.54),(-1.27,0)])
    ps=[]; it=[]; fx='(effects (font (size 1.27 1.27)))'
    for side,pp in enumerate(cols):
        for i,pin in enumerate(pp):
            px=(-1 if side==0 else 1)*(hx+5.08)
            py=0 if passive else hy-3.81-i*2.54
            a=0 if side==0 else 180
            ps.append(f'(pin {pin["type"]} line (at {px} {py} {a}) (length 5.08) (name {Q(pin["name"])} {fx}) (number {Q(pin["num"])} {fx}))')
            gx,gy=round(x+px,5),round(y-py,5)
            tag=f'{boardname}:{ref}:{pin["num"]}'
            if pin['net'] is None:
                it.append(f'(no_connect (at {gx} {gy}) (uuid {UID(tag+"NC")}))')
            else:
                xx=round(gx+(-7.62 if side==0 else 7.62),5)
                it.append(f'(wire (pts (xy {gx} {gy}) (xy {xx} {gy})) (stroke (width 0) (type default)) (uuid {UID(tag+"W")}))')
                just='right bottom' if side==0 else 'left bottom'
                it.append(f'(label {Q(pin["net"])} (at {xx} {gy} {a}) (effects (font (size 1.27 1.27)) (justify {just})) (uuid {UID(tag+"L")}))')
    key='SOUNDPCB:'+ref; root=UID(boardname)
    lib=f'(symbol {Q(key)} (pin_names (offset .6)) (in_bom yes) (on_board yes) (property "Reference" "U" (at 0 0 0) {fx}) (property "Value" {Q(p["value"])} (at 0 0 0) {fx}) (symbol {Q(ref+"_1_1")} {g} '+''.join(ps)+'))'
    sid=UID(boardname+':'+ref)
    fpname='SOUNDPCB:'+ref
    physical=not ref.startswith('#')
    it.append(f'(symbol (lib_id {Q(key)}) (at {x} {y} 0) (unit 1) (in_bom {"yes" if physical else "no"}) (on_board {"yes" if physical else "no"}) (dnp no) (uuid {sid})'
              f'(property "Reference" {Q(ref)} (at {x} {y-hy-3.81} 0) {fx})'
              f'(property "Value" {Q(p["value"])} (at {x} {y+hy+3.81} 0) {fx})'
              f'(property "Footprint" {Q(fpname if physical else "")} (at {x} {y} 0) (effects (font (size 1 1)) hide))'
              f'(instances (project {Q(boardname)} (path "/{root}" (reference {Q(ref)}) (unit 1)))))')
    return lib,it,hy


def export_schematic(b):
    # Six panels on A0: each group flows in a separate column, pin labels never overlap.
    groups=[['controller','io'],['ym','clock'],['bus','fm'],['safety','power'],['dac'],['analog','pulls','decoupling','test']]
    libs=[];items=[]
    def note(t,x,y,size=2):
        items.append(f'(text {Q(t)} (at {x} {y} 0) (effects (font (size {size} {size})) (justify left)) (uuid {UID(b.name+t)}))')
    note(b.title,20,20,4)
    note('Rev C / GPIO approved 2026-10-18 / Prototype - hardware untested / See README before manufacture',20,30)
    note('Labels of the same name are connected. Pin numbers are physical pins. Mono mix duplicated to L/R line output for AMS-22. USB-MIDI requires firmware.',20,38)
    ys=[70]*len(groups)
    for col,gg in enumerate(groups):
        pp=[p for p in b.parts if p['group'] in gg]
        x=94+col*194
        note(' / '.join(gg).upper(),x-70,52,2.5)
        for p in pp:
            h=max(5.08,(math.ceil(len(p['pins'])/2)+1)*2.54/2)
            target=col if ys[col]+2*h+19.05<790 else min(range(len(groups)),key=lambda k:ys[k])
            if ys[target]+2*h+19.05>790:raise ValueError((b.name,col,p['ref'],ys))
            lib,it,_=symbol(p,94+target*194,round(ys[target]+h,5),b.name)
            libs.append(lib);items+=it;ys[target]+=2*h+19.05
    # Rail flags are explicit and excluded from the physical BOM.
    for i,n in enumerate([GND,'USB_VBUS','USB_FUSED','VSYS']):
        flag=dict(ref=f'#FLG{i}',value='POWER FLAG',pins=[dict(num='1',name=n,net=n,type='power_out')],footprint=dict(kind='flag'))
        l,it,h=symbol(flag,700+i*100,817,b.name);libs.append(l);items+=it
    sch=b.dir/(b.name+'.kicad_sch')
    sch.write_text(f'(kicad_sch (version 20250114) (generator "eeschema") (uuid {UID(b.name)}) (paper "A0") (lib_symbols '+''.join(libs)+')\n'+'\n'.join(items)+'\n(embedded_fonts no))\n')
    pro=dict(board=dict(design_settings=dict(rules=dict(min_clearance=.2,min_track_width=.18,
         min_via_diameter=.7,min_via_drill=.3,min_hole_clearance=.25,min_copper_edge_clearance=.5))),
         net_settings=dict(classes=[dict(name='Default',clearance=.2,track_width=.25,via_diameter=.7,via_drill=.3,
         diff_pair_width=.25,diff_pair_gap=.25,diff_pair_via_gap=.25,wire_width=6,bus_width=12,pcb_color='rgba(0, 0, 0, 0)',schematic_color='rgba(0, 0, 0, 0)')]))
    (b.dir/(b.name+'.kicad_pro')).write_text(json.dumps(pro,indent=2)+'\n')
    libtext=''.join(l.replace('(symbol "SOUNDPCB:','(symbol "',1) for l in libs)
    (b.dir/'SOUNDPCB.kicad_sym').write_text('(kicad_symbol_lib (version 20241209) (generator "kicad_symbol_editor") '+libtext+')\n')
    (b.dir/'sym-lib-table').write_text('(sym_lib_table (version 7) (lib (name "SOUNDPCB") (type "KiCad") (uri "${KIPRJMOD}/SOUNDPCB.kicad_sym") (options "") (descr "Original prototype symbols")))\n')
    for args in [
        ['netlist','--format','kicadxml','-o',str(b.dir/'netlist.xml')],
        ['erc','--format','json','-o',str(b.dir/'erc.json')],
        ['svg','--no-background-color','--exclude-drawing-sheet','--default-font','Arial Unicode MS','-o',str(b.dir)],
        ['pdf','--no-background-color','--exclude-drawing-sheet','--default-font','Arial Unicode MS','-o',str(b.dir/(b.name+'-schematic.pdf'))],
    ]:
        cmd=['kicad-cli','sch',args[0]] if args[0]=='erc' else ['kicad-cli','sch','export',args[0]]
        r=subprocess.run(cmd+args[1:]+[str(sch)],capture_output=True,text=True)
        if r.returncode:raise RuntimeError(r.stdout+r.stderr)
    # Compare complete physical pin sets, not just net counts.
    expected=defaultdict(set)
    for p in b.parts:
        for pin in p['pins']:
            if pin['net'] is not None:expected[pin['net']].add((p['ref'],pin['num']))
    actual={n.attrib['name'].lstrip('/'):{(p.attrib['ref'],p.attrib['pin']) for p in n.findall('node') if not p.attrib['ref'].startswith('#')}
            for n in ET.parse(b.dir/'netlist.xml').findall('./nets/net')}
    actual={n:v for n,v in actual.items() if v and not n.startswith('unconnected-')}
    assert dict(expected)==actual,(b.name,{n:expected[n]^actual.get(n,set()) for n in expected if expected[n]!=actual.get(n)})
    b.nets=len(expected)

