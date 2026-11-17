#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Limited mapped-netlist structural checks; not an exhaustive CDC/STA analysis."""
import argparse
import copy
import json
from pathlib import Path

# Every declared two-flop input/single-bit crossing must retain its direct pair.
PAIRS=[('backend.audio.rx.meta','backend.audio.rx.sync','audio_clk'),
       ('backend.bus.data_meta','backend.bus.data_sync','clk'),
       ('control.target.scl_meta','control.target.scl_sync','clk'),
       ('control.target.sda_meta','control.target.sda_sync','clk'),
       *[('backend.'+n+'_meta','backend.'+n+'_sync',clock) for n,clock in
         [('audible','audio_clk'),('sys','audio_clk'),('hb','clk'),('healthy','clk'),('fault','clk')]]]
REGISTERED=['backend.bus.'+n+'_pin' for n in ['cs','wr','rd','a0','oe','drive']]+['ym_data_out',
    'backend.pipeline_reset','backend.arm_state','backend.release_state','backend.gate_open']


def check(module,prefix="",clocked=False,usb=False):
    nets=module['netnames'];cells=module['cells'];drivers={}
    for name,c in cells.items():
        if c['type']=='TRELLIS_FF':
            for b in c['connections']['Q']:drivers[b]=(name,c)
    def ff(bit):
        if bit not in drivers:raise ValueError('Expected register for bit '+str(bit))
        return drivers[bit][1]
    pairs=[(prefix+a,prefix+b,c) for a,b,c in PAIRS]
    cp='board.' if usb else ''
    if usb:
        pairs.extend([(n+'_meta',n+'_sync','clk') for n in ['gates','fault']])
        pairs.extend([('usb_device.'+a,'usb_device.'+b,'clk') for a,b in [('rx_meta','rx_sync'),('vbus_meta','vbus_sync')]])
    if clocked:
        pairs.append((cp+'gates_meta',cp+'gates_sync','clk'))
        pairs.extend([(cp+'clocks.master.'+n+'_meta',cp+'clocks.master.'+n+'_sync','clk') for n in ['scl','sda']])
        pairs.append((prefix+'backend.rate_meta',prefix+'backend.rate_sync','audio_clk'))
    total=0;constants=0
    for meta,sync,clock in pairs:
        a=nets[meta]['bits'];b=nets[sync]['bits'];clk=module['ports'][clock]['bits']
        if len(a)!=len(b):raise ValueError('Synchronizer width mismatch: '+meta)
        for first,second in zip(a,b):
            if isinstance(first,str) and first==second:
                constants+=1;continue
            f=ff(first);s=ff(second)
            if f['connections']['CLK']!=clk or s['connections']['CLK']!=clk:raise ValueError('Wrong synchronizer clock: '+meta)
            if s['connections']['DI']!=[first]:raise ValueError('Synchronizer bypass: '+sync)
            # First stage data/enable can feed only the second-stage DI, never logic.
            for cell in cells.values():
                for port,bits in cell['connections'].items():
                    if cell['port_directions'][port]=='input' and first in bits:
                        if cell is not s or port!='DI':raise ValueError('First-stage fanout: '+meta+' '+port)
            total+=1
    pin_bits=0
    controls=[prefix+n if n!='ym_data_out' else n for n in REGISTERED]
    if clocked:controls+=[cp+n for n in ['clocks.master.scl_drive','clocks.master.sda_drive','clocks.ready']]
    if clocked:controls.append('active_profile')
    for name in controls:
        for b in nets[name]['bits']:
            if ff(b)['connections']['CLK']!=module['ports']['clk']['bits']:raise ValueError('Wrong pin register clock: '+name)
            pin_bits+=1
    reset_bits=0
    reset_pairs=[(prefix+n,c) for n,c in [('backend.ar.release_pipe','audio_clk'),('backend.sr.release_pipe','audio_clk'),('backend.cr.release_pipe','clk')]]
    if clocked:reset_pairs.append((cp+'management_domain.release_pipe','clk'))
    if usb:reset_pairs.extend([('usb_device.usb_domain.release_pipe','clk'),('domain.release_pipe','clk')])
    for name,clock in reset_pairs:
        bits=nets[name]['bits']
        if len(bits)!=2 or ff(bits[1])['connections']['DI']!=[bits[0]]:raise ValueError('Reset release chain: '+name)
        for b in bits:
            if ff(b)['connections']['CLK']!=module['ports'][clock]['bits']:raise ValueError('Reset clock: '+name)
        reset_bits+=2
    return {'synchronizer_bits':total,'constant_synchronizer_bits':constants,'registered_control_bits':pin_bits,'reset_release_bits':reset_bits}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('netlist',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--clocked',action='store_true');p.add_argument('--usb',action='store_true')
    a=p.parse_args();prefix='real_ym.' if a.clocked else '';top='revc_clocked_ym_top' if a.clocked else 'revc_real_ym_top'
    if a.usb:a.clocked=True;prefix='board.real_ym.';top='revc_usb_ym_top'
    m=json.loads(a.netlist.read_text())['modules'][top];r=check(m,prefix,a.clocked,a.usb)
    mutations=0
    for first_name,second_name,_ in [PAIRS[1],PAIRS[-2]]:
        meta=prefix+first_name;sync=prefix+second_name
        bad=copy.deepcopy(m);bit=bad['netnames'][sync]['bits'][0]
        first=bad['netnames'][meta]['bits'][0]
        source=next(c['connections']['DI'] for c in bad['cells'].values() if c['type']=='TRELLIS_FF' and c['connections']['Q']==[first])
        c=next(c for c in bad['cells'].values() if c['type']=='TRELLIS_FF' and c['connections']['Q']==[bit])
        c['connections']['DI']=source[:]
        try:check(bad,prefix,a.clocked,a.usb)
        except ValueError:mutations+=1
        else:raise RuntimeError('Mutation not detected: '+sync)
    r.update({'mutation_bypasses_rejected':mutations,'scope':'listed direct synchronizer chains, exclusive first-stage fanout, reset release pairs and registered controls only',
              'exhaustive_cdc':False,'sta_mtbf_signoff':False})
    a.output.write_text(json.dumps(r,indent=2)+'\n');print('PASS clock-boundary structure:',r)


if __name__=='__main__':main()
