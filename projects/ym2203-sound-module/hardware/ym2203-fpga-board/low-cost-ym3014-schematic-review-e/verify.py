#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent pin, preservation, footprint, level and purchase checks for E."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,math,re
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent

def read(p):return json.loads(p.read_text())
def main():
 old=ROOT/'low-cost-schematic-review-c'
 d={b:read(HERE/b/'circuit.json') for b in ['base','module','panel']}
 by={b:{p['ref']:p for p in v['parts']} for b,v in d.items()}
 prev={b:read(old/b/'circuit.json') for b in d}
 # Base, panel and all MCU pinout/GPIO identities preserved exactly.
 for b in ['base','panel']:assert d[b]['parts']==prev[b]['parts'],b
 m=by['module'];oldm={p['ref']:p for p in prev['module']['parts']}
 def nets(ref):return {p['num']:p['net'] for p in m[ref]['pins']}
 def expected(ref,pin,net):assert nets(ref)[str(pin)]==net,(ref,pin,net)
 assert m['USOURCE']==oldm['USOURCE']
 changed=set()
 for ref,p in oldm.items():
  new=m[ref]
  if new!=p:changed.add(ref)
 assert changed=={'JMOD','U16','ULINK1','RSMIXA','RSMIXB','RSMIXC'},changed
 for ref in changed:
  a={k:v for k,v in m[ref].items() if k!='note'};b={k:v for k,v in oldm[ref].items() if k!='note'}
  if ref=='JMOD':
   assert all(x==y for x,y in zip(a['pins'],b['pins']) if x['num']!='39')
  elif ref.startswith('RSMIX'):
   assert a['pins'][0]==b['pins'][0];assert a['value']==b['value'];expected(ref,2,'AUDIO_R')
  else:assert a==b,ref
 expected('JMOD',37,'AUDIO_L');expected('JMOD',39,'AUDIO_R')
 for n in [31,33,34,7,8,25]:assert nets('JMOD')[str(n)]==next(x['net'] for x in oldm['JMOD']['pins'] if x['num']==str(n))
 # Manufacturer 16SOP pinout, independent of design.py. NC are genuinely disconnected.
 expected_dac={'1':'V5_MODULE','2':'DAC_TO_BUFF','4':'DAC_LOAD','7':'DAC_SD','10':'DAC_CLK','12':'GND','14':'DAC_RB','16':'DAC_MP'}
 for n,v in expected_dac.items():expected('UDAC',n,v)
 assert set(nets('UDAC'))==set(map(str,range(1,17)))
 for n in [3,5,6,8,9,11,13,15]:
  expected('UDAC',n,None);assert next(p['type'] for p in m['UDAC']['pins'] if p['num']==str(n))=='no_connect'
 assert nets('UAF')=={'1':'DAC_MP','2':'DAC_MP','3':'DAC_RB','4':'GND','5':'DAC_TO_BUFF','6':'FM_BUF','7':'FM_BUF','8':'V5_MODULE'}
 assert m['UAF']['value']=='MCP6002-E/P'
 assert nets('CRB')=={'1':'DAC_RB','2':'GND'}
 assert nets('RFMOUT')=={'1':'FM_BUF','2':'AUDIO_L'};assert m['RFMOUT']['value']=='100'
 for ref,src,dst in [('RFMSD','Y_SD','DAC_SD'),('RFMCLK','Y_CLK','DAC_CLK'),('RFMSH','Y_SH','DAC_LOAD')]:
  assert nets(ref)=={'1':src,'2':dst};assert m[ref]['value']=='33'
 expected('U12',23,'Y_SD');expected('U12',22,'Y_SH');expected('U12',39,'Y_CLK')
 expected('U12',38,'Y_PHI_M');assert nets('RFMCLK')['1']!='Y_PHI_M'
 for ref in ['CFMDAC','COPAMP','CANABULK']:assert set(nets(ref).values())=={'V5_MODULE','GND'}
 # Native ERC checked without exclusions; exact physical netlist verified by generator.
 native=read(HERE/'native-verification.json');assert native['kicad_version']=='10.0.5'
 for board in d:
  assert not [v for sh in read(HERE/board/'erc.json')['sheets'] for v in sh['violations']]
  assert native['boards'][board]['components']==len(by[board])
 # Old saved files and old review's preservation manifest remain byte-identical.
 preserved=read(HERE/'preservation.json')['files']
 for n,h in preserved.items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 for n,h in read(old/'preservation.json')['files'].items():assert hashlib.sha256((ROOT/n).read_bytes()).hexdigest()==h,n
 # Datasheet-derived footprint, numbering/pitch and front-side pad spans.
 fp=(HERE/'P2LC.pretty/YM3014BF_SOP16_5.3x10.2_P1.27mm.kicad_mod').read_text()
 pads=re.findall(r'\(pad "(\d+)" smd roundrect \(at ([-\d.]+) ([-\d.]+)\) \(size ([-\d.]+) ([-\d.]+)\)',fp)
 assert len(pads)==16 and {int(p[0]) for p in pads}==set(range(1,17))
 geom={int(n):(float(x),float(y),float(w),float(h)) for n,x,y,w,h in pads}
 for i in range(8):
  y=-4.445+i*1.27
  assert math.isclose(geom[i+1][1],y,abs_tol=1e-6) and geom[i+1][0]==-3.55
  assert geom[16-i][0]==3.55 and math.isclose(geom[16-i][1],y,abs_tol=1e-6)
  assert geom[i+1][2:]==(1.6,.65)
 # Small-signal upper-bound calculation; not SPICE or guaranteed device limits.
 gain_min=9900/(9900+6868+101);gain_max=10100/(10100+6732+99)
 vmax=5.25;fm_peak_before_adc=vmax/4+.009
 peak=fm_peak_before_adc*gain_max
 assert peak<.81
 assert 1.65-peak>.8 and 1.65+peak<2.5
 required_slew=2*math.pi*20000*(vmax/4)/1e6
 assert required_slew<.6 # typical MCP6002 SR; not minimum-over-temperature proof.
 # Purchase: each installed ref appears once, no lost retained ADC/DAC/MCUs.
 q=read(HERE/'purchase-plan.json');refs=[r for row in q['rows'] for r in row['refs']]
 allrefs={b+':'+ref for b,p in by.items() for ref in p}
 assert len(refs)==len(set(refs)) and set(refs)==allrefs
 for row in q['rows']:
  assert Decimal(row['subtotal_jpy'])==Decimal(row['price_jpy_incl'])*row['buy_packs']
  assert row['purchased']==row['pack']*row['buy_packs']
  assert row['spare']==row['purchased']+row['stock']-row['used']>=0
 assert q['parts_goods_jpy']==math.ceil(sum(Decimal(r['subtotal_jpy']) for r in q['rows']))
 assert q['total_jpy']==sum(q[k] for k in ['parts_goods_jpy','parts_freight_jpy','pcb_goods_jpy','pcb_freight_allowance_jpy','reserve_jpy'])
 assert q['pcb_each']==5 and q['populated_sets']==1
 rows={r['id']:r for r in q['rows']}
 assert rows['YM_DAC']['stock']==1 and rows['YM_DAC']['buy_packs']==0
 for id in ['MBASE','MSOURCE','MPANEL','ADC','DAC','U01']:assert rows[id]['used']==1
 result=dict(date='2026-11-19',result='PASS',scope='native ERC, independent static pin/power/routing/budget/preservation checks; no firmware or bench acceptance',
  boards=native['boards'],installed_refs=len(allrefs),purchase_rows=len(rows),total_jpy=q['total_jpy'],delta_review_C_jpy=q['total_jpy']-29751,
  preserved_current_files=len(preserved),preserved_prior_files=len(read(old/'preservation.json')['files']),
  gpio_changed=False,base_and_panel_electrical_parts_unchanged=True,
  analog_calculation={'pre_coupling_unloaded_divider_gain_range_1percent':[gain_min,gain_max],'fm_conservative_peak_at_adc_v':peak,'assumed_adc_bias_v':1.65,'required_20khz_slew_v_per_us':required_slew,'opamp_typical_slew_v_per_us':.6,'spice_or_hardware_measurement':False},
  footprint={'pads':16,'pitch_mm':1.27,'sample_fit_verified':False},pcb_created=False,firmware_implemented=False,hardware_accepted=False)
 (HERE/'verification.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))
if __name__=='__main__':main()
