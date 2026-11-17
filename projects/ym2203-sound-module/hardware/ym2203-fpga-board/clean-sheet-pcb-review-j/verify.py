#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native PCB/H-net, mating/socket/UNO and conditional stack verification. No bench claim."""
import argparse, copy, csv, hashlib, json, math
from pathlib import Path
import pcbnew as P

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(Path(p).read_text())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def mm(v):return [round(P.ToMM(v.x),6),round(P.ToMM(v.y),6)]
def require(b,m):
    if not b:raise AssertionError(m)
def contract(d):
    for name in ['mating_error_mm','mount_error_mm','uno_error_mm','core_error_mm']:
        require(d[name]<.0001,name)
    for name in ['electrical_errors','socket_errors','signal_tracks_in_ground_layer','drc_failures','erc_failures','exclusions']:
        require(d[name]==0,name)
    require(not d['tall_parts_under_source'],'stack intrusion')
    require(d['cavity_mm']>=3.5,'stack cavity')

def run(reference,output):
    for rel,digest in read(HERE/'native-binding.json').items():require(sha(HERE/rel)==digest,'stale native report '+rel)
    stats={};placement={};pins={};routes={};solder=[]
    electrical=socket=groundtracks=drc=erc=exclusions=0;tall=[]
    boards={}
    for side,name in [('base','p2-base-j'),('module','p2-ym2203-i')]:
        folder=HERE/side;f=folder/(name+'.kicad_pcb');b=P.LoadBoard(str(f));boards[side]=b
        c=read(folder/'circuit.json');h=read(reference/side/'circuit.json')
        require(c['parts']==h['parts'],'H electrical design or footprint contract changed')
        expected={p['ref']:p for p in c['parts']};fps={f.GetReference():f for f in b.GetFootprints()}
        require(set(expected)<=set(fps),'missing footprint')
        require(set(fps)-set(expected)==({'H'+str(i) for i in range(1,13)} if side=='base' else {'H'+str(i) for i in range(1,5)}),'unexpected PCB-only parts')
        pads_checked=0;byref={}
        for ref,q in expected.items():
            fp=fps[ref];require(fp.GetValue()==q['value'],'value '+ref);require(str(fp.GetFPID().GetLibNickname())+':'+str(fp.GetFPID().GetLibItemName())==q['footprint'],'footprint '+ref);ps={p['num']:p['net'] for p in q['pins']}
            require({p.GetNumber() for p in fp.Pads() if p.GetNumber()}==set(ps),'physical pin set '+ref)
            byref[ref]={}
            for pad in fp.Pads():
                n=pad.GetNumber()
                if not n:continue
                net=pad.GetNetname();want=ps[n]
                electrical+=int(net!=want) if want else int(not net.startswith('unconnected-'))
                byref[ref][n]=dict(xy=mm(pad.GetPosition()),net=want);pads_checked+=1
                if ref=='MPGA' or ref.startswith('JCORE'):
                    socket+=int(abs(P.ToMM(pad.GetDrillSize().x)-1.2)>.0001 or abs(P.ToMM(pad.GetSize().x)-1.9)>.0001)
            if side=='base' and ref not in ['JMOD'] and not ref.startswith('JUNO'):
                if any(p.GetDrillSize().x for p in fp.Pads()):
                    if ref=='MPGA':box=[96.48,6.48,122.38,32.38]
                    else:
                        z=fp.GetBoundingBox(False,False);box=[P.ToMM(z.GetLeft()),P.ToMM(z.GetTop()),P.ToMM(z.GetRight()),P.ToMM(z.GetBottom())]
                    if box[0]<190 and box[2]>90 and box[1]<138 and box[3]>38:tall.append(ref)
        pins[side]=byref
        placement[side]={r:dict(xy=mm(f.GetPosition()),angle=f.GetOrientationDegrees(),layer=f.GetLayerName()) for r,f in fps.items()}
        netroutes={};vias=[]
        for t in b.GetTracks():
            net=t.GetNetname();z=netroutes.setdefault(net,dict(length_mm=0,segments=0,vias=0,layers=set(),min_width_mm=99))
            if isinstance(t,P.PCB_VIA):z['vias']+=1;vias.append(t)
            else:
                groundtracks+=int(t.GetLayer()==P.In1_Cu);z['segments']+=1;z['length_mm']+=P.ToMM(t.GetLength());z['layers'].add(t.GetLayerName());z['min_width_mm']=min(z['min_width_mm'],P.ToMM(t.GetWidth()))
        for z in netroutes.values():z.update(length_mm=round(z['length_mm'],4),layers=sorted(z['layers']),min_width_mm=round(z['min_width_mm'],4))
        routes[side]=netroutes
        for v in vias:
            hole=P.SHAPE_CIRCLE(v.GetPosition(),v.GetDrillValue()//2+P.FromMM(.05))
            for ref,fp in fps.items():
                for pad in fp.Pads():
                    if pad.GetDrillSize().x or pad.GetNetname()!=v.GetNetname():continue
                    for layer in [P.F_Cu,P.B_Cu]:
                        if pad.IsOnLayer(layer) and pad.GetEffectiveShape(layer).Collide(hole,0):
                            solder.append(dict(board=side,ref=ref,pin=pad.GetNumber(),net=v.GetNetname(),via_mm=mm(v.GetPosition()),drill_mm=P.ToMM(v.GetDrillValue())));break
        report=read(folder/'drc.json');counts={k:len(report[k]) for k in ['violations','unconnected_items','schematic_parity']};drc+=sum(counts.values())
        erccount=sum(len(s['violations']) for s in read(folder/'erc.json')['sheets']);erc+=erccount
        proj=read(folder/(name+'.kicad_pro'));exclusions+=len(proj['board']['design_settings']['drc_exclusions'])
        require(b.GetCopperLayerCount()==4,'copper layers')
        require(abs(P.ToMM(b.GetDesignSettings().GetBoardThickness())-1.6)<.0001,'board thickness')
        xy=[mm(v) for item in b.GetDrawings() if isinstance(item,P.PCB_SHAPE) and item.GetLayer()==P.Edge_Cuts for v in [item.GetStart(),item.GetEnd()]]
        dimensions=[max(v[k] for v in xy)-min(v[k] for v in xy) for k in [0,1]]
        require(dimensions==([220,142] if side=='base' else [100,100]),'board outline')
        stats[side]=dict(components=len(expected),pcb_only_holes=len(fps)-len(expected),physical_pad_checks=pads_checked,segments=sum(not isinstance(t,P.PCB_VIA) for t in b.GetTracks()),vias=len(vias),layers=4,erc=erccount,**counts,ignored_checks=report['ignored_checks'],pcb_sha256=sha(f),schematic_sha256=sha(folder/(name+'.kicad_sch')))
    require(placement['base']['JMOD']['layer']=='F.Cu' and placement['module']['JMOD']['layer']=='B.Cu','connector mating faces')
    mating=max(math.dist(pins['base']['JMOD'][str(n)]['xy'],[x+y for x,y in zip(pins['module']['JMOD'][str(n)]['xy'],[90,38])]) for n in range(1,41))
    mount=max(math.dist(placement['base']['H'+str(n+4)]['xy'],[x+y for x,y in zip(placement['module']['H'+str(n)]['xy'],[90,38])]) for n in range(1,5))
    geom=read(reference.parent/'carrier-p2/header-geometry.json')['derived_board_header_facts']
    uno=max(math.dist(pins['base'][p['ref']][str(p['pin'])]['xy'],[p['x_mm']+10,p['y_mm']+10]) for p in geom)
    core=read(HERE/'core-pad-coordinates.json')['pins']
    ce=max(math.dist(pins['module']['JCORE'+p['header'][-1]][str(p['pin'])]['xy'],[p['x_mm']+18,p['y_mm']+66]) for p in core)
    m=read(HERE/'mechanical-review.json');c=m['connector'];cavity=c['analysis_min_face_gap_mm']-c['base_body_max_mm']-c['module_underside_max_mm']
    state=dict(mating_error_mm=mating,mount_error_mm=mount,uno_error_mm=uno,core_error_mm=ce,electrical_errors=electrical,socket_errors=socket,signal_tracks_in_ground_layer=groundtracks,drc_failures=drc,erc_failures=erc,exclusions=exclusions,tall_parts_under_source=tall,cavity_mm=cavity)
    contract(state)
    from stack_checks import inspect
    integration=inspect(boards['base'],boards['module'],reference.parent,HERE)
    mutants={k:(['C1'] if k=='tall_parts_under_source' else 2 if k=='cavity_mm' else 1) for k in state}
    for k,v in mutants.items():
        bad=copy.deepcopy(state);bad[k]=v
        try:contract(bad)
        except AssertionError:pass
        else:raise AssertionError('invalid board accepted '+k)
    for rel,digest in read(HERE/'preservation.json')['inputs_sha256'].items():require(sha(reference.parent/rel)==digest,'historical input changed '+rel)
    result=dict(schema_version=1,date='2026-11-18',revision='3.7-pcb-review-j',tool=P.GetBuildVersion(),scope='native CAD, electrical equivalence and conditional mechanical envelope; no firmware/bench acceptance',boards=stats,integration=integration,contracts=state,positive_checks=len(state),rejection_mutations=len(mutants),mating_positions=40,uno_contacts=len(geom),core_contacts=len(core),hardware_accepted=False,firmware_changed=False)
    if output:
        output.mkdir(exist_ok=True,parents=True)
        for name,data in [('verification.json',result),('stack-verification.json',integration),('routing-review.json',dict(scope='total native segment length including branches; not delay or impedance',nets=routes)),('hand-assembly-vias.json',dict(policy='prefill/flatten before SMT assembly or manufacturing filled/capped; do not silently accept open drill under pad',count=len(solder),sites=solder))]:
            (output/name).write_text(json.dumps(data,indent=2)+'\n')
        for side in placement:
            (output/(side+'-placement.json')).write_text(json.dumps(placement[side],indent=2)+'\n')
            (output/side).mkdir(exist_ok=True)
            with (output/side/'placement.csv').open('w',newline='') as f:
                w=csv.writer(f,lineterminator='\n');w.writerow(['Reference','X_mm','Y_mm','Rotation_deg','Layer'])
                for ref,q in sorted(placement[side].items()):w.writerow([ref,*q['xy'],q['angle'],q['layer']])
    print(json.dumps(result,indent=2));print('hand-assembly via sites',len(solder))

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reference',type=Path,default=HERE.parent/'clean-sheet-schematic-review-h');a.add_argument('--output',type=Path);args=a.parse_args();run(args.reference,args.output)
