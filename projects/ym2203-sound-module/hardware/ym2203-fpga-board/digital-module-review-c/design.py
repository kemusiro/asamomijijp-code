# SPDX-License-Identifier: MIT
"""Connected P2 digital-module review C; approved native GPIO proposal adopted.
Historical circuits are read-only inputs. This is not a firmware or PCB port.
"""
from pathlib import Path
from copy import deepcopy
import json,hashlib
HERE=Path(__file__).resolve().parent
V3='V3V3';V5='V5_CARRIER';G='GND'
ROOT=HERE.parent
SRC={
 'buf':'https://www.ti.com/lit/ds/symlink/sn74lv4t125.pdf',
 'and':'https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf',
 'schmitt':'https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf',
 'od':'https://www.ti.com/lit/ds/symlink/sn74lvc1g07.pdf',
 'adc':'https://www.ti.com/lit/ds/symlink/pcm1863.pdf',
 'ldo':'https://www.ti.com/lit/ds/symlink/tlv755p.pdf',
 'tmux':'https://www.ti.com/lit/ds/symlink/tmux1511.pdf',
 'clamp':'https://assets.nexperia.com/documents/data-sheet/BAT54S.pdf?215=',
 'core':'https://files.waveshare.com/wiki/Core2350B0/Core2350B.pdf'}

def part(ref,value,sheet,pins,footprint,source='',note=''):
 return dict(ref=ref,value=value,sheet=sheet,pins=[dict(num=str(n),name=a,net=b,type=c) for n,(a,b,c) in pins.items()],footprint=footprint,source=SRC.get(source,source),note=note)
def r(ref,value,a,b,sheet):return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Resistor_SMD:R_0805_2012Metric')
def c(ref,value,a,b,sheet):return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Capacitor_SMD:C_0805_2012Metric')
def ppin(p,n):return next(x for x in p['pins'] if x['num']==str(n))
def dec(parts,ref,rail,sheet):parts.append(c(ref,'100n X7R 10V',rail,G,sheet))
def gate(ref,value,a,b,out,rail,sheet,kind='and'):
 if kind=='and':pins={1:('A',a,'input'),2:('B',b,'input'),3:('GND',G,'power_in'),4:('Y',out,'output'),5:('VCC',rail,'power_in')}
 else:pins={1:('NC',None,'no_connect'),2:('A',a,'input'),3:('GND',G,'power_in'),4:('Y',out,'open_collector' if kind=='od' else 'output'),5:('VCC',rail,'power_in')}
 return part(ref,value,sheet,pins,'Package_TO_SOT_SMD:SOT-23-5',kind)
def buf4(ref,channels,rail,sheet):
 p={7:('GND',G,'power_in'),14:('VCC',rail,'power_in')}
 for k,(a,y,oe) in enumerate(channels):
  oe_n,a_n,y_n=[(1,2,3),(4,5,6),(10,9,8),(13,12,11)][k]
  p.update({oe_n:(f'{k+1}OE_N',oe,'input'),a_n:(f'{k+1}A',a,'input'),y_n:(f'{k+1}Y',y,'output')})
 return part(ref,'SN74LV4T125PWR',sheet,dict(sorted(p.items())),'Package_SO:TSSOP-14_4.4x5mm_P0.65mm','buf','Ioff receiver rail; input defaults explicit; unused gates disabled; NOT plainLVC125A')
def jmod(board):
 spec=json.loads((HERE/'connector.json').read_text());pins={}
 for x in spec['pins']:
  net=x[board+'_net'];typ='passive'
  if net and x['kind']=='digital':
   src=x['direction']=='module_to_base'
   typ=('output' if src else 'input') if board=='base' else ('input' if src else 'output')
   if x['signal']=='MOD_ALERT_N':typ='open_collector' if board=='base' else 'bidirectional'
  elif board=='module' and x['pin'] in (1,2):typ='power_out'
  pins[x['pin']]=(x['signal'],net,typ)
 return part('JMOD','P2 DIGITAL 32 / pin32 KEY','10-link' if board=='base' else '01-link',pins,
 'Connector_PinSocket_2.54mm:PinSocket_2x16_P2.54mm_Vertical' if board=='base' else 'Connector_PinHeader_2.54mm:PinHeader_2x16_P2.54mm_Vertical',
 'https://www.samtec.com/products/ssw-116-02-g-d' if board=='base' else 'https://www.samtec.com/products/tsw-116-07-g-d','Connector pin electrical types model external board sources for standalone ERC. No hotplug. Key removed/blocked; fit pending.')

def make():
 prior={b:json.loads((ROOT/'modular-review-a'/b/'circuit.json').read_text()) for b in ['base','module']}
 gpio=json.loads((HERE/'pins.json').read_text())
 base=deepcopy(prior['base']['parts']);module=deepcopy(prior['module']['parts'])
 drop={'JMOD','R42','R43','R44','CA0','CA1','CA2','RM0','RM1','RM2','RM0R','RM1R','RM2R','RAUXPDL','RAUXPDR','CAUXL','CAUXR','RMAUXL','RMAUXR'}
 base=[p for p in base if p['ref'] not in drop];b={p['ref']:p for p in base}
 mpga=b['MPGA'];old_pads={x['module_pad'] for x in gpio['base']}
 # All native pin choices are in the accepted proposal. Free old YM pins become NC.
 oldnet_to_pad={p['net']:p['num'] for p in mpga['pins'] if p['net'] is not None}
 new_by_pad={p['module_pad']:p for p in gpio['base']}
 old_native_pads=set(json.loads((HERE/'pins.json').read_text())['historical_native_pads'])
 for p in mpga['pins']:
  if p['num'] in old_native_pads:
   proposed=new_by_pad.get(p['num']);p['net']=proposed['net'] if proposed else None
   if proposed and proposed['gpio'] in [0,4,16]:p['type']='input'
   elif proposed and proposed['gpio'] in [1,2,3,34]:p['type']='output'
 mpga['note']='PGA2350 only on base; accepted reviewB GPIO adopted by user2026-11-16. FreeYM pins andPSRAM47NC. USB resistors already onboard. Firmware port pending.'
 b['F1']['value']='MF-MSMF150/16X-2 / hold1.5A@23C';b['F1']['source']='https://bourns.com/docs/product-datasheets/mf-msmf.pdf'
 b['JPOWER']['note']='Regulated5.1V class2A; verify4.75..5.25V atYM under load. USB VBUS is not a power source.'
 for ref in ['R54','R54R']:b[ref]['value']='47k 1%'
 b['U17']['note']='Stereo FINAL FM+SSG I2S. XSMT mutes all sources. AV3V3 input buffers isolate MCU and AUX rails.'
 # Branch base reset directly to local gates and module permit. No extra native GPIO.
 s='03-default-stop'
 for ref,a,out in [('UPERMIT','MOD_ENABLE','MODULE_PERMIT'),('UDACRUN','M_DAC_ALLOW','DAC_RUN_OK'),('ULINERUN','M_LINE_ALLOW','LINE_RUN_OK')]:
  base.append(gate(ref,'SN74LVC1G08DBVR',a,'RUN_N',out,V3,s));dec(base,'C'+ref,V3,s)
 ppin(b['R55'],1)['net']='LINE_RUN_OK'
 # Replace direct MCU DAC connections with receiver-domain Ioff buffers.
 for ref,a in [('R47','M_I2S_BCK'),('R48','M_I2S_LRCK'),('R49','M_I2S_DIN')]:ppin(b[ref],1)['net']='BUF_'+a
 base.append(buf4('UDACBUF',[(x,'BUF_'+x,G) for x in ['M_I2S_BCK','M_I2S_LRCK','M_I2S_DIN']]+[('DAC_RUN_OK','DAC_XSMT',G)],'V3_AUX','06-dac'));dec(base,'CUDACBUF','V3_AUX','06-dac')
 ppin(b['U17'],17)['net']='DAC_XSMT';ppin(b['R50'],1)['net']='DAC_XSMT'
 base.append(r('RDACIN','100k','DAC_RUN_OK',G,'06-dac'))
 # Link source termination; CLK1/2 route to connector but are unused on first module.
 for ref,sig in [('RCLK0','SOUND_CLK0'),('RCLK1','SOUND_CLK1'),('RCLK2','SOUND_CLK2')]:ppin(b[ref],2)['net']='L_'+sig
 s='10-link'
 for ref,src,dst in [('RLKSCK','MOD_SPI_SCK','L_MOD_SPI_SCK'),('RLKMOSI','MOD_SPI_MOSI','L_MOD_SPI_MOSI'),('RLKCS','MOD_SPI_CS_N','L_MOD_SPI_CS_N'),('RLKEN','MODULE_PERMIT','L_MOD_ENABLE'),('RLKBCK','M_I2S_BCK','L_MOD_I2S_BCK'),('RLKLR','M_I2S_LRCK','L_MOD_I2S_LRCK')]:base.append(r(ref,'33',src,dst,s))
 base.append(buf4('URXBUF',[('L_MOD_SPI_MISO','MOD_SPI_MISO','MOD_SPI_CS_N'),('L_MOD_I2S_DATA','MOD_I2S_DATA',G),(G,None,V3),(G,None,V3)],V3,s));dec(base,'CURXBUF',V3,s)
 for ref,net,value,other in [('RBCS','MOD_SPI_CS_N','10k',V3),('RBEN','MOD_ENABLE','10k',G),('RBI0','L_MOD_SPI_MISO','100k',G),('RBI1','L_MOD_I2S_DATA','100k',G),('RBMISO','MOD_SPI_MISO','100k',G),('RBSD','MOD_I2S_DATA','100k',G),('RBALERT','L_MOD_ALERT_N','10k',V3)]:base.append(r(ref,value,net,other,s))
 # Alert is an external open-drain line at3V3 (FT GP4); no pullup on module.
 # GPIO proposed name maps directly to link alert by a net alias resistor.
 base.append(r('RALERT','0','L_MOD_ALERT_N','MOD_ALERT_N',s));base.append(jmod('base'))
 # Module retains local YM/level translation. Remove EEPROM and old link.
 removed={'UID','CID','RWP','TPWP','JMOD'}
 module=[p for p in module if p['ref'] not in removed]
 rename={V3:'MCU_3V3',V5:'V5_MODULE','M_FM_SD':'YM_FM_SD','M_FM_CLK':'YM_FM_CLK','M_FM_SH':'YM_FM_SH','M_RESET_RELEASE':'YM_RESET_RELEASE','M_DATA_DIR':'YM_DATA_DIR','M_DATA_OE_N':'YM_DATA_OE_N','M_CTRL_OE_N':'YM_CTRL_OE_N','M_YM_A0':'YM_A0','M_YM_CS_N':'YM_CS_N','M_YM_WR_N':'YM_WR_N','M_YM_RD_N':'YM_RD_N','MOD_CLK0':'YM_CLOCK_3V3'}
 rename.update({f'M_D{i}':f'YM_D{i}' for i in range(8)})
 for p in module:
  for pin in p['pins']:pin['net']=rename.get(pin['net'],pin['net'])
 m={p['ref']:p for p in module};m['U16']['value']='SN74LV4T125PWR';m['U16']['source']=SRC['buf'];m['U16']['note']='Ioff5V YM receiver, local3V3. Third output isSH, not LRCK.'
 for ref in ['RS3','RS6','RS8']:ppin(m[ref],1)['net']=rename.get(ppin(m[ref],1)['net'],ppin(m[ref],1)['net'])
 # Three FM buffer output nets were named BUF_M_FM_* in reviewA; retain these local names.
 for i in range(3):m['RL'+str(i)]['value']='1.33k 1%'
 # Core2350B separate P1..P4 header identity, NOT PGA socket footprint.
 hdr=json.loads((HERE/'module-header.json').read_text())['headers'];by_gp={p['gpio']:p for p in gpio['module']}
 for name,positions in hdr.items():
  ps={}
  for n,identity in enumerate(positions,1):
   net=None;typ='bidirectional';label='GPIO'+str(identity) if isinstance(identity,int) else identity
   if isinstance(identity,int) and identity in by_gp:
    q=by_gp[identity];net=q['net'];fun=q['function'];typ='bidirectional'
    if fun in ('pio_input','spi1_rx','spi1_ss_n','spi1_sclk'):typ='input'
    elif fun=='pio_output' or fun=='spi1_tx' or fun=='sio':typ='output'
    # YM data bus must remain bidirectional for status reads.
    if identity in range(8):typ='bidirectional'
   elif identity=='GND':net=G;typ='power_in'
   elif identity=='VBUS':net='V5_MODULE';typ='power_in'
   elif identity=='3V3':net='MCU_3V3';typ='power_out'
   elif identity in ['RUN','BOOTSEL','SWD','SWCLK']:
    net={'RUN':'CORE_RUN_N','BOOTSEL':'CORE_BOOT_N','SWD':'CORE_SWD','SWCLK':'CORE_SWCLK'}[identity];typ='bidirectional' if identity=='SWD' else 'input'
   ps[n]=(label,net,typ)
  module.append(part('JCORE'+name[1:],'Core2350B0 '+name+' SOCKET','02-core',ps,'Connector_PinSocket_2.54mm:PinSocket_2x08_P2.54mm_Vertical','core','Manufacturer P1..P4 identity; physical coordinates/body mating not checked. Core module is separate assembly item.'))
 dec(module,'CCORE','MCU_3V3','02-core');module.append(c('CCOREB','4.7u X7R 10V','MCU_3V3',G,'02-core'))
 module.append(part('JSWD','Core SWD / VREF input only','02-core',{1:('VREF','MCU_3V3','passive'),2:('SWD','CORE_SWD','passive'),3:('SWCLK','CORE_SWCLK','passive'),4:('GND',G,'passive')},'Connector_PinHeader_2.54mm:PinHeader_1x04_P2.54mm_Vertical','', 'Probe VREF is sense only; carrier supplies power. Do not connect moduleUSB adapter VBUS simultaneously.'))
 for ref,net in [('SWCOREBOOT','CORE_BOOT_N'),('SWCORERESET','CORE_RUN_N')]:module.append(part(ref,ref,'02-core',{1:('A',net,'passive'),2:('B',G,'passive')},'Button_Switch_THT:SW_PUSH_6mm_H4.3mm'))
 # Independent module permit and RUN open drain (manual RESET cannot short a push-pull high).
 s='03-default-reset'
 module.append(gate('UENABLE','SN74LVC1G17DBVR','L_MOD_ENABLE',None,'MODULE_PERMIT_LOCAL','MCU_3V3',s,'schmitt'))
 module.append(gate('URUNOD','SN74LVC1G07DBVR','MODULE_PERMIT_LOCAL',None,'CORE_RUN_N','MCU_3V3',s,'od'))
 module.append(gate('UYMALLOW','SN74LVC1G08DBVR','MODULE_PERMIT_LOCAL','YM_RESET_RELEASE','YM_RELEASE_OK','MCU_3V3',s))
 for ref in ['UENABLE','URUNOD','UYMALLOW']:dec(module,'C'+ref,'MCU_3V3',s)
 module.extend([r('RENPD','10k','L_MOD_ENABLE',G,s),r('RRUNUP','10k','CORE_RUN_N','MCU_3V3',s),r('RADENPD','10k','MODULE_PERMIT_LOCAL',G,s)])
 module.append(gate('UYMRUN','SN74LVC1G08DBVR','YM_RELEASE_OK','CORE_RUN_N','YM_RELEASE_SAFE','MCU_3V3',s))
 dec(module,'CUYMRUN','MCU_3V3',s)
 module.append(r('RYMSAFEPD','100k','YM_RELEASE_SAFE',G,s))
 ppin(m['R20'],1)['net']='YM_RELEASE_SAFE'
 # Local reset default clamp remains powered by5V even if MCU3V3 is absent.
 # Ioff link receivers, with CS/SCK/MOSI defaults. First profile uses onlyCLK0.
 s='01-link'
 module.append(buf4('ULINK0',[('L_MOD_SPI_SCK','MOD_SPI_SCK',G),('L_MOD_SPI_MOSI','MOD_SPI_MOSI',G),('L_MOD_SPI_CS_N','MOD_SPI_CS_N',G),('L_SOUND_CLK0','YM_CLOCK_3V3',G)],'MCU_3V3',s))
 module.append(buf4('ULINK1',[('L_MOD_I2S_BCK','MOD_I2S_BCK',G),('L_MOD_I2S_LRCK','MOD_I2S_LRCK',G),(G,None,'MCU_3V3'),(G,None,'MCU_3V3')],'MCU_3V3',s))
 module.append(buf4('ULINKTX',[('MOD_SPI_MISO','LINK_TX_MISO','MOD_SPI_CS_N'),('MOD_I2S_DATA','LINK_TX_DATA',G),(G,None,'MCU_3V3'),(G,None,'MCU_3V3')],'MCU_3V3',s))
 for ref in ['ULINK0','ULINK1','ULINKTX']:dec(module,'C'+ref,'MCU_3V3',s)
 for ref,net,value,other in [('RMSCK','L_MOD_SPI_SCK','100k',G),('RMMOSI','L_MOD_SPI_MOSI','100k',G),('RMCS','L_MOD_SPI_CS_N','10k','MCU_3V3'),('RMBCK','L_MOD_I2S_BCK','100k',G),('RMLR','L_MOD_I2S_LRCK','100k',G),('RMCLK','L_SOUND_CLK0','100k',G),('RMSD','MOD_I2S_DATA','100k',G),('RMADR','MOD_ALERT_DRIVE','100k',G)]:module.append(r(ref,value,net,other,s))
 module.extend([r('RMTXMISO','33','LINK_TX_MISO','L_MOD_SPI_MISO',s),r('RMTXDATA','33','LINK_TX_DATA','L_MOD_I2S_DATA',s)])
 module.append(gate('UALERT','SN74LVC1G07DBVR','MOD_ALERT_DRIVE',None,'L_MOD_ALERT_N','MCU_3V3',s,'od'));dec(module,'CUALERT','MCU_3V3',s);module.append(jmod('module'))
 # ADC rail: switched withpermit; outputs never tied toMCU rail; permanent680R bleed.
 s='06-adc-power'
 module.append(part('UADCPOWER','TLV75533PDBVR',s,{1:('IN','V5_MODULE','power_in'),2:('GND',G,'power_in'),3:('EN','MODULE_PERMIT_LOCAL','input'),4:('NC',None,'no_connect'),5:('OUT','ADC_3V3','power_out')},'Package_TO_SOT_SMD:SOT-23-5','ldo','EN low onSTOP; active discharge plus680R bleed. Check effectiveC and measured decay.'))
 for ref,rail in [('CADCIN','V5_MODULE'),('CADCOUT','ADC_3V3')]:module.append(c(ref,'4.7u X7R 10V',rail,G,s))
 module.extend([r('RADCBLEED','680','ADC_3V3',G,s),c('CMOD5','22u X7R 10V','V5_MODULE',G,s)])
 # PCM1863 true pin map. LDO pin11 decouples internal1.8V only.
 s='07-adc'
 adcp={1:('VINL2','ADC_SSG_B','input'),2:('VINR2',None,'input'),3:('VINL1','ADC_SSG_A','input'),4:('VINR1',None,'input'),5:('MICBIAS',None,'power_out'),6:('VREF','ADC_VREF','power_out'),7:('AGND',G,'power_in'),8:('AVDD','ADC_3V3','power_in'),9:('XO',None,'output'),10:('XI',G,'input'),11:('LDO_1V8','ADC_LDO_1V8','power_out'),12:('DGND',G,'power_in'),13:('DVDD','ADC_3V3','power_in'),14:('IOVDD','ADC_3V3','power_in'),15:('SCKI',G,'input'),16:('LRCK','ADC_LRCK','input'),17:('BCK','ADC_BCK','input'),18:('DOUT','ADC_DOUT_RAW','output'),19:('GPIO3_INPUT_ARM','ADC_INPUT_ARM','bidirectional'),20:('GPIO2',None,'bidirectional'),21:('GPIO1_DMIN','ADC_DMIN_PD','bidirectional'),22:('GPIO0',None,'bidirectional'),23:('SDA','ADC_SDA','bidirectional'),24:('SCL','ADC_SCL','input'),25:('AD',G,'input'),26:('MD0_I2C',G,'input'),27:('VINL4',None,'input'),28:('VINR4',None,'input'),29:('VINL3','ADC_SSG_C','input'),30:('VINR3',None,'input')}
 module.append(part('UADC','PCM1863DBT',s,adcp,'Package_SO:TSSOP-30_4.4x7.8mm_P0.5mm','adc','8analog inputs but2ADCs; L SUM1+2+3, R muted. No external reset/brownout detector. Pins11/6 decoupling only. Unusedanalog inputs NC/muted.'))
 for name,rail in [('AV','ADC_3V3'),('DV','ADC_3V3'),('IO','ADC_3V3'),('LDO','ADC_LDO_1V8')]:
  module.append(c('CADC'+name+'0','100n X7R 10V',rail,G,s));module.append(c('CADC'+name+'1','10u X7R 10V',rail,G,s))
 module.append(r('RDMINPD','100k','ADC_DMIN_PD',G,s))
 module.append(c('CADCVREF','1u X7R 10V','ADC_VREF',G,s))
 for ref,net in [('RADCSDA','ADC_SDA'),('RADCSCL','ADC_SCL')]:module.append(r(ref,'4.7k',net,'ADC_3V3',s))
 module.append(buf4('UADCCLK',[('MOD_I2S_BCK','ADC_BCK',G),('MOD_I2S_LRCK','ADC_LRCK',G),(G,None,'ADC_3V3'),(G,None,'ADC_3V3')],'ADC_3V3',s));dec(module,'CUADCCLK','ADC_3V3',s)
 module.append(part('UADCDATA','SN74LVC1G125DBVR',s,{1:('OE_N',G,'input'),2:('A','ADC_DOUT_RAW','input'),3:('GND',G,'power_in'),4:('Y','ADC_DOUT','output'),5:('VCC','MCU_3V3','power_in')},'Package_TO_SOT_SMD:SOT-23-5','https://www.ti.com/lit/ds/symlink/sn74lvc1g125.pdf','Receiver powered byMCU3V3; Ioff prevents ADC rail feeding unpoweredMCU.'))
 dec(module,'CUADCDATA','MCU_3V3',s);module.append(r('RADCDATAPD','100k','ADC_DOUT',G,s))
 # Analog poweroff isolation BEFORE AC coupling keeps TMUX terminals nonnegative.
 s='08-ssg-adc-protection'
 module.append(gate('UINPUTAND','SN74LVC1G08DBVR','ADC_INPUT_ARM','YM_RELEASE_SAFE','ADC_INPUT_ENABLE','ADC_3V3',s));dec(module,'CUINPUTAND','ADC_3V3',s)
 module.extend([r('RADCARM','10k','ADC_INPUT_ARM',G,s),r('RMUXPD','10k','ADC_INPUT_ENABLE',G,s)])
 mux={1:('SEL1','ADC_INPUT_ENABLE','input'),2:('S1','SSG_DIV_A','passive'),3:('D1','SSG_ISO_A','passive'),4:('SEL2','ADC_INPUT_ENABLE','input'),5:('S2','SSG_DIV_B','passive'),6:('D2','SSG_ISO_B','passive'),7:('GND',G,'power_in'),8:('D3','SSG_ISO_C','passive'),9:('S3','SSG_DIV_C','passive'),10:('SEL3','ADC_INPUT_ENABLE','input'),11:('D4',None,'passive'),12:('S4',G,'passive'),13:('SEL4',G,'input'),14:('VDD','ADC_3V3','power_in')}
 module.append(part('UINPUT','TMUX1511PWR',s,mux,'Package_SO:TSSOP-14_4.4x5mm_P0.65mm','tmux','Powered-off protection0..3.6V; divider bound<1.34V. Before coupling caps; defaultOFF. ARM only afterADC init+local YM permit.'))
 dec(module,'CUINPUT','ADC_3V3',s)
 for i,ch in enumerate('ABC'):
  module.extend([r('RDIVT'+ch,'3.01k 1%','SSG_'+ch,'SSG_DIV_'+ch,s),r('RDIVB'+ch,'1k 1%','SSG_DIV_'+ch,G,s),r('RISOBLEED'+ch,'100k','SSG_ISO_'+ch,G,s),c('CAC'+ch,'2.2u X7R 10V','SSG_ISO_'+ch,'SSG_AC_'+ch,s),r('RADCLIMIT'+ch,'4.7k 1%','SSG_AC_'+ch,'ADC_SSG_'+ch,s),c('CAAF'+ch,'470p C0G','ADC_SSG_'+ch,G,s)])
  module.append(part('DCLAMP'+ch,'BAT54S,215',s,{1:('A1',G,'passive'),2:('K2','ADC_3V3','passive'),3:('K1_A2','ADC_SSG_'+ch,'passive')},'Package_TO_SOT_SMD:SOT-23','clamp','Lowerclamp GND->VIN; upper VIN->ADC3V3. Must be series BAT54S, not commonanode/cathode variants.'))
 # Test points are not additional control GPIO.
 for ref,net in [('TPM3','MCU_3V3'),('TPADC3','ADC_3V3'),('TPADCEN','MODULE_PERMIT_LOCAL'),('TPARM','ADC_INPUT_ENABLE'),('TPRESET','Y_RESET_N')]:module.append(part(ref,net,'09-test',{1:('TP',net,'passive')},'TestPoint:TestPoint_Pad_D1.5mm'))
 for side,parts in [('base',base),('module',module)]:
  assert len({p['ref'] for p in parts})==len(parts),'duplicate ref '+side
 common=dict(schema_version=1,revision='3.1 review C',date='2026-11-16',status='connected schematic review NOT FOR FABRICATION',gpio_approval='User adopted presented reviewB proposal2026-11-16; no extra MCU GPIO added',firmware_implemented=False,pcb_created=False,hardware_accepted=False)
 return {side:dict(common,board=side,parts=parts) for side,parts in [('base',base),('module',module)]}
