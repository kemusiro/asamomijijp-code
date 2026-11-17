#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Mapped FF D/CE/LSR cross-domain census for the two-clock F1 USB top.
Listed two-flop chains are audited separately by check_real_cdc.py. This census
rejects additional combinational cross-domain consumers, including clock enables.
It is not an asynchronous-input, metastability, recovery/removal or analog audit.
"""
from collections import defaultdict
from functools import lru_cache

TOP='revc_usb_ym_top'
PREFIX='board.real_ym.backend.'
CONTROL_META=['board.gates_meta','gates_meta','fault_meta',PREFIX+'fault_meta',PREFIX+'hb_meta',PREFIX+'healthy_meta']
AUDIO_META=[PREFIX+'audible_meta',PREFIX+'sys_meta']
BUNDLE=PREFIX+'rate_meta'
RESET=PREFIX+'sr.release_pipe'
COMB={'LUT4','PFUMX','L6MUX21','CCU2C','MULT18X18D'}


def census(module):
    cells=module['cells'];nets=module['netnames']
    clocks={module['ports'][n]['bits'][0]:n for n in ['clk','audio_clk']}
    if len(clocks)!=2:raise ValueError('Two distinct clocks required')
    sources={};deps={};aliases=defaultdict(list)
    for name,net in nets.items():
        for bit in net['bits']:
            if isinstance(bit,int):aliases[bit].append(name)
    for name,c in cells.items():
        typ=c['type'];co=c['connections']
        if typ not in COMB|{'TRELLIS_FF','DP16KD','TRELLIS_DPR16X4','$scopeinfo'}:raise ValueError('Unaudited cell type '+typ)
        outputs=[b for p,bs in co.items() if c['port_directions'][p]=='output' for b in bs if isinstance(b,int)]
        if typ=='TRELLIS_FF':
            clock=co['CLK'][0]
            if clock not in clocks:raise ValueError('Unconstrained FF clock: '+name)
            for b in outputs:sources[b]=frozenset([clocks[clock]])
        elif typ in ['DP16KD','TRELLIS_DPR16X4']:
            for port,bs in co.items():
                if c['port_directions'][port]!='output':continue
                # ECP5 pseudo-dual-port width36 uses A for writes and B for
                # reads; DOA and DOB together are the B-clocked 36-bit result.
                # See Yosys techlibs/lattice/brams_map_16kd.v $__PDPW16KD_.
                pdp=typ=='DP16KD' and int(c['parameters']['DATA_WIDTH_A'],2)==36
                if pdp and co.get('WEB')!=['0']:raise ValueError('Unexpected PDP read-port write enable')
                ck='WCK' if typ=='TRELLIS_DPR16X4' else 'CLKB' if pdp else 'CLKA' if port.startswith('DOA') else 'CLKB'
                clock=co[ck][0]
                if clock not in clocks:raise ValueError('Unconstrained RAM clock: '+name)
                for b in bs:
                    if isinstance(b,int):sources[b]=frozenset([clocks[clock]])
        elif typ!='$scopeinfo':
            if typ=='MULT18X18D' and any(v!='NONE' for k,v in c['parameters'].items() if k.startswith('REG_') and k.endswith('_CLK')):
                raise ValueError('Registered DSP requires a new clock-domain model')
            ins=[b for p,bs in co.items() if c['port_directions'][p]=='input' for b in bs if isinstance(b,int)]
            for b in outputs:deps[b]=ins
    active=set()
    @lru_cache(None)
    def domains(bit):
        if bit in sources:return sources[bit]
        if bit in active:raise ValueError('Combinational cycle')
        active.add(bit);v=frozenset().union(*(domains(b) for b in deps.get(bit,[])));active.remove(bit);return v
    allowed={}
    for name,dst,src,reason in [(n,'clk','audio_clk','two-flop input') for n in CONTROL_META]+[(n,'audio_clk','clk','two-flop input') for n in AUDIO_META]+[(BUNDLE,'audio_clk','clk','stable bundled configuration; captured only during stream reset')]:
        for bit in nets[name]['bits']:
            if isinstance(bit,int):allowed[(bit,'DI')]=(dst,src,reason)
    for bit in nets[RESET]['bits']:allowed[(bit,'LSR')]=('audio_clk','clk','asynchronous assert into synchronous-release reset chain')
    rows=[];ff_count=0
    for name,c in cells.items():
        if c['type']!='TRELLIS_FF':continue
        ff_count+=1;dst=clocks[c['connections']['CLK'][0]];q=c['connections']['Q'][0]
        for port,bs in c['connections'].items():
            if c['port_directions'][port]!='input' or port=='CLK':continue
            cross=set().union(*(domains(b) for b in bs if isinstance(b,int)))-{dst}
            if not cross:continue
            rule=allowed.get((q,port))
            if rule is None or rule[:2]!=(dst,next(iter(cross))) or len(cross)!=1:
                raise ValueError('Unclassified CDC consumer: '+name+'/'+port+' '+str(sorted(cross))+' -> '+dst)
            if port=='LSR' and c['parameters'].get('SRMODE')!='ASYNC':raise ValueError('Reset crossing must be asynchronous assertion')
            rows.append({'cell':name,'port':port,'from':rule[1],'to':dst,'reason':rule[2]})
    return {'ff_bits_checked':ff_count,'cross_domain_input_bits':len(rows),'consumers':rows,
        'scope':'All mapped FF D/CE/LSR cones for listed cell types; primary async inputs and physical timing are outside this census',
        'unclassified_crossings':0,'physical_cdc_signoff':False}
