# SPDX-License-Identifier: MIT
"""Strict acceptance of internal ECP5 OOC timing reports (not board signoff)."""
from check_real_cdc import PAIRS
CLOCKS={'clk':48.0,'audio_clk':49.152}

def timing(report):
    if set(report['fmax'])!=set(CLOCKS):raise ValueError('Missing or unexpected timed clock')
    rows={}
    for name,mhz in CLOCKS.items():
        item=report['fmax'][name];required=float(item['constraint']);actual=float(item['achieved'])
        if abs(required-mhz)>0.01:raise ValueError('Clock constraint changed: '+name)
        if actual<required:raise ValueError('Timing failed: '+name)
        rows[name]={'required_mhz':required,'fmax_mhz':actual,'setup_margin_ns':1000/required-1000/actual}
    if report['utilization']['TRELLIS_IO']['used']!=0 or report['utilization']['DCCA']['used']!=0:
        raise ValueError('Expected IO/global-clock-free out-of-context evaluation')
    paths=[]
    for p in report['critical_paths']:
        path=p['path']
        paths.append({'from':p['from'],'to':p['to'],'delay_ns':sum(float(x['delay']) for x in path),
            'start':path[0]['from']['cell'],'end':path[-1]['to']['cell'],
            'source_locations':sorted({s.rsplit('/',1)[-1] for x in path for s in x.get('sources',[])})})
    return {'clocks':rows,'utilization':report['utilization'],'critical_paths':paths}

def stage_delays(module,report):
    """Require every nonconstant synchronizer stage1->stage2 net in the route report.
    A half-period interstage budget is a placement acceptance guard, not an MTBF claim.
    """
    prefix='board.real_ym.'
    pairs=[(prefix+a,prefix+b,c) for a,b,c in PAIRS]
    pairs += [('board.clocks.master.'+n+'_meta','board.clocks.master.'+n+'_sync','clk') for n in ['scl','sda']]
    pairs += [(prefix+'backend.rate_meta',prefix+'backend.rate_sync','audio_clk')]
    pairs += [(p+n+'_meta',p+n+'_sync','clk') for p,n in [('board.','gates'),('','gates'),('','fault'),('usb_device.','rx'),('usb_device.','vbus')]]
    drivers={b:n for n,c in module['cells'].items() if c['type']=='TRELLIS_FF' for b in c['connections']['Q']}
    # Include synchronous reset-release pairs as well, without assigning a false path.
    reset_pairs=[(prefix+'backend.'+n+'.release_pipe',c) for n,c in [('ar','audio_clk'),('sr','audio_clk'),('cr','clk')]]
    reset_pairs += [('board.management_domain.release_pipe','clk'),('usb_device.usb_domain.release_pipe','clk'),('domain.release_pipe','clk')]
    bit_pairs=[]
    for first,second,clock in pairs:
        bit_pairs += [(a,b,clock,first) for a,b in zip(module['netnames'][first]['bits'],module['netnames'][second]['bits']) if isinstance(a,int)]
    for name,clock in reset_pairs:
        a,b=module['netnames'][name]['bits'];bit_pairs.append((a,b,clock,name))
    routes={}
    for net in report['detailed_net_timings']:
        for e in net['endpoints']:
            if e['port'] in ['M','DI']:routes[(net['driver'],e['cell'])]=max(map(float,e['delay']))
    rows=[]
    for a,b,clock,name in bit_pairs:
        key=(drivers[a],drivers[b])
        if key not in routes:raise ValueError('Missing interstage route: '+name+' '+str(key))
        delay=routes[key];budget=500/CLOCKS[clock]
        if delay>=budget:raise ValueError('Interstage route exceeds half-period budget: '+name)
        rows.append({'first_cell':key[0],'second_cell':key[1],'clock':clock,'max_net_delay_ns':delay,'budget_ns':budget})
    return {'checks':len(rows),'max_interstage_net_delay_ns':max(x['max_net_delay_ns'] for x in rows),
        'scope':'Listed synchronizer and reset-release net delay only; ideal OOC clocks, no MTBF or recovery/removal signoff','routes':rows}
