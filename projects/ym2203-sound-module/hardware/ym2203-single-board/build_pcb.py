"""Run with the KiCad-bundled Python interpreter (pcbnew required).

Creates original footprints, checks placement, writes boards and Specctra input.
Does not download, invoke, or install a routing program.
"""
from pathlib import Path
import json, math, uuid, sys, subprocess, os, re
import pcbnew as pcb

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'rev-c'
DESIGN=json.loads((OUT/'design.json').read_text())
UID=lambda v:str(uuid.uuid5(uuid.NAMESPACE_URL,'weblab-ym2203-single-rev-c:'+v))
V=lambda x,y:pcb.VECTOR2I(pcb.FromMM(x),pcb.FromMM(y))
def layers(*ids):
    s=pcb.LSET()
    for i in ids:s.AddLayer(i)
    return s


def shape(parent,layer,a,b,width=.15):
    s=pcb.PCB_SHAPE(parent);s.SetShape(pcb.SHAPE_T_SEGMENT)
    s.SetStart(V(*a));s.SetEnd(V(*b));s.SetLayer(layer);s.SetWidth(pcb.FromMM(width));parent.Add(s)


def box(parent,layer,bb,width=.15):
    x1,y1,x2,y2=bb
    for a,b in [((x1,y1),(x2,y1)),((x2,y1),(x2,y2)),((x2,y2),(x1,y2)),((x1,y2),(x1,y1))]:shape(parent,layer,a,b,width)


def pad(fp,num,x,y,sx=1.8,sy=1.8,drill=.9,smd=False,npth=False):
    p=pcb.PAD(fp);p.SetNumber(str(num));p.SetPosition(V(x,y));p.SetSize(V(sx,sy))
    p.SetShape(pcb.PAD_SHAPE_RECT if str(num)=='1' and not npth else pcb.PAD_SHAPE_CIRCLE if not smd else pcb.PAD_SHAPE_RECT)
    if npth:
        p.SetAttribute(pcb.PAD_ATTRIB_NPTH);p.SetDrillSize(V(drill,drill));p.SetLayerSet(pcb.LSET.AllCuMask())
    elif smd:
        p.SetAttribute(pcb.PAD_ATTRIB_SMD);p.SetLayerSet(layers(pcb.F_Cu,pcb.F_Paste,pcb.F_Mask))
    else:
        p.SetAttribute(pcb.PAD_ATTRIB_PTH);p.SetDrillSize(V(drill,drill));p.SetLayerSet(pcb.PAD.PTHMask())
    fp.Add(p)
    return p


def footprint(p,boardname):
    fp=pcb.FOOTPRINT(None);fp.SetReference(p['ref']);fp.SetValue(p['value'])
    fp.SetFPID(pcb.LIB_ID('SOUNDPCB',p['ref']))
    fp.SetPath(pcb.KIID_PATH('/'+UID(boardname)+'/'+UID(boardname+':'+p['ref'])))
    f=p['footprint'];k=f['kind'];smd=False
    if k=='dip':
        n=f['n'];w=f['width'];h=(n//2-1)*2.54
        for i in range(n//2):pad(fp,i+1,0,i*2.54);pad(fp,n-i,w,i*2.54)
        extra=p.get('body_extra');body=[-1.3,-2,w+1.3,h+2]
        if extra:body=[(w-extra[0])/2,(h-extra[1])/2,(w+extra[0])/2,(h+extra[1])/2]
    elif k=='tssop':
        n=f['n'];h=(n//2-1)*.65
        for i in range(n//2):
            pad(fp,i+1,-2.925,i*.65,1.45,.4,smd=True)
            pad(fp,n-i,2.925,i*.65,1.45,.4,smd=True)
        body=[-3.75,-.6,3.75,h+.6];smd=True
    elif k=='sip':
        n=f['n']
        for i in range(n):pad(fp,i+1,i*2.54,0,1.7,1.7,.8)
        body=[-1.7,-1.5,(n-1)*2.54+1.7,1.5]
    elif k=='header':
        n=f['n'];rows=f['rows']
        for i in range(n):pad(fp,i+1,(i%rows)*2.54,(i//rows)*2.54,1.9,1.9,1.02)
        body=[-1.5,-1.5,(rows-1)*2.54+1.5,(math.ceil(n/rows)-1)*2.54+1.5]
    elif k=='rk097_dual':
        # Original footprint from the ALPS mounting-side drawing, p.2.
        # Datum is the front body face / shaft centre; shaft points toward +Y.
        # Near row R1, rear row R2; CCW is pin 1 (4), CW is pin 3 (6).
        for row,y in enumerate([-5,-7.5]):
            for col,x in enumerate([-2.5,0,2.5]):pad(fp,row*3+col+1,x,y,1.8,1.8,1.0)
        body=[-4.75,-9.55,4.75,0]
        # Shaft/bushing protrude off-board. Fab geometry shows the full reach;
        # the courtyard below covers the body, not the external panel space.
        box(fp,pcb.F_Fab,[-3,0,3,15],.1)
        shape(fp,pcb.F_Fab,(-3,5),(3,5),.1)
    elif k=='st005g':
        # Original layout from Switronic V2.3, transformed toward +Y.
        # Coordinates measured from mouth; two legs of the TIP share pin 4.
        for x in [-2.9,2.9]:pad(fp,4,x,-3.5,2.0,2.0,1.2)
        pad(fp,2,-2.25,-11,2.0,2.0,1.2)
        pad(fp,3,2.25,-11,2.0,2.0,1.2)
        for x in [-2.5,2.5]:pad(fp,'',x,-7,1.0,1.0,1.0,npth=True)
        body=[-3.25,-14,3.25,0]
    elif k=='usb_c_module':
        # AE-USB2.0-TYPE-C module, top view rotated 180 degrees (mouth +Y).
        # CN2: 1 VBUS, 2 D-, 3 D+, 4 GND, 5 CC1, 6 CC2, 7 GND.
        # Two front support headers use the module's duplicate VBUS/GND holes.
        for i in range(7):pad(fp,i+1,7.62-i*2.54,0,1.9,1.9,1.02)
        for y in [7.62,10.16]:
            pad(fp,1,7.62,y,1.9,1.9,1.02);pad(fp,7,-7.62,y,1.9,1.9,1.02)
        body=[-10,-1.9,10,10.56]
    elif k=='sot23_6':
        # TI DBV top view: 1/2/3 left top-to-bottom, 6/5/4 right.
        for i in range(3):
            pad(fp,i+1,-1.3,(i-1)*.95,1.1,.6,smd=True)
            pad(fp,6-i,1.3,(i-1)*.95,1.1,.6,smd=True)
        body=[-1.9,-1.6,1.9,1.6];smd=True
    elif k=='smd2':
        for i,x in enumerate([0,3.2]):pad(fp,i+1,x,0,1.4,1.8,smd=True)
        body=[-.8,-1.1,4,1.1];smd=True
    elif k=='smd2v':
        for i,y in enumerate([0,3.2]):pad(fp,i+1,0,y,1.8,1.4,smd=True)
        body=[-1.1,-.8,1.1,4];smd=True
    elif k=='sma':
        pad(fp,1,0,0,2.5,1.9,smd=True);pad(fp,2,4.4,0,2.5,1.9,smd=True)
        body=[-1.4,-1.6,5.8,1.6];smd=True
    elif k=='sot23':
        # Top view, MMBT3904 style 6: B1 upper-left, E2 lower-left, C3 right.
        # Swapping the two left pins is a mirror, not a package rotation.
        pad(fp,1,-.95,-.95,1.4,.7,smd=True);pad(fp,2,-.95,.95,1.4,.7,smd=True)
        pad(fp,3,.95,0,1.4,.7,smd=True);body=[-1.8,-1.5,1.8,1.5];smd=True
    elif k in ('axial','cap','radial'):
        pitch=f['pitch'];pad(fp,1,0,0,1.5,1.5,.8);pad(fp,2,pitch,0,1.5,1.5,.8)
        body=[-1.5,-2.5,pitch+1.5,2.5] if k=='radial' else [-1,-1.8,pitch+1,1.8]
    elif k=='dip8osc':
        for n,x,y in [(1,0,0),(4,0,7.62),(5,7.62,7.62),(8,7.62,0)]:pad(fp,n,x,y)
        body=[-2.2,-2.7,9.82,10.32]
    elif k=='tp':
        pad(fp,1,0,0,2,2,1);body=[-1.2,-1.2,1.2,1.2]
    elif k=='hole':
        pad(fp,1,0,0,3.2,3.2,3.2,npth=True);body=[-3.1,-3.1,3.1,3.1]
    else:raise ValueError(k)
    fp.SetAttributes(pcb.FP_SMD if smd else pcb.FP_THROUGH_HOLE)
    # Fabrication outline is a physical body envelope; courtyard includes assembly clearance.
    box(fp,pcb.F_Fab,body,.1)
    cy=[round(body[0]-.5,3),round(body[1]-.5,3),round(body[2]+.5,3),round(body[3]+.5,3)]
    box(fp,pcb.F_CrtYd,cy,.05)
    # Minimal silk: pin-1 dot plus identifier, kept outside the body and copper.
    # Pin 1 is identified by its rectangular copper pad; no silk bar overlaps it.
    fp.Reference().SetPosition(V((body[0]+body[2])/2,cy[1]-1.5))
    fp.Reference().SetTextSize(V(.9,.9));fp.Reference().SetTextThickness(pcb.FromMM(.15))
    fp.Value().SetVisible(False)
    return fp,cy


def underside(fp):
        # PTH pad numbering is intentionally identical in board coordinates.
        # A flip of a stock footprint would mirror the electrical contact order.
        fp.SetLayer(pcb.B_Cu)
        for g in list(fp.GraphicalItems()):
            if g.GetLayer()==pcb.F_Fab:g.SetLayer(pcb.B_Fab)
            if g.GetLayer()==pcb.F_CrtYd:g.SetLayer(pcb.B_CrtYd)
            if g.GetLayer()==pcb.F_SilkS:g.SetLayer(pcb.B_SilkS)
        fp.Reference().SetLayer(pcb.B_SilkS);fp.Reference().SetMirrored(True)


def overlaps(a,b):return a[0]<b[2] and a[2]>b[0] and a[1]<b[3] and a[3]>b[1]


def build(name,desc):
    folder=OUT/name;lib=folder/'SOUNDPCB.pretty';lib.mkdir(exist_ok=True)
    # Do not retain removed components (e.g. the old power selector) in release libraries.
    refs={part['ref'] for part in desc['parts']}
    for obsolete in lib.glob('*.kicad_mod'):
        if obsolete.stem not in refs:obsolete.unlink()
    board=pcb.BOARD();board.SetCopperLayerCount(2)
    board.SetFileName(str(folder/(name+'.kicad_pcb')))
    settings=board.GetDesignSettings()
    settings.m_MinClearance=pcb.FromMM(.2)
    settings.m_TrackMinWidth=pcb.FromMM(.18)
    settings.m_ViasMinSize=pcb.FromMM(.7)
    settings.m_MinThroughDrill=pcb.FromMM(.3)
    w,h=desc['size_mm']
    box(board,pcb.Edge_Cuts,[0,0,w,h],.05)
    netnames=sorted({pn['net'] for p in desc['parts'] for pn in p['pins'] if pn['net'] is not None})
    nets={}
    for n in netnames:
        ni=pcb.NETINFO_ITEM(board,'/'+n);board.Add(ni);nets[n]=ni
    bodies=[];placement=[];fpby={}
    # Fix mechanical interfaces, then large parts, then small parts around them.
    priority=lambda p:0 if p.get('fixed') or p['ref'] in ('A1','JMOD') or p['footprint']['kind']=='hole' else 1 if p['footprint']['kind'] in ('dip','tssop','dip8osc','header') else 2
    for p in sorted(desc['parts'],key=priority):
        fp,cy=footprint(p,name)
        pcb.PCB_IO_KICAD_SEXPR().FootprintSave(str(lib),fp)
        ox,oy=p['xy'];chosen=None
        trial=[(0,0)]
        if priority(p)>0:
            # Deterministic search near the reviewed functional grouping.
            trial+=sorted([(dx,dy) for dx in range(-25,26) for dy in range(-25,26) if dx or dy],
                          key=lambda q:q[0]**2+q[1]**2+abs(q[1])*.1)
        for dx,dy in trial:
            x,y=ox+dx,oy+dy;bb=[x+cy[0],y+cy[1],x+cy[2],y+cy[3]]
            # JLINE mouth is flush with the edge so a plug shoulder can seat.
            # Its body courtyard may extend 0.5mm beyond the PCB; pads remain inside.
            bottom_limit=h+.5 if p['ref']=='JLINE' else h-.5 if p['ref']=='JPOWER' else h-.8
            if min(bb[:2])<.8 or bb[2]>w-.8 or bb[3]>bottom_limit:continue
            if any(overlaps(bb,z) for z in bodies):continue
            chosen=(x,y,bb);break
        if chosen is None:raise RuntimeError('No placement for '+name+'/'+p['ref'])
        x,y,bb=chosen;bodies.append(bb);board.Add(fp)
        if p.get('underside'):underside(fp)
        fp.SetPosition(V(x,y));fpby[p['ref']]=fp
        for padobj in fp.Pads():
            if padobj.GetAttribute()==pcb.PAD_ATTRIB_NPTH:continue
            pin=next((z for z in p['pins'] if z['num']==padobj.GetNumber()),None)
            if pin is None:raise RuntimeError((p['ref'],padobj.GetNumber(),[z['num'] for z in p['pins']]))
            if pin['net'] is not None:padobj.SetNet(nets[pin['net']])
        placement.append(dict(ref=p['ref'],value=p['value'],x_mm=x,y_mm=y,
                              preferred_xy_mm=p['xy'],courtyard=bb,side='bottom' if p.get('underside') else 'top'))
    # Assembly text belongs to the PCB, not a misplaced electrical footprint.
    for text,xy,sz in [('YM2203C SINGLE REV C / PROTOTYPE',(60,7),1.1)]:
        t=pcb.PCB_TEXT(board);t.SetText(text);t.SetPosition(V(*xy));t.SetLayer(pcb.F_SilkS)
        t.SetTextSize(V(sz,sz));t.SetTextThickness(pcb.FromMM(.15));t.SetHorizJustify(pcb.GR_TEXT_H_ALIGN_LEFT);board.Add(t)
    # Place field text clear of all solder-mask openings and board edges.
    pads=[p for fp in board.GetFootprints() for p in fp.Pads()]
    keep=[]
    for p in pads:
        c=p.GetPosition();s=p.GetSize()
        keep.append([pcb.ToMM(c.x-s.x/2)-.35,pcb.ToMM(c.y-s.y/2)-.35,
                     pcb.ToMM(c.x+s.x/2)+.35,pcb.ToMM(c.y+s.y/2)+.35])
    for fp in board.GetFootprints():
        t=fp.Reference();s=t.GetText();pos=t.GetPosition();ox=pcb.ToMM(pos.x);oy=pcb.ToMM(pos.y)
        if fp.GetReference().startswith('H'):
            t.SetLayer(pcb.F_Fab);continue
        tw=max(1,len(s)*.7);th=1
        for dx,dy in sorted([(dx,dy) for dx in range(-6,7) for dy in range(-6,7)],key=lambda z:z[0]**2+z[1]**2):
            x,y=ox+dx,oy+dy;bb=[x-tw/2,y-th/2,x+tw/2,y+th/2]
            if min(bb[:2])<1 or bb[2]>w-1 or bb[3]>h-1:continue
            if any(overlaps(bb,z) for z in keep):continue
            t.SetPosition(V(x,y));keep.append(bb);break
    board.BuildConnectivity()
    pcb.SaveBoard(str(folder/(name+'.kicad_pcb')),board)
    ok=pcb.ExportSpecctraDSN(board,str(folder/(name+'.dsn')))
    if not ok:raise RuntimeError('DSN export failed')
    # pcbnew's DSN exporter uses its default routing widths unless a UI project
    # is loaded. Set the explicit design rules in the standalone routing input.
    dsn=folder/(name+'.dsn');txt=dsn.read_text()
    txt=txt.replace('Via[0-1]_600:300_um','Via[0-1]_700:300_um')
    txt=txt.replace('(circle F.Cu 600)','(circle F.Cu 700)').replace('(circle B.Cu 600)','(circle B.Cu 700)')
    txt=txt.replace('(width 200)','(width 250)').replace('(clearance 50 (type smd_smd))','(clearance 200 (type smd_smd))')
    m=re.search(r'\(class kicad_default ([^()]+)(?=\(circuit)',txt)
    default=m.group(1).split()
    classes=[]
    for cname,cwidth,names in [('PWR5',800,['/+5V','/USB_VBUS','/USB_FUSED','/VSYS']),
                               ('PWR3',400,['/+3V3'])]:
        used=[n for n in names if n in default]
        default=[n for n in default if n not in used]
        if used:classes.append('(class '+cname+' '+' '.join(used)+' (circuit (use_via "Via[0-1]_700:300_um")) (rule (width '+str(cwidth)+') (clearance 200)))\n')
    txt=txt[:m.start()]+''.join(classes)+'(class kicad_default '+' '.join(default)+'\n      '+txt[m.end():]
    # Reserve 30um beyond the PCB's 0.20mm rule: Freerouting may neck down
    # short segments, which finish_pcb.py restores to the 0.18mm minimum.
    txt=txt.replace('(clearance 200)', '(clearance 230)')
    txt=txt.replace('(clearance 200 (type smd_smd))', '(clearance 230 (type smd_smd))')
    txt=re.sub(r'^\(pcb "[^"\n]+"','(pcb "'+name+'.dsn"',txt,count=1)
    dsn.write_text(txt)
    (folder/'fp-lib-table').write_text('(fp_lib_table (version 7) (lib (name "SOUNDPCB") (type "KiCad") (uri "${KIPRJMOD}/SOUNDPCB.pretty") (options "") (descr "Original prototype footprints")))\n')
    (folder/'placement.json').write_text(json.dumps(placement,ensure_ascii=False,indent=2)+'\n')
    print(name,len(placement),'footprints, DSN exported',flush=True)


if __name__=='__main__':
    if len(sys.argv)==1:
        # Separate native sessions avoid a KiCad SWIG teardown fault between boards.
        for n in DESIGN['boards']:
            subprocess.run([sys.executable,__file__,n],check=True)
    else:
        n=sys.argv[1]
        build(n,DESIGN['boards'][n])
        # All outputs are closed synchronously above. Avoid macOS wx/SWIG teardown.
        sys.stdout.flush();sys.stderr.flush();os._exit(0)
