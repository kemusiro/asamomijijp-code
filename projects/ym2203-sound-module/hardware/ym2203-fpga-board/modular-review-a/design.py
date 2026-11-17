# SPDX-License-Identifier: MIT
"""P2 split review A. Existing native GPIO unchanged; no firmware or PCB port."""
from pathlib import Path
from copy import deepcopy
import hashlib,json
HERE=Path(__file__).resolve().parent
REFERENCE=HERE.parent/'carrier-p2/pcb-review-b/schematic/circuit.json'
PINFILE=HERE.parent/'carrier-p2/pins.json'
V3='V3V3';V5='V5_CARRIER';G='GND'
SOURCES={
 'id':'https://ww1.microchip.com/downloads/aemDocuments/documents/MPD/ProductDocuments/DataSheets/24AA02-24LC02B-24FC02-2Kbit-I2C-Serial-EEPROM-DS20001709.pdf',
 'data':'https://www.ti.com/lit/ds/symlink/sn74lvc8t245.pdf',
 'fm':'https://www.ti.com/lit/ds/symlink/sn74lvc125a.pdf',
 'clock':'https://www.ti.com/lit/ds/symlink/sn74lvc1t45.pdf',
 'ym':'https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf',
 'socket':'https://www.samtec.com/products/ssw-130-02-g-d',
 'header':'https://www.samtec.com/products/tsw-130-07-g-d'}

def part(ref,value,sheet,pins,footprint,source='',note=''):
 return dict(ref=ref,value=value,sheet=sheet,pins=[dict(num=str(n),name=a,net=b,type=c) for n,(a,b,c) in sorted(pins.items(),key=lambda kv:int(kv[0]) if str(kv[0]).isdigit() else 1000)],footprint=footprint,source=SOURCES.get(source,source),note=note)

def resistor(ref,value,a,b,sheet):
 return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Resistor_SMD:R_0805_2012Metric')

def capacitor(ref,value,a,b,sheet):
 return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Capacitor_SMD:C_0805_2012Metric')

def connector(board):
 spec=json.loads((HERE/'connector.json').read_text());pins={}
 for row in spec['pins']:
  n=row['pin'];net=row[board+'_net'];direction=row['direction'];typ='passive'
  # Types model an external source only for standalone-board ERC. Connectors do not generate signals.
  if net is not None:
   if direction in ('base_to_module_power','ground'):
    typ='power_out' if board=='module' and n in [1,2,5] else 'passive'
   elif direction=='bidirectional':typ='bidirectional'
   elif direction=='base_to_module':typ='output' if board=='module' else 'input'
   elif direction=='module_to_base':typ='input' if board=='module' else 'output'
  pins[n]=(row['signal'],net,typ)
 return part('JMOD','P2M 60pos / pin60 KEY','10-module-connector' if board=='base' else '01-connector',pins,
  'Connector_PinSocket_2.54mm:PinSocket_2x30_P2.54mm_Vertical' if board=='base' else 'Connector_PinHeader_2.54mm:PinHeader_2x30_P2.54mm_Vertical',
  'socket' if board=='base' else 'header','Base socket60 blocked; module pin60 removed. Match conductor numbers, not mirrored drawing columns. NO HOT PLUG.')

def pin(obj,n):return next(p for p in obj['pins'] if p['num']==str(n))

def make():
 reference=json.loads(REFERENCE.read_text());source=deepcopy(reference['parts'])
 moved={p['ref'] for p in source if p['sheet']=='04-ym-bus'}
 moved.update(['Q1','Q2','R19','R20','R21','R22','R23','U12','C19','C20','U14','C23','C24','R39','R40','U16','C27','RL0','RL1','RL2'])
 base=[p for p in source if p['ref'] not in moved];module=[p for p in source if p['ref'] in moved]
 for p in module:
  if p['sheet']=='04-ym-bus':p['sheet']='02-level-bus'
  elif p['sheet']=='03-default-stop':p['sheet']='03-default-reset'
  elif p['ref'] in ['RL0','RL1','RL2']:p['sheet']='05-ssg'
  else:p['sheet']='04-ym-fm-clock'
 m={p['ref']:p for p in module};b={p['ref']:p for p in base}
 # Correctly name real unused GPIO terminals rather than calling them physical NC pins.
 for n in range(9,17):pin(m['U12'],n).update(name='IOA'+str(16-n),type='bidirectional')
 for n in range(26,34):pin(m['U12'],n).update(name='IOB'+str(n-26),type='bidirectional')
 pin(m['U12'],17)['name']='AGND'
 for p in [m['U8'],m['U9']]:p['source']=SOURCES['data']
 m['U16']['source']=SOURCES['fm'];m['U14']['source']=SOURCES['clock'];m['U12']['source']=SOURCES['ym']
 # Clock source termination is on base;5V translation and final YM termination stay on module.
 pin(m['U14'],3)['net']='MOD_CLK0'
 pin(b['U13'],9)['net']='SI_CLK1';pin(b['U13'],6)['net']='SI_CLK2'
 for ref,src,dst in [('RCLK0','SI_YM','MOD_CLK0'),('RCLK1','SI_CLK1','MOD_CLK1'),('RCLK2','SI_CLK2','MOD_CLK2')]:base.append(resistor(ref,'33',src,dst,'05-clock-ym'))
 # Add source damping after3.3V buffers; no5V digital waveform crosses JMOD.
 for n,signal in [(3,'M_FM_SD'),(6,'M_FM_CLK'),(8,'M_FM_SH')]:
  raw='BUF_'+signal;pin(m['U16'],n)['net']=raw
  module.append(resistor('RS'+str(n),'33',raw,signal,'04-ym-fm-clock'))
 # 24LC02B A0..A2 are internally NC; it responds throughout0x50..0x57.
 module.append(part('UID','24LC02B-I/SN','06-module-id',{
  1:('NC_A0',None,'no_connect'),2:('NC_A1',None,'no_connect'),3:('NC_A2',None,'no_connect'),
  4:('VSS',G,'power_in'),5:('SDA','PANEL_SDA','bidirectional'),6:('SCL','PANEL_SCL','input'),
  7:('WP','ID_WP','input'),8:('VCC',V3,'power_in')},'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm','id','Canonical address0x50, aliases0x51..57 reserved. WP10k high; pullTPWP low only during stopped programming.'))
 module.extend([capacitor('CID','100n X7R 10V',V3,G,'06-module-id'),resistor('RWP','10k','ID_WP',V3,'06-module-id')])
 module.append(part('TPWP','ID WP service','06-module-id',{1:('WP','ID_WP','passive')},'TestPoint:TestPoint_Pad_D1.5mm','', 'Normally leave open. Never short power rails; pull WP low with an external open-drain programmer when stopped.'))
 # Stereo-ready base: keep legacy left net names and duplicate the analog signal path.
 # YM2203 firmware emits identical FM samples on L/R; future stereo formats need their own driver.
 b['R54']['value']='8.2k 1%'
 pin(b['U17'],7)['net']='DAC_R'
 for n,net in [(1,'VREF'),(2,'MIX_R'),(10,'MUTE_5V'),(15,'MUTED_R')]:pin(b['U19'],n)['net']=net
 pin(b['JPOT'],6)['net']='OUT_AC_R'
 base.append(part('U20','MCP6022-I/SN','07-analog',{
  1:('OUTA','MIX_R','output'),2:('INA-','SUM_R','input'),3:('INA+','VREF','input'),4:('VSS',G,'power_in'),
  5:('INB+','VREF','input'),6:('INB-','SPARE_FOLLOWER','input'),7:('OUTB','SPARE_FOLLOWER','output'),8:('VDD',V5,'power_in')},
  'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm','https://ww1.microchip.com/downloads/en/DeviceDoc/20001685E.pdf','Right-channel mixer. Unused amplifier configured asVREF follower; no floating inputs.'))
 base.append(capacitor('CU20','100n X7R 10V',V5,G,'07-analog'))
 base.extend([resistor('R53R','470','DAC_R','FM_FILTER_R','07-analog'),capacitor('C38R','2.2n C0G','FM_FILTER_R',G,'07-analog')])
 ac=deepcopy(b['CA3']);ac.update(ref='CA3R');ac['pins'][0]['net']='FM_FILTER_R';ac['pins'][1]['net']='FM_FILTER_R_AC';base.append(ac)
 base.append(resistor('RM3R','100k 1%','FM_FILTER_R_AC','SUM_R','07-analog'))
 for i,ch in enumerate('ABC'):base.append(resistor('RM'+str(i)+'R','100k 1%','SSG_'+ch+'_AC','SUM_R','07-analog'))
 base.extend([resistor('R54R','8.2k 1%','MIX_R','SUM_R','07-analog'),capacitor('C39R','47p C0G','MIX_R','SUM_R','07-analog')])
 ac=deepcopy(b['C41']);ac.update(ref='C41R');ac['pins'][0]['net']='MUTED_R';ac['pins'][1]['net']='OUT_AC_R';base.append(ac)
 base.append(resistor('R58R','100k','OUT_AC_R',G,'07-analog'))
 for side,summer in [('L','SUM_MONO'),('R','SUM_R')]:
  inp='AUX_ANALOG_'+side
  base.append(resistor('RAUXPD'+side,'100k',inp,G,'07-analog'))
  ac=deepcopy(b['CA3']);ac.update(ref='CAUX'+side);ac['pins'][0]['net']=inp;ac['pins'][1]['net']=inp+'_AC';base.append(ac)
  base.append(resistor('RMAUX'+side,'100k 1%',inp+'_AC',summer,'07-analog'))
 base.append(connector('base'));module.append(connector('module'))
 for p in base:
  if p['ref']=='MPGA':p['note']+=' Native pin allocation unchanged from reviewB; module ID firmware NOT IMPLEMENTED.'
 # Source audit is recorded rather than mutating historical reviewB or its pin manifest.
 common=dict(schema_version=1,revision='3.0 review A',date='2026-11-16',status='connected split schematic review; NOT FOR FABRICATION',reference='carrier-p2/pcb-review-b/schematic/circuit.json',reference_sha256=hashlib.sha256(REFERENCE.read_bytes()).hexdigest(),pins_manifest_sha256=hashlib.sha256(PINFILE.read_bytes()).hexdigest(),native_gpio_changed=False,firmware_implemented=False,hardware_accepted=False)
 return dict(base=dict(common,board='base',parts=base),module=dict(common,board='YM2203x1',parts=module))
