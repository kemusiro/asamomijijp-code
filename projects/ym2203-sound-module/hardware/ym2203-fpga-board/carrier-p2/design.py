# SPDX-License-Identifier: MIT
"""Authoritative P2 revision2.1 pin-level review design. Not fabrication release."""
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
V3='V3V3';V5='V5_CARRIER';G='GND'
PINS=ROOT/'pins.json'

def make(pin_manifest=None):
 d=json.loads((pin_manifest or PINS).read_text());parts=[]
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
 m={r['net']:r for r in d['gpio'] if r['net']}
 alias={'ym_a0':'M_YM_A0','ym_cs_n':'M_YM_CS_N','ym_wr_n':'M_YM_WR_N','ym_rd_n':'M_YM_RD_N','translator_dir':'M_DATA_DIR','translator_oe_n':'M_DATA_OE_N','fm_sd':'M_FM_SD','fm_clk':'M_FM_CLK','fm_sh':'M_FM_SH','i2s_data':'M_I2S_DIN','i2s_bclk':'M_I2S_BCK','i2s_lrck':'M_I2S_LRCK','si_sda':'PANEL_SDA','si_scl':'PANEL_SCL','host_sda':'HOST_SDA','host_scl':'HOST_SCL'}
 pins={}
 for r0 in d['gpio']:
  net=r0['net'];typ='bidirectional'
  if net and net.startswith('M_') and not net.startswith('M_D') and net not in ['M_FM_SD','M_FM_CLK','M_FM_SH','M_VBUS_SENSE']:typ='output'
  if net in ['M_DATA_DIR','M_DATA_OE_N','M_CTRL_OE_N','M_DAC_ALLOW']:typ='output'
  if net in ['M_FM_SD','M_FM_CLK','M_FM_SH','M_VBUS_SENSE']:typ='input'
  pins[r0['module_pad']]=('GP'+str(r0['gpio']),net,typ)
 fixed_names={'A3':'VBUS','A4':'3V3_EN','A5':'RUN','A6':'USB_DP','A7':'USB_DM','A8':'BOOTSEL','B4':'3V3_OUT','B5':'ADC_VREF','B6':'SWCLK','B7':'SWDIO'}
 for pad,net in d['module_fixed_pins'].items():
  typ='power_out' if pad=='B4' else 'power_in' if net in [G,V5] else 'input' if pad in ['A5','A8','B6'] else 'bidirectional' if net else 'no_connect'
  pins[pad]=(fixed_names.get(pad,'GND'),net,typ)
 part('MPGA','PGA2350 PIM722 SOCKET','01-module',dict(sorted(pins.items())), 'P2C:PGA2350_Socket_64', 'https://shop.pimoroni.com/products/pga2350','Top view A1 at upper left. GP47 B8 NC: PSRAM onboard. USB 27R4 ALREADY on module. ADC_VREF/3V3_EN NC.')
 hdr('JHOST',4,{1:G,2:'HOST_SDA',3:'HOST_SCL',4:G},'01-module','Existing OTHER Pico GP0 SDA / GP1 SCL; 100kHz / 0x42; NO supply pin')
 hdr('JSWD',3,{1:'SWDIO',2:G,3:'SWCLK'},'01-module','3.3V SWD probe; never power carrier through probe')
 for ref,net in [('SWRESET','RUN_N'),('SWBOOT','BOOTSEL_N')]:
  part(ref,'RESET' if ref=='SWRESET' else 'BOOTSEL','01-module',{1:('A',net,'passive'),2:('B',G,'passive')},'Button_Switch_THT:SW_PUSH_6mm_H4.3mm','', 'Two contact numbers; each has two duplicated physical pads in KiCad footprint')
 r('RRUN','10k',V3,'RUN_N','01-module');c('CRUN','1n C0G','RUN_N',G,'01-module')
 # Independent external supply. USB VBUS has no connection to either module VBUS or carrier 5V.
 hdr('JPOWER',2,{1:'EXT5_IN',2:G},'02-power-usb','Regulated external5V; 1.5A supply target; verify 4.95..5.05V at YM under load',{1:'power_out'})
 part('F1','PTC 1.1A hold','02-power-usb',{1:('IN','EXT5_IN','passive'),2:('OUT',V5,'passive')},'Fuse:Fuse_1812_4532Metric')
 c('C1','100u 10V',V5,G,'02-power-usb');c('C2','10u 10V',V3,G,'02-power-usb')
 usb={}
 for side in ['A','B']:
  for n in [1,4,5,6,7,8,9,12]:
   net=G if n in [1,12] else 'USB_VBUS_RAW' if n in [4,9] else 'USB_DP' if n==6 else 'USB_DM' if n==7 else 'CC'+('1' if side=='A' else '2') if n==5 else None
   usb[side+str(n)]=(side+str(n),net,'passive')
 usb['SH']=('SHIELD',G,'passive')
 part('JUSB','HRO TYPE-C-31-M-12 USB2 DEVICE','02-power-usb',usb,'Connector_USB:USB_C_Receptacle_HRO_TYPE-C-31-M-12','http://www.krhro.com/uploads/soft/180320/1-1P320120243.pdf','Self-powered. A6/B6 DP; A7/B7 DM; SBU NC. Verify exact purchased connector drawing before layout release.')
 for ref,n in [('RCC1','CC1'),('RCC2','CC2')]:r(ref,'5.1k 1%',n,G,'02-power-usb')
 part('UESD','USBLC6-2SC6','02-power-usb',{1:('IO1','USB_DP','passive'),2:('GND',G,'power_in'),3:('IO2','USB_DM','passive'),4:('IO2','USB_DM','passive'),5:('VBUS','USB_VBUS_RAW','passive'),6:('IO1','USB_DP','passive')},'Package_TO_SOT_SMD:SOT-23-6','https://www.st.com/resource/en/datasheet/usblc6-2.pdf','Place at USB connector, short return. VBUS protection/sense only; no external5V power path.')
 c('CVBUS','100n X7R 10V','USB_VBUS_RAW',G,'02-power-usb')
 r('RVB1','47k 0.1%','USB_VBUS_RAW','VBUS_DIV','02-power-usb');r('RVB2','68k 0.1%','VBUS_DIV',G,'02-power-usb');c('CVBD','100p C0G','VBUS_DIV',G,'02-power-usb')
 part('UVBUS','SN74LVC1G17DBVR','02-power-usb',{1:('NC',None,'no_connect'),2:('A','VBUS_DIV','input'),3:('GND',G,'power_in'),4:('Y','M_VBUS_SENSE','output'),5:('VCC',V3,'power_in')},'Package_TO_SOT_SMD:SOT-23-5','vbus','Schmitt buffer / Ioff; USB VBUS sense to GP46; no power through USB')
 dec('CVB3',V3,'02-power-usb');r('RVB3','100k','M_VBUS_SENSE',G,'02-power-usb')
 # Reset clamps persist when MCU is reset/unpowered. No watchdog/DFF/AND permit chain in supervised prototype.
 q('Q1','RESET_CLAMP_B','Y_RESET_N','03-default-stop');r('R19','4.7k',V5,'RESET_CLAMP_B','03-default-stop')
 q('Q2','RESET_REL_B','RESET_CLAMP_B','03-default-stop');r('R20','10k','M_RESET_RELEASE','RESET_REL_B','03-default-stop');r('R21','100k','RESET_REL_B',G,'03-default-stop');r('R22','10k',V5,'Y_RESET_N','03-default-stop');r('R23','100k','M_RESET_RELEASE',G,'03-default-stop')
 r('RPDAC','10k','M_DAC_ALLOW',G,'03-default-stop');r('RPLINE','10k','M_LINE_ALLOW',G,'03-default-stop')
 def trans(ref,oe,dir,aa,bb):
  pins={1:('VCCA',V3,'power_in'),2:('DIR',dir,'input'),11:('GND',G,'power_in'),12:('GND',G,'power_in'),13:('GND',G,'power_in'),22:('OEn',oe,'input'),23:('VCCB',V5,'power_in'),24:('VCCB',V5,'power_in')}
  for i in range(8):pins[3+i]=('A'+str(i+1),aa[i],'input' if dir==V3 else 'bidirectional');pins[21-i]=('B'+str(i+1),bb[i],'output' if dir==V3 else 'bidirectional')
  part(ref,'SN74LVC8T245PWR','04-ym-bus',dict(sorted(pins.items())),'Package_SO:TSSOP-24_4.4x7.8mm_P0.65mm','data','Bare IC pinout: OE=22 DIR=2; NOT the Rev C breakout numbering')
 trans('U8','M_DATA_OE_N',alias['translator_dir'],['M_D'+str(i) for i in range(8)],['Y_D'+str(i) for i in range(8)])
 trans('U9','M_CTRL_OE_N',V3,[alias[n] for n in ['ym_a0','ym_cs_n','ym_wr_n','ym_rd_n']]+[G]*4,['Y_A0','Y_CS_N','Y_WR_N','Y_RD_N']+[None]*4)
 for i,net in enumerate([V3,V5,V5,V3,V5,V5],11):dec('C'+str(i),net,'04-ym-bus')
 r('RDIR','10k','M_DATA_DIR',G,'04-ym-bus');r('RDOE','10k','M_DATA_OE_N',V3,'04-ym-bus');r('RCOE','10k','M_CTRL_OE_N',V3,'04-ym-bus')
 for i in range(8):r('RD'+str(i),'100k','Y_D'+str(i),G,'04-ym-bus')
 for i,n in enumerate(['CS_N','WR_N','RD_N'],32):r('R'+str(i),'10k','Y_'+n,V5,'04-ym-bus');r('RMC'+str(i),'10k','M_YM_'+n,V3,'04-ym-bus')
 r('R35','100k','Y_A0',G,'04-ym-bus');r('RMA','100k','M_YM_A0',G,'04-ym-bus')
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
 part('U13','Si5351A-B-GT','05-clock-ym',{1:('VDD',V3,'power_in'),2:('XA','XTAL_A','passive'),3:('XB','XTAL_B','passive'),4:('SCL',alias['si_scl'],'input'),5:('SDA',alias['si_sda'],'bidirectional'),6:('CLK2',None,'output'),7:('VDDO',V3,'power_in'),8:('GND',G,'power_in'),9:('CLK1',None,'output'),10:('CLK0','SI_YM','output')},'Package_SO:MSOP-10_3x3mm_P0.5mm','si','Blank no-boot preset; P2 firmware must disable CLK1/2 and configure CLK0 before reset release')
 part('Y1','25MHz CL10pF +/-20ppm','05-clock-ym',{1:('XA','XTAL_A','passive'),2:('GND',G,'passive'),3:('XB','XTAL_B','passive'),4:('GND',G,'passive')},'Crystal:Crystal_SMD_3225-4Pin_3.2x2.5mm','', 'ABM8-25.000MHZ-10-1-U-T candidate; ESR/drive and actual footprint need confirmation')
 dec('C21',V3,'05-clock-ym');dec('C22',V3,'05-clock-ym');r('R37','2.2k',alias['si_scl'],V3,'05-clock-ym');r('R38','2.2k',alias['si_sda'],V3,'05-clock-ym')
 part('U14','SN74LVC1T45DBVR','05-clock-ym',{1:('VCCA',V3,'power_in'),2:('GND',G,'power_in'),3:('A','SI_YM','input'),4:('B','YM_CLK_5','output'),5:('DIR',V3,'input'),6:('VCCB',V5,'power_in')},'Package_TO_SOT_SMD:SOT-23-6','clockshift','Fixed A->B; clock may run while YM RESET is asserted')
 dec('C23',V3,'05-clock-ym');dec('C24',V5,'05-clock-ym');r('R39','33','YM_CLK_5','Y_PHI_M','05-clock-ym');r('R40','100k','Y_PHI_M',G,'05-clock-ym')
 # Receive only, 5V-tolerant inputs; Ioff protects FPGA rail when power is absent.
 p={7:('GND',G,'power_in'),14:('VCC',V3,'power_in')}
 for oe,a,y,n in [(1,2,3,'sd'),(4,5,6,'clk'),(10,9,8,'sh')]:p[oe]=('OEn',G,'input');p[a]=('A','Y_'+n.upper(),'input');p[y]=('Y',alias['fm_'+n],'output')
 p[13]=('OEn',V3,'input');p[12]=('A',G,'input');p[11]=('Y',None,'output')
 part('U16','SN74LVC125APWR','06-dac',dict(sorted(p.items())),'Package_SO:TSSOP-14_4.4x5mm_P0.65mm','fm');dec('C27',V3,'06-dac')
 for i,name in enumerate(['sd','clk','sh'],42):r('R'+str(i),'100k',alias['fm_'+name],G,'06-dac')
 r('R45','2.2k',alias['host_scl'],V3,'06-dac');r('R46','2.2k',alias['host_sda'],V3,'06-dac')
 part('FB1','BLM21PG601SN1 / 600R@100MHz','06-dac',{1:('IN',V3,'passive'),2:('OUT','AV3V3','passive')},'Inductor_SMD:L_0805_2012Metric')
 p={1:('CPVDD','AV3V3','power_in'),2:('CAPP','CAPP','passive'),3:('CPGND',G,'power_in'),4:('CAPM','CAPM','passive'),5:('VNEG','VNEG','power_out'),6:('OUTL','DAC_L','output'),7:('OUTR',None,'output'),8:('AVDD','AV3V3','power_in'),9:('AGND',G,'power_in'),10:('DEMP',G,'input'),11:('FLT',G,'input'),12:('SCK',G,'input'),13:('BCK','DAC_BCK','input'),14:('DIN','DAC_DIN','input'),15:('LRCK','DAC_LRCK','input'),16:('FMT',G,'input'),17:('XSMT','M_DAC_ALLOW','input'),18:('LDOO','LDOO','power_out'),19:('DGND',G,'power_in'),20:('DVDD',V3,'power_in')}
 part('U17','PCM5102APWR','06-dac',p,'Package_SO:TSSOP-20_4.4x6.5mm_P0.65mm','dac','Left used, right intentionally unused as Rev C; mono analog output duplicated to L/R')
 for i,(a,b) in enumerate([('CAPP','CAPM'),('VNEG',G),('LDOO',G)],28):c('C'+str(i),'2.2u X7R 10V' if i!=30 else '1u X7R 10V',a,b,'06-dac')
 for i,n in enumerate(['AV3V3','AV3V3',V3],31):dec('C'+str(i),n,'06-dac')
 c('C34','10u 10V','AV3V3',G,'06-dac');c('C35','10u 10V',V3,G,'06-dac')
 for i,(src,dst) in enumerate([('i2s_bclk','DAC_BCK'),('i2s_lrck','DAC_LRCK'),('i2s_data','DAC_DIN')],47):r('R'+str(i),'33',alias[src],dst,'06-dac')
 r('R50','10k','M_DAC_ALLOW',G,'06-dac')
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
 dec('C40',V5,'07-analog');q('Q5','LINE_B','MUTE_5V','07-analog');r('R55','10k','M_LINE_ALLOW','LINE_B','07-analog');r('R56','100k','LINE_B',G,'07-analog');r('R57','10k',V5,'MUTE_5V','07-analog')
 c('C41','4.7u bipolar 10V','MUTED_MONO','OUT_AC','07-analog');r('R58','100k','OUT_AC',G,'07-analog')
 hdr('JPOT',6,{1:G,2:'VOL_L',3:'OUT_AC',4:G,5:'VOL_R',6:'OUT_AC'},'07-analog','Dual A10k offboard pot; CW=3/6, wipers 2/5, CCW=1/4')
 r('R59','100','VOL_L','LINE_L','07-analog');r('R60','100','VOL_R','LINE_R','07-analog');hdr('JLINE',3,{1:'LINE_L',2:G,3:'LINE_R'},'07-analog','Line output, not headphone driver')
 # Panel expander. Latest MCP23017 GPA7/GPB7 output-only restriction respected.
 mcp={9:('VDD',V3,'power_in'),10:('VSS',G,'power_in'),11:('NC',None,'no_connect'),12:('SCL','PANEL_SCL','input'),13:('SDA','PANEL_SDA','bidirectional'),14:('NC',None,'no_connect'),15:('A0',G,'input'),16:('A1',G,'input'),17:('A2',G,'input'),18:('RESETn','RUN_N','input'),19:('INTB',None,'open_collector'),20:('INTA',None,'open_collector')}
 a=['DIP1_N','DIP2_N','DIP3_N','DIP4_N','STOP_N','TEST_N',None,'RX_LED_N'];b=['FM1_LED_N','FM2_LED_N','FM3_LED_N','SSGA_LED_N','SSGB_LED_N','SSGC_LED_N',None,None]
 for i in range(8):
  mcp[21+i]=('GPA'+str(i),a[i],'output' if i==7 else 'bidirectional');mcp[1+i]=('GPB'+str(i),b[i],'output' if i==7 else 'bidirectional')
 part('UPANEL','MCP23017-E/SO','08-panel',dict(sorted(mcp.items())),'Package_SO:SOIC-28W_7.5x17.9mm_P1.27mm','https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-Data-Sheet-DS20001952.pdf','Address0x20. Poll10ms; no IRQ. GPA7 and GPB7 output-only. OLAT high BEFORE output direction; reset clears LEDs in firmware.')
 dec('CPANEL',V3,'08-panel')
 dp={}
 for i in range(4):dp[1+i]=('SW'+str(i+1),a[i],'passive');dp[8-i]=('GND',G,'passive')
 part('SWCLOCK','4-bit DIP ON=0 SW1=LSB','08-panel',dp,'Button_Switch_THT:SW_DIP_SPSTx04_Slide_6.7x11.72mm_W7.62mm_P2.54mm_LowProfile','', 'OFF/OFF/OFF/OFF=4MHz. Latched at reset only. Codes8..15 remain muted.')
 for i,n in enumerate(a[:6]):r('RP'+str(i),'10k',V3,n,'08-panel')
 for ref,n in [('SWSTOP','STOP_N'),('SWTEST','TEST_N')]:
  part(ref,'STOP' if ref=='SWSTOP' else 'TEST','08-panel',{1:('A',n,'passive'),2:('B',G,'passive')},'Button_Switch_THT:SW_PUSH_6mm_H4.3mm','', 'STOP global priority; TEST only when no owner; each debounced20ms')
 for i,n in enumerate([a[7]]+b[:6]):
  r('RLED'+str(i),'1k','LED_ANODE'+str(i),V3,'08-panel')
  part('DLED'+str(i),'RX GREEN' if i==0 else ['FM1','FM2','FM3','SSGA','SSGB','SSGC'][i-1],'08-panel',{1:('K',n,'passive'),2:('A','LED_ANODE'+str(i),'passive')},'LED_THT:LED_D3.0mm','', '<=2mA sink target; RX50ms / voice shadow20ms update; not VU')
 # UNO physical contact order matches official UNO-TH Rev3e; all signal voltages3.3V.
 groups={'JUNO_D0':[(i+1,'D'+str(i),'EXT_D'+str(i)) for i in range(8)],'JUNO_D8':[(i+1,'D'+str(i+8),'EXT_D'+str(i+8)) for i in range(6)]+[(7,'GND',G),(8,'AREF',None),(9,'SDA','EXT_A4'),(10,'SCL','EXT_A5')],'JUNO_A':[(i+1,'A'+str(i),'EXT_A'+str(i)) for i in range(6)],'JUNO_PWR':[(1,'NC',None),(2,'IOREF',V3),(3,'RESET','RUN_N'),(4,'3V3',V3),(5,'5V','SHIELD_5V'),(6,'GND',G),(7,'GND',G),(8,'VIN',None)],'JUNO_SPI':[(1,'CIPO','EXT_D12'),(2,'VCC_3V3',V3),(3,'SCK','EXT_D13'),(4,'COPI','EXT_D11'),(5,'RESET','RUN_N'),(6,'GND',G)]}
 for ref,seq in groups.items():part(ref,ref+' 3V3 ONLY','09-uno',{n:(label,net,'passive') for n,label,net in seq},'P2C:'+ref,'https://docs.arduino.cc/hardware/uno-rev3/','UNO geometry and role aliases; not universal5V shield / not AVR programmer. AREF and VIN NC.')
 # A4/A5 isolation is physical, not a firmware promise. Pullups on board side of jumpers.
 for ref,a,b in [('JP_SDA','EXT_A4','PANEL_SDA'),('JP_SCL','EXT_A5','PANEL_SCL')]:
  part(ref,'CLOSED I2C / OPEN ADC (STOPPED)','09-uno',{1:('MCU_HEADER',a,'passive'),2:('BOARD_I2C',b,'passive')},'Jumper:SolderJumper-2_P1.3mm_Bridged_RoundedPad1.0x1.5mm','', 'Normally closed. Opening isolates Si5351/panel AND board pullups; disable clock control/panel software; no sound allowed in ADC service mode.')
 part('JP5V','OPEN DEFAULT / SHIELD POWER','09-uno',{1:('5V',V5,'passive'),2:('SHIELD','SHIELD_5V','passive')},'Jumper:SolderJumper-2_P1.3mm_Open_RoundedPad1.0x1.5mm','', 'Fit only for3.3V-compatible shield using optional5V supply; never feed power back.')
 return {'schema_version':1,'variant':'P2 revision2.1 carrier reviewA','status':'connected schematic review + header placement fixture; NOT FOR FABRICATION','parts':parts,'port_aliases':alias,'pins_manifest':'pins.json','limits':['No routed PCB or electrical/EMC/USB acceptance','No P2 firmware port or variable-clock SRC implementation','300mA module3.3V regulator shared with MCU; measure total current before enabling shield load','STOP is software polled; internal watchdog only, no independent hardware stop guarantee']}
