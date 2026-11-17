# SPDX-License-Identifier: MIT
"""Audit mapped data/enable crossings. Asynchronous reset paths are inventoried separately."""
from functools import lru_cache


def inspect(netlist):
    m = netlist['modules']['jt03_minimal']
    cells, nets = m['cells'], m['netnames']
    synth = m['ports']['synth_clk']['bits'][0]
    audio = m['ports']['audio_clk']['bits'][0]
    domains = {synth: 'synth', audio: 'audio'}
    drivers = {}
    primary = set()
    for p in m['ports'].values():
        if p['direction']=='input': primary.update(b for b in p['bits'] if isinstance(b,int))
    for n,c in cells.items():
        for p,d in c.get('port_directions',{}).items():
            if d=='output':
                for b in c['connections'][p]:
                    if isinstance(b,int): drivers[b]=(n,c,p)
    def domain(c, port):
        return domains.get(c['connections'].get(port, [None])[0])
    @lru_cache(None)
    def origins(b):
        if not isinstance(b,int): return frozenset()
        item=drivers.get(b)
        if item is None:return frozenset(['external']) if b in primary else frozenset()
        n,c,p=item;t=c['type']
        if t.startswith('SB_DFF'):return frozenset([domain(c,'C')])
        if t.startswith('SB_RAM40_4K'):return frozenset([domain(c,'RCLK')])
        if t=='SB_MAC16' and domain(c,'CLK'):return frozenset([domain(c,'CLK')])
        result=set()
        for port,d in c.get('port_directions',{}).items():
            if d=='input':
                for bit in c['connections'][port]:result.update(origins(bit))
        return frozenset(result)
    expected={}
    def mark(name,which,target):
        if name not in nets:raise ValueError('Missing kept synchronizer '+name)
        bits=nets[name]['bits'] if which=='all' else [nets[name]['bits'][which]]
        for b in bits:expected[b]=(name,target)
    for n in ['pcm_fifo.rq1_wgray']:mark(n,'all','audio')
    for n in ['pcm_fifo.wq1_rgray']:mark(n,'all','synth')
    for n in ['prime_sync','bad_sync','hb_sync']:mark(n,0,'synth')
    mark('run_sync',0,'audio')
    for n in ['spi.cs_sync','spi.sck_sync','spi.mosi_sync']:mark(n,0,'synth')
    found=[];violations=[]
    for n,c in cells.items():
        if not c['type'].startswith('SB_DFF'):continue
        dest=domain(c,'C')
        if dest is None:raise ValueError('Unexpected clock on '+n)
        q=c['connections']['Q'][0]
        for p in ['D','E']:
            if p not in c['connections']:continue
            src=set()
            for b in c['connections'][p]:src.update(origins(b))
            other=src-{dest}
            if not other:continue
            if q not in expected or expected[q][1]!=dest or p!='D':
                violations.append({'cell':n,'port':p,'sources':sorted(map(str,other)),'destination':dest})
            else:
                # Require the first synchronizer D to be a direct FF Q (Gray bus),
                # or an external pin (SPI), never unregistered combinational Gray.
                b=c['connections']['D'][0];driver=drivers.get(b)
                direct=b in primary or (driver and driver[1]['type'].startswith('SB_DFF'))
                if not direct:violations.append({'cell':n,'reason':'nonregistered crossing'})
                found.append({'sink':expected[q][0],'sources':sorted(map(str,other)),'destination':dest})
    dual_ram=[]
    for n,c in cells.items():
        if not c['type'].startswith('SB_RAM40_4K'):continue
        rd,wr=domain(c,'RCLK'),domain(c,'WCLK')
        if rd and wr and rd!=wr:
            if (wr,rd)!=('synth','audio'):violations.append({'cell':n,'reason':'unexpected RAM clocks'})
            for port,d in c.get('port_directions',{}).items():
                if d!='input' or port in ['RCLK','WCLK']:continue
                target=rd if port.startswith('R') else wr
                for bit in c['connections'][port]:
                    if origins(bit)-{target}:violations.append({'cell':n,'port':port,'reason':'RAM port CDC'})
            dual_ram.append({'cell':n,'write_clock':wr,'read_clock':rd})
    if any(c['type'].startswith('SB_RAM40_4K') for c in cells.values()) and len(dual_ram)!=1:
        violations.append({'reason':'expected exactly one PCM dual-clock RAM'})
    if violations:raise ValueError('Unapproved data/enable CDC: '+str(violations))
    if len(found)!=21:raise ValueError(f'Expected 21 first-stage bits, saw {len(found)}')
    return {'checked_first_stage_bits':len(found),'crossings':found,'dual_clock_ram':dual_ram,
            'unexpected_data_or_enable_crossings':0,
            'async_reset_release':'separate two-flop reset_sync per domain; asynchronous assertion',
            'exceptions':'reset-control pins and asynchronous safety output are outside this data-path audit'}
