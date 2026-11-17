# SPDX-License-Identifier: MIT
"""Authoritative pin-level F1 carrier review design. Not fabrication release."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parent
SOURCES={
 'wd':'https://www.analog.com/media/en/technical-documentation/data-sheets/max6369-max6374.pdf',
 'sup':'https://www.ti.com/lit/ds/symlink/tps3808.pdf',
 'ff':'https://www.ti.com/lit/ds/symlink/sn74lvc74a.pdf',
 'and':'https://www.ti.com/lit/ds/symlink/sn74lvc08a.pdf',
 'data':'https://www.ti.com/lit/ds/symlink/sn74lvc8t245.pdf',
 'fm':'https://www.ti.com/lit/ds/symlink/sn74lvc125a.pdf',
 'clockbuf':'https://www.ti.com/lit/ds/symlink/cdclvc1102.pdf',
 'clockshift':'https://www.ti.com/lit/ds/symlink/sn74lvc1t45.pdf',
 'si':'https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/data-sheets/Si5351-B.pdf',
 'vbus':'https://www.ti.com/lit/ds/symlink/sn74lvc1g17.pdf',
 'ym':'https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf',
 'dac':'https://www.ti.com/lit/ds/symlink/pcm5102a.pdf',
 'mix':'https://ww1.microchip.com/downloads/en/DeviceDoc/20001685E.pdf',
 'mute':'https://www.ti.com/lit/ds/symlink/cd74hc4053.pdf',
 'xo':'https://abracon.com/Oscillators/ASV.pdf'}
V3='V3_ULX';V5='V5_CARRIER';G='GND'
PINS=Path(__file__).resolve().parents[3]/'fpga-standalone/boards/ulx3s/pins.json'

def make(pin_manifest=None):
 d=json.loads((pin_manifest or PINS).read_text());parts=[];idx={}
 def part(ref,value,sheet,pins,fp,source='',note=''):
  assert ref not in {p['ref'] for p in parts}
  p=dict(ref=ref,value=value,sheet=sheet,pins=[dict(num=str(n),name=v[0],net=v[1],type=v[2]) for n,v in pins.items()],footprint=fp,source=SOURCES.get(source,source),note=note);parts.append(p);return p
 def r(ref,value,a,b,sheet):return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},'Resistor_SMD:R_0805_2012Metric')
 def c(ref,value,a,b,sheet):
  fp='Capacitor_SMD:C_0805_2012Metric'
  if value.startswith('100u'):fp='Capacitor_THT:CP_Radial_D6.3mm_P2.50mm'
  if 'bipolar' in value:fp='Capacitor_THT:C_Radial_D5.0mm_H11.0mm_P2.00mm'
  return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},fp,'','Capacitor body/height and effective capacitance to be checked against final MPN')
 def dec(ref,net,sheet):c(ref,'100n X7R 10V',net,G,sheet)
 def hdr(ref,n,nets,sheet,note='',types=None):
  types=types or {};return part(ref,ref,sheet,{i:('P'+str(i),nets.get(i),types.get(i,'passive')) for i in range(1,n+1)},f'Connector_PinHeader_2.54mm:PinHeader_1x{n:02d}_P2.54mm_Vertical','',note)
 def q(ref,base,collector,sheet):part(ref,'MMBT3904LT1G',sheet,{1:('B',base,'input'),2:('E',G,'passive'),3:('C',collector,'open_collector')},'Package_TO_SOT_SMD:SOT-23','https://www.onsemi.com/pdf/datasheet/mmbt3904lt1-d.pdf')
 alias={p['port']:('F_D'+p['port'][8:-1] if p['port'].startswith('ym_data[') else 'F_'+p['port'].upper()) for p in d['pins']}
 # Complete physical mating headers. Male-vertical numbering, as pinned by board manifest.
 for name in ['J1','J2']:
  nets={};types={}
  for p in d['pins']:
   if p['connector'].startswith(name+'.'):
    num=int(p['connector'].split()[0].split('.')[1]);nets[num]=alias[p['port']];types[num]={'input':'input','output':'output','inout':'bidirectional'}[p['direction']]
  powers=([1,2,19,20,39,40] if name=='J1' else [1,2,19,20]);grounds=[3,4,21,22,37,38] if name=='J1' else [17,18,21,22,37,38]
  # J2.17/18 are GP21/GN21, not ground! Only actual rail pins are below.
  if name=='J2':grounds=[21,22,37,38];nets[40]=V5;types[40]='power_in'
  for n in powers:nets[n]=V3
  for n in grounds:nets[n]=G
  if name=='J2':types[1]='power_out'
  p=hdr('JULX'+name[-1],40,nets,'01-connectors','ULX3S 85F v3.0.8; vertical male numbering; D9/D52 OPEN, D51 diode mandatory',types)
  p['footprint']='Connector_PinSocket_2.54mm:PinSocket_2x20_P2.54mm_Vertical';p['value']='ULX3S '+name+' MATE'
 hdr('JOLED',7,{1:G,2:V3,3:'REF12'},'01-connectors','OLED1.3=P3 PLL reference. No OLED fitted.',{3:'input'})
 hdr('JHOST',4,{1:G,2:alias['host_sda'],3:alias['host_scl'],4:G},'01-connectors','Existing OTHER Pico: GP0 SDA, GP1 SCL; 100kHz; no supply pin')
 hdr('JVBUS',2,{1:'US2_VBUS_RAW',2:G},'01-connectors','Flying lead from US2 side of REMOVED D9; never MODULE_5V')
 hdr('JPOWER',2,{1:'EXT5_IN',2:G},'02-power','5V supply 1.5A; AFTER fuse V5_CARRIER must be 4.95..5.05V; never exceed 5.25V; verify drop/ripple', {1:'power_out'})
 part('F1','PTC 1.1A hold','02-power',{1:('IN','EXT5_IN','passive'),2:('OUT',V5,'passive')},'Fuse:Fuse_1812_4532Metric')
 c('C1','100u 10V',V5,G,'02-power');c('C2','10u 10V',V3,G,'02-power')
 # USB VBUS is sense-only, with power-off protected logic on the module 3.3V rail.
 r('R1','47k 0.1%','US2_VBUS_RAW','VBUS_DIV','02-power');r('R2','68k 0.1%','VBUS_DIV',G,'02-power');c('C3','100p C0G','VBUS_DIV',G,'02-power')
 part('U1','SN74LVC1G17DBVR','02-power',{1:('NC',None,'no_connect'),2:('A','VBUS_DIV','input'),3:('GND',G,'power_in'),4:('Y',alias['vbus_sense'],'output'),5:('VCC',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-5','vbus','5.5V-tolerant input, Ioff; not a power path')
 dec('C4',V3,'02-power');r('R3','100k',alias['vbus_sense'],G,'02-power')
 for ref,rail,top in [('U2',V5,'110k 0.1%'),('U3',V3,'66.5k 0.1%')]:
  sense='SENSE_'+ref
  part(ref,'TPS3808G01DBVR','02-power',{1:('RESETn','PGWD_N','open_collector'),2:('GND',G,'power_in'),3:('MRn',V3,'input'),4:('CT',None,'no_connect'),5:('SENSE',sense,'input'),6:('VDD',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-6','sup','CT intentionally open: fixed 20ms nominal release delay')
  r('R'+str(4+(ref=='U3')*2),top,rail,sense,'02-power');r('R'+str(5+(ref=='U3')*2),'10k 0.1%',sense,G,'02-power');dec('C'+str(5+(ref=='U3')),V3,'02-power')
 # Missing-pulse timer is independent of the FPGA clock and uses a hand-solderable SOT23-8.
 part('U4','MAX6369KA+T','03-safety',{1:('WDI',alias['heartbeat'],'input'),2:('GND',G,'power_in'),3:('NC',None,'no_connect'),4:('SET0',V3,'input'),5:('SET1',G,'input'),6:('SET2',G,'input'),7:('WDOn','PGWD_N','open_collector'),8:('VCC',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-8','wd','001: delay and timeout 10..30ms; WDO pulse 100..300ms')
 dec('C7',V3,'03-safety');r('R8','100k',alias['heartbeat'],G,'03-safety')
 hdr('JESTOP',2,{1:V3,2:'NC_RETURN'},'03-safety','Normally-closed external stop loop. Open/unplug inhibits. No automatic score restart.')
 r('R9','10k','NC_RETURN','PGWD_N','03-safety');r('R10','100k','PGWD_N',G,'03-safety')
 part('U5','SN74LVC74APWR','03-safety',{1:('CLR1n','PGWD_N','input'),2:('D1',V3,'input'),3:('CLK1',alias['heartbeat'],'input'),4:('PRE1n',V3,'input'),5:('Q1','HB_SEEN_META','output'),6:('Q1n',None,'output'),7:('GND',G,'power_in'),8:('Q2n',None,'output'),9:('Q2','HB_SEEN','output'),10:('PRE2n',V3,'input'),11:('CLK2',alias['heartbeat'],'input'),12:('D2','HB_SEEN_META','input'),13:('CLR2n','PGWD_N','input'),14:('VCC',V3,'power_in')},'Package_SO:TSSOP-14_4.4x5mm_P0.65mm','ff','Two heartbeat edges after PGWD release; a WDO pulse clears both stages')
 dec('C8',V3,'03-safety')
 part('U6','SN74LVC08APWR','03-safety',{1:('1A','PGWD_N','input'),2:('1B','HB_SEEN','input'),3:('1Y',alias['permit'],'output'),4:('2A',alias['permit'],'input'),5:('2B',alias['arm_request'],'input'),6:('2Y','RUN','output'),7:('GND',G,'power_in'),8:('3Y','DAC_RUN','output'),9:('3A','RUN','input'),10:('3B',alias['dac_allow'],'input'),11:('4Y','LINE_RUN','output'),12:('4A','RUN','input'),13:('4B',alias['line_allow'],'input'),14:('VCC',V3,'power_in')},'Package_SO:TSSOP-14_4.4x5mm_P0.65mm','and')
 dec('C9',V3,'03-safety')
 for i,net in enumerate([alias['permit'],alias['arm_request'],alias['dac_allow'],alias['line_allow'],'RUN','DAC_RUN','LINE_RUN',alias['ym_reset_n']],11):r('R'+str(i),'10k',net,G,'03-safety')
 part('U7','SN74LVC1G08DBVR','03-safety',{1:('A','RUN','input'),2:('B',alias['ym_reset_n'],'input'),3:('GND',G,'power_in'),4:('Y','RESET_OK','output'),5:('VCC',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-5','https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf')
 dec('C10',V3,'03-safety')
 # 5V-domain default clamp: no MCU/FPGA clock required to assert YM reset.
 q('Q1','RESET_CLAMP_B','Y_RESET_N','03-safety');r('R19','4.7k',V5,'RESET_CLAMP_B','03-safety')
 q('Q2','RESET_REL_B','RESET_CLAMP_B','03-safety');r('R20','10k','RESET_OK','RESET_REL_B','03-safety');r('R21','100k','RESET_REL_B',G,'03-safety');r('R22','10k',V5,'Y_RESET_N','03-safety');r('R23','100k','Y_RESET_N',G,'03-safety')
 # Separate data and fixed-direction control translators, referenced to module 3.3V.
 def trans(ref,oe,dir,aa,bb):
  pins={1:('VCCA',V3,'power_in'),2:('DIR',dir,'input'),11:('GND',G,'power_in'),12:('GND',G,'power_in'),13:('GND',G,'power_in'),22:('OEn',oe,'input'),23:('VCCB',V5,'power_in'),24:('VCCB',V5,'power_in')}
  for i in range(8):pins[3+i]=('A'+str(i+1),aa[i],'input' if dir==V3 else 'bidirectional');pins[21-i]=('B'+str(i+1),bb[i],'output' if dir==V3 else 'bidirectional')
  part(ref,'SN74LVC8T245PWR','04-ym-bus',dict(sorted(pins.items())),'Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm','data','Bare IC pinout: OE=22 DIR=2; NOT the Rev C breakout numbering')
 trans('U8','DATA_OE_N',alias['translator_dir'],['F_D'+str(i) for i in range(8)],['Y_D'+str(i) for i in range(8)])
 trans('U9','CTRL_OE_N',V3,[alias[n] for n in ['ym_a0','ym_cs_n','ym_wr_n','ym_rd_n']]+[G]*4,['Y_A0','Y_CS_N','Y_WR_N','Y_RD_N']+[None]*4)
 for i,net in enumerate([V3,V5,V5,V3,V5,V5],11):dec('C'+str(i),net,'04-ym-bus')
 part('U10','SN74LVC1G04DBVR','04-ym-bus',{1:('NC',None,'no_connect'),2:('A',alias['translator_oe_n'],'input'),3:('GND',G,'power_in'),4:('Y','DATA_OE_REQ','output'),5:('VCC',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-5','https://www.ti.com/lit/ds/symlink/sn74lvc1g04.pdf')
 part('U11','SN74LVC1G08DBVR','04-ym-bus',{1:('A','RUN','input'),2:('B','DATA_OE_REQ','input'),3:('GND',G,'power_in'),4:('Y','DATA_EN','output'),5:('VCC',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-5','https://www.ti.com/lit/ds/symlink/sn74lvc1g08.pdf')
 dec('C17',V3,'04-ym-bus');dec('C18',V3,'04-ym-bus')
 for ref,en,oe,base in [('Q3','DATA_EN','DATA_OE_N','DATA_EN_B'),('Q4','RUN','CTRL_OE_N','CTRL_EN_B')]:
  q(ref,base,oe,'04-ym-bus');r('R'+str(24+(ref=='Q4')*3),'10k',en,base,'04-ym-bus');r('R'+str(25+(ref=='Q4')*3),'100k',base,G,'04-ym-bus');r('R'+str(26+(ref=='Q4')*3),'10k',oe,V3,'04-ym-bus')
 r('R30','10k',alias['translator_dir'],G,'04-ym-bus');r('R31','10k',alias['translator_oe_n'],V3,'04-ym-bus')
 for i in range(8):r('RD'+str(i),'100k','Y_D'+str(i),G,'04-ym-bus');r('RA'+str(i),'100k','F_D'+str(i),G,'04-ym-bus')
 for i,n in enumerate(['CS_N','WR_N','RD_N'],32):r('R'+str(i),'10k','Y_'+n,V5,'04-ym-bus')
 r('R35','100k','Y_A0',G,'04-ym-bus')
 # YM2203C socket, pin numbers and mono mix preserved from Rev C.
 ym={i:('NC'+str(i),None,'no_connect') for i in range(1,41)}
 for pin in [1,17]:ym[pin]=('GND',G,'power_in')
 ym[21]=('VDD',V5,'power_in')
 for i,pin in enumerate([40,2,3,4,5,6,7,8]):ym[pin]=('D'+str(i),'Y_D'+str(i),'bidirectional')
 for pin,name in [(37,'A0'),(36,'RD_N'),(35,'WR_N'),(34,'CS_N'),(24,'RESET_N'),(38,'PHI_M')]:ym[pin]=(name,'Y_'+name,'input')
 for pin,name in [(23,'SD'),(39,'CLK'),(22,'SH')]:ym[pin]=(name,'Y_'+name,'output')
 ym[25]=('IRQn',None,'open_collector')
 for pin,n in [(20,'SSG_A'),(19,'SSG_B'),(18,'SSG_C')]:ym[pin]=(n,n,'output')
 part('U12','YM2203C SOCKET','05-clock-ym',ym,'Package_DIP:DIP-40_W15.24mm_Socket','ym','IO ports A/B unused; IRQ unconnected; 5V supply')
 dec('C19',V5,'05-clock-ym');c('C20','10u 10V',V5,G,'05-clock-ym')
 # Dedicated clock IC remains autonomous from USB/control reference.
 part('U13','Si5351A-B-GT','05-clock-ym',{1:('VDD',V3,'power_in'),2:('XA','XTAL_A','passive'),3:('XB','XTAL_B','passive'),4:('SCL',alias['si_scl'],'input'),5:('SDA',alias['si_sda'],'bidirectional'),6:('CLK2',None,'output'),7:('VDDO',V3,'power_in'),8:('GND',G,'power_in'),9:('CLK1','SI_AUDIO','output'),10:('CLK0','SI_YM','output')},'Package_SO:MSOP-10_3x3mm_P0.5mm','si','Blank no-boot preset; RTL programs 25MHz XTAL / internal 10pF load')
 part('Y1','25MHz CL10pF +/-20ppm','05-clock-ym',{1:('XA','XTAL_A','passive'),2:('GND',G,'passive'),3:('XB','XTAL_B','passive'),4:('GND',G,'passive')},'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm','', 'ABM8-25.000MHZ-10-1-U-T candidate; ESR/drive and actual footprint need confirmation')
 dec('C21',V3,'05-clock-ym');dec('C22',V3,'05-clock-ym');r('R36','33','SI_AUDIO',alias['audio49'],'05-clock-ym');r('R37','2.2k',alias['si_scl'],V3,'05-clock-ym');r('R38','2.2k',alias['si_sda'],V3,'05-clock-ym')
 part('U14','SN74LVC1T45DBVR','05-clock-ym',{1:('VCCA',V3,'power_in'),2:('GND',G,'power_in'),3:('A','SI_YM','input'),4:('B','YM_CLK_5','output'),5:('DIR',V3,'input'),6:('VCCB',V5,'power_in')},'Package_TO_SOT_SMD:SOT-23-6','clockshift','Fixed A->B; clock may run while YM RESET is asserted')
 dec('C23',V3,'05-clock-ym');dec('C24',V5,'05-clock-ym');r('R39','33','YM_CLK_5','Y_PHI_M','05-clock-ym');r('R40','100k','Y_PHI_M',G,'05-clock-ym')
 part('X1','ASV-12.000MHZ-EJ-T','05-clock-ym',{1:('STANDBYn',V3,'input'),2:('GND',G,'power_in'),3:('OUT','XO12','output'),4:('VDD',V3,'power_in')},'Oscillator:Oscillator_SMD_Abracon_ASV-4Pin_7.0x5.1mm_HandSoldering','xo','Package must be checked against exact ASV variant; buffer below provides fast edge')
 # ASV is 7x5mm, not the smaller ASV2 footprint.
 part('U15','CDCLVC1102PWR','05-clock-ym',{1:('CLKIN','XO12','input'),2:('1G',V3,'input'),3:('Y0','REF12_BUF','output'),4:('GND',G,'power_in'),5:('NC',None,'no_connect'),6:('VDD',V3,'power_in'),7:('NC',None,'no_connect'),8:('Y1',None,'output')},'Package_SO:TSSOP-8_3x3mm_P0.65mm','clockbuf','0.8ns max 20-80% edge at documented load; 10-90% P3 edge remains measurement gate')
 dec('C25',V3,'05-clock-ym');dec('C26',V3,'05-clock-ym');r('R41','22','REF12_BUF','REF12','05-clock-ym')
 # Receive only, 5V-tolerant inputs; Ioff protects FPGA rail when power is absent.
 p={7:('GND',G,'power_in'),14:('VCC',V3,'power_in')}
 for oe,a,y,n in [(1,2,3,'sd'),(4,5,6,'clk'),(10,9,8,'sh')]:p[oe]=('OEn',G,'input');p[a]=('A','Y_'+n.upper(),'input');p[y]=('Y',alias['fm_'+n],'output')
 p[13]=('OEn',V3,'input');p[12]=('A',G,'input');p[11]=('Y',None,'output')
 part('U16','SN74LVC125APWR','06-dac',dict(sorted(p.items())),'Package_SO:TSSOP-14_4.4x5mm_P0.65mm','fm');dec('C27',V3,'06-dac')
 for i,name in enumerate(['sd','clk','sh'],42):r('R'+str(i),'100k',alias['fm_'+name],G,'06-dac')
 r('R45','2.2k',alias['host_scl'],V3,'06-dac');r('R46','2.2k',alias['host_sda'],V3,'06-dac')
 part('FB1','BLM21PG601SN1 / 600R@100MHz','06-dac',{1:('IN',V3,'passive'),2:('OUT','AV3V3','passive')},'Inductor_SMD:L_0805_2012Metric')
 p={1:('CPVDD','AV3V3','power_in'),2:('CAPP','CAPP','passive'),3:('CPGND',G,'power_in'),4:('CAPM','CAPM','passive'),5:('VNEG','VNEG','power_out'),6:('OUTL','DAC_L','output'),7:('OUTR',None,'output'),8:('AVDD','AV3V3','power_in'),9:('AGND',G,'power_in'),10:('DEMP',G,'input'),11:('FLT',G,'input'),12:('SCK',G,'input'),13:('BCK','DAC_BCK','input'),14:('DIN','DAC_DIN','input'),15:('LRCK','DAC_LRCK','input'),16:('FMT',G,'input'),17:('XSMT','DAC_RUN','input'),18:('LDOO','LDOO','power_out'),19:('DGND',G,'power_in'),20:('DVDD',V3,'power_in')}
 part('U17','PCM5102APWR','06-dac',p,'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm','dac','Left used, right intentionally unused as Rev C; mono analog output duplicated to L/R')
 for i,(a,b) in enumerate([('CAPP','CAPM'),('VNEG',G),('LDOO',G)],28):c('C'+str(i),'2.2u X7R 10V' if i!=30 else '1u X7R 10V',a,b,'06-dac')
 for i,n in enumerate(['AV3V3','AV3V3',V3],31):dec('C'+str(i),n,'06-dac')
 c('C34','10u 10V','AV3V3',G,'06-dac');c('C35','10u 10V',V3,G,'06-dac')
 for i,(src,dst) in enumerate([('i2s_bclk','DAC_BCK'),('i2s_lrck','DAC_LRCK'),('i2s_data','DAC_DIN')],47):r('R'+str(i),'33',alias[src],dst,'06-dac')
 r('R50','10k','DAC_RUN',G,'06-dac')
 # Rev C analog gain/load baseline, kept to preserve accepted FM/SSG balance.
 part('U18','MCP6022-I/SN','07-analog',{1:('OUTA','VREF','output'),2:('INA-','VREF','input'),3:('INA+','REF_RAW','input'),4:('VSS',G,'power_in'),5:('INB+','VREF','input'),6:('INB-','SUM_MONO','input'),7:('OUTB','MIX_MONO','output'),8:('VDD',V5,'power_in')},'Package_SO:SOIC-8_3.9x4.9mm_P1.27mm','mix')
 dec('C36',V5,'07-analog');r('R51','10k 1%',V5,'REF_RAW','07-analog');r('R52','10k 1%','REF_RAW',G,'07-analog');c('C37','10u 10V','REF_RAW',G,'07-analog')
 r('R53','470','DAC_L','FM_FILTER','07-analog');c('C38','2.2n C0G','FM_FILTER',G,'07-analog')
 for i,s in enumerate(['SSG_A','SSG_B','SSG_C','FM_FILTER']):
  c('CA'+str(i),'4.7u bipolar 10V',s,s+'_AC','07-analog');r('RM'+str(i),'100k 1%',s+'_AC','SUM_MONO','07-analog')
  if i<3:r('RL'+str(i),'1k 1%',s,G,'07-analog')
 r('R54','22k 1%','MIX_MONO','SUM_MONO','07-analog');c('C39','47p C0G','MIX_MONO','SUM_MONO','07-analog')
 p={1:('Y1',G,'passive'),2:('Y0',G,'passive'),3:('Z1',G,'passive'),4:('Z',None,'passive'),5:('Z0',G,'passive'),6:('INH',G,'input'),7:('VEE',G,'power_in'),8:('GND',G,'power_in'),9:('C',G,'input'),10:('B',G,'input'),11:('A','MUTE_5V','input'),12:('X0','MIX_MONO','passive'),13:('X1','VREF','passive'),14:('X','MUTED_MONO','passive'),15:('Y',None,'passive'),16:('VCC',V5,'power_in')}
 part('U19','CD74HC4053M','07-analog',p,'Package_SO:SOIC-16_3.9x9.9mm_P1.27mm','mute','Default A=HIGH selects VREF; active LINE_RUN transistor selects audio')
 dec('C40',V5,'07-analog');q('Q5','LINE_B','MUTE_5V','07-analog');r('R55','10k','LINE_RUN','LINE_B','07-analog');r('R56','100k','LINE_B',G,'07-analog');r('R57','10k',V5,'MUTE_5V','07-analog')
 c('C41','4.7u bipolar 10V','MUTED_MONO','OUT_AC','07-analog');r('R58','100k','OUT_AC',G,'07-analog')
 hdr('JPOT',6,{1:G,2:'VOL_L',3:'OUT_AC',4:G,5:'VOL_R',6:'OUT_AC'},'07-analog','Dual A10k offboard pot; CW=3/6, wipers 2/5, CCW=1/4')
 r('R59','100','VOL_L','LINE_L','07-analog');r('R60','100','VOL_R','LINE_R','07-analog');hdr('JLINE',3,{1:'LINE_L',2:G,3:'LINE_R'},'07-analog','Line output, not headphone driver')
 return {'schema_version':1,'variant':'F1 ULX3S carrier review A','status':'schematic review; no PCB/fabrication release','parts':parts,'port_aliases':alias,'module_modifications':{'D8':'verified Schottky US1->module 5V; no zero-ohm link','D9':'REMOVE / OPEN; US2 VBUS sense-only','D51':'cut bridge, fit STPS2L30AF: J2.40 IN5V -> module internal 5V','D52':'REMOVE / OPEN; J2.39 unused'},'limits':['No PCB geometry or manufactured board; module voltage/population/continuity must be inspected','Clock edge at P3 and USB analog behavior require bench measurements','Power logic model is not transistor SPICE, PVT or metastability signoff']}
