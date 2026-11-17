# SPDX-License-Identifier: MIT
"""Strict ULX3S pad/clock acceptance. Physical routes, not electrical signoff."""
import copy
from check_real_cdc import check
from check_pnr_cdc import census
from tools.pnr_checks import stage_delays

CLOCKS={'$glbnet$clk':50.,'$glbnet$audio49$TRELLIS_IO_IN':49.152}
GUARD_NS={'$glbnet$clk':0.65,'$glbnet$audio49$TRELLIS_IO_IN':0.25}
FIXED={'ref12':'P3','audio49':'A10','usb_dp_rx':'E16','usb_dn_rx':'F16','usb_dp_tx':'D15','usb_dn_tx':'E15','usb_dp_bias':'B12','usb_dn_bias':'C12','esp_en':'F1'}

def lpf(manifest):
 ps=manifest['pins']
 if len({p['port'] for p in ps})!=len(ps) or len({p['ball'] for p in ps})!=len(ps):raise ValueError('Duplicate port/pin')
 for p in ps:
  if p['port'] in FIXED and p['ball']!=FIXED[p['port']]:raise ValueError('Wrong fixed board connection')
  if p['io_type']!='LVCMOS33' or manifest['bank_vccio_volts'][str(p['bank'])]!=3.3:raise ValueError('Wrong IO voltage')
  if p['ball'] in ['F4','E3','G3','F3','H4','G5','G2','M4','R2','W2','V2','W1','Y2']:raise ValueError('Reserved board pin')
 if {p['port'] for p in ps}&set(FIXED)!=set(FIXED):raise ValueError('Missing fixed board connection')
 lines=['# Generated from pins.json. No unconstrained physical ports.']
 for p in ps:
  lines += [f'LOCATE COMP "{p["port"]}" SITE "{p["ball"]}";',f'IOBUF PORT "{p["port"]}" IO_TYPE=LVCMOS33 PULLMODE={p["pull"]}'+(' DRIVE=4 SLEWRATE=SLOW' if p['direction']!='input' else '')+';']
 return '\n'.join(lines)+'\n'

def netlist_view(module):
 # Keep every mapped FF, including the carrier synchronizers and heartbeat.
 # Remove only the analog PLL and top-level tristates from the digital FF-cone census.
 n=copy.deepcopy(module)
 n['netnames']={(k[5:] if k.startswith('core.') else k):v for k,v in n['netnames'].items()}
 n['netnames']['ym_data_out']=module['netnames']['core.board.real_ym.ym_data_out']
 n['netnames']['active_profile']=module['netnames']['core.board.clocks.active_profile']
 n['ports']={'clk':{'bits':module['netnames']['clk']['bits']},'audio_clk':{'bits':module['ports']['audio49']['bits']}}
 n['cells']={k:c for k,c in n['cells'].items() if c['type'] not in ['EHXPLLL','$_TBUF_','TRELLIS_IO']}
 return n

def pad_drivers(module):
 # Open-drain bus must never source HIGH; ULX3S bias must never select pulldown.
 for name,constant in [('host_scl','0'),('host_sda','0'),('si_scl','0'),('si_sda','0'),('usb_dp_bias','1')]:
  bit=module['ports'][name]['bits']
  buf=[c for c in module['cells'].values() if c['type']=='$_TBUF_' and c['connections']['Y']==bit]
  if len(buf)!=1 or buf[0]['connections']['A']!=[constant]:raise ValueError('Wrong open-drain/bias driver: '+name)
 bufs=[c for c in module['cells'].values() if c['type']=='TRELLIS_IO' and c['connections']['B']==module['ports']['usb_dn_bias']['bits']]
 if len(bufs)!=1 or bufs[0]['connections']['T']!=['1']:raise ValueError('USB D- bias must stay physically high-Z')

def mapped_checks(module):
 pad_drivers(module)
 pll=[c for c in module['cells'].values() if c['type']=='EHXPLLL']
 if len(pll)!=1:raise ValueError('Exactly one PLL required')
 p=pll[0]['parameters']
 for name,expected in [('CLKI_DIV',1),('CLKFB_DIV',4),('CLKOP_DIV',12)]:
  if int(p[name],2)!=expected:raise ValueError('PLL ratio changed')
 if p['FEEDBK_PATH']!='INT_OP':raise ValueError('Internal PLL feedback required')
 n=netlist_view(module)
 pairs=check(n,'board.real_ym.',True,True)
 drivers={b:c for c in n['cells'].values() if c['type']=='TRELLIS_FF' for b in c['connections']['Q']}
 for first,second in [('stop_meta','stop_sync'),('config_meta','config_sync'),('profile_meta','profile_sync')]:
  for a,b in zip(n['netnames'][first]['bits'],n['netnames'][second]['bits']):
   if drivers[b]['connections']['DI']!=[a]:raise ValueError('Carrier synchronizer bypass')
   for c in n['cells'].values():
    for port,bs in c['connections'].items():
     if c['port_directions'][port]=='input' and a in bs and (c is not drivers[b] or port!='DI'):raise ValueError('Carrier first-stage fanout')
 a,b=n['netnames']['pad_domain.release_pipe']['bits']
 if drivers[b]['connections']['DI']!=[a]:raise ValueError('Carrier reset bypass')
 return {'direct_pairs':pairs,'ff_cones':census(n),'pll_pfd_hz':12000000,'pll_vco_hz':576000000,'pll_output_hz':48000000}

def routed_checks(report,routed,manifest,mapped,clock_routes):
 if set(report['fmax'])!=set(CLOCKS):raise ValueError('Missing/extra timed clock')
 clocks={}
 for name,mhz in CLOCKS.items():
  v=report['fmax'][name];freq=float(v['constraint']);ach=float(v['achieved'])
  if abs(freq-mhz)>.01 or ach<freq:raise ValueError('Failed/relaxed clock')
  nominal=48. if name=='$glbnet$clk' else 49.152
  margin=1000/nominal-1000/ach
  if margin<GUARD_NS[name]:raise ValueError('Engineering period reserve not met: '+name)
  clocks[name]={'nominal_mhz':nominal,'required_mhz':freq,'fmax_mhz':ach,'nominal_margin_ns':margin,'engineering_reserve_ns':GUARD_NS[name],'remaining_margin_ns':margin-GUARD_NS[name]}
 util=report['utilization']
 for typ,number in [('TRELLIS_IO',len(manifest['pins'])),('DCCA',2),('EHXPLLL',1)]:
  if util[typ]['used']!=number:raise ValueError('Wrong physical resource count: '+typ)
 if routed['settings'].get('out_of_context','0') not in ['0','00000000000000000000000000000000']:raise ValueError('OOC mode forbidden')
 if routed['settings']['arch.speed']!='6' or routed['settings']['arch.package']!='CABGA381':raise ValueError('Wrong physical device context')
 ios={c['attributes']['LOC']:c for c in routed['cells'].values() if c['type']=='TRELLIS_IO'}
 for pin in manifest['pins']:
  c=ios[pin['ball']];a=c['attributes']
  if a.get('IO_TYPE')!='LVCMOS33' or a.get('PULLMODE')!=pin['pull'] or not a.get('NEXTPNR_BEL'):raise ValueError('Unplaced/wrong pad configuration')
  # Verify physical top bit -> exact pad, not just the set of used balls.
  name=pin['port'];base=name.split('[')[0];idx=int(name.split('[')[1][:-1]) if '[' in name else 0
  if c['connections']['B']!=[routed['ports'][base]['bits'][idx]]:raise ValueError('Pin permutation')
 for c in clock_routes['clock_cells']:
  if not c['bel'] or any(p['model_max_ns'] is None for p in c['ports']):raise ValueError('Missing clock route')
 # Bound individual pad-connected routing nets; this is not pad/PCB setup or hold STA.
 io_nets=[]
 for net in report['detailed_net_timings']:
  for e in net['endpoints']:
   if net['driver'].endswith('$tr_io') or e['cell'].endswith('$tr_io'):
    vals=list(map(float,e['delay']));maximum=max(vals)
    if maximum>40:raise ValueError('Pad routing net exceeds 40ns engineering bound')
    io_nets.append({'driver':net['driver'],'sink':e['cell'],'port':e['port'],'min_route_ns':min(vals),'max_route_ns':maximum})
 if not io_nets:raise ValueError('No pad timing evidence')
 # I2S data/LRCK change on falling BCLK; bound setup and hold at next/previous rising BCLK.
 paths={}
 for n in io_nets:
  for p in ['i2s_bclk','i2s_lrck','i2s_data']:
   if n['sink']==p+'$tr_io' and n['port']=='I':paths[p]=n
 if len(paths)!=3:raise ValueError('Missing I2S pad routes')
 worst=max(p['max_route_ns'] for p in paths.values())-min(p['min_route_ns'] for p in paths.values())
 # Explicit design allowances: 4ns pad skew, 2ns PCB skew, 10ns receiver setup/hold.
 # These are carrier requirements, not measured or inferred device guarantees.
 allowance=4+2+10+GUARD_NS['$glbnet$audio49$TRELLIS_IO_IN']
 i2s_margin=1e9/(3072000*2)-worst-allowance
 if i2s_margin<=0:raise ValueError('I2S design budget exceeded')
 pair=stage_delays(netlist_view(mapped),report);pair['scope']='Listed synchronizer net routing with placed clocks; no MTBF, global clock skew or reset recovery/removal signoff'
 # Additional carrier synchronizer/reset route pairs.
 bits=[];view=netlist_view(mapped)
 for a,b in [('stop_meta','stop_sync'),('config_meta','config_sync'),('profile_meta','profile_sync')]:bits+=list(zip(view['netnames'][a]['bits'],view['netnames'][b]['bits']))
 bits += [tuple(view['netnames']['pad_domain.release_pipe']['bits'])]
 driver={b:n for n,c in mapped['cells'].items() if c['type']=='TRELLIS_FF' for b in c['connections']['Q']}
 routes={(n['driver'],e['cell']):max(e['delay']) for n in report['detailed_net_timings'] for e in n['endpoints'] if e['port'] in ['M','DI']}
 extra=[routes[(driver[a],driver[b])] for a,b in bits]
 if max(extra)>=10:raise ValueError('Carrier synchronizer route too long')
 return {'clocks':clocks,'utilization':util,'synchronizer_routes':pair,'carrier_interstage_checks':len(extra),'carrier_max_interstage_route_ns':max(extra),
  'pad_route_nets':io_nets,'max_pad_net_route_ns':max(n['max_route_ns'] for n in io_nets),
  'i2s_budget':{'bclk_hz':3072000,'half_period_ns':1e9/(3072000*2),'route_spread_ns':worst,'external_allowance_ns':allowance,'setup_and_hold_design_margin_ns':i2s_margin,'physical_signoff':False},
  'clock_tree':clock_routes}
