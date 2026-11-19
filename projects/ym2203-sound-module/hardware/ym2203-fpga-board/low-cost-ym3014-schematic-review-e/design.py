# SPDX-License-Identifier: MIT
"""YM3014B-F split-analog revision E; preserve saved C circuits and GPIO."""
from copy import deepcopy
from pathlib import Path
import json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
V3='V3V3';V5='V5_CARRIER';G='GND'
YAMAHA='https://bitsavers.trailing-edge.com/components/yamaha/YM3014B_199403.pdf'
MICROCHIP='https://www.microchip.com/content/dam/mchp/documents/MSLD/ProductDocuments/DataSheets/MCP6001-1R-1U-2-4-1-MHz-Low-Power-Op-Amp-DS20001733L.pdf'
def part(ref,value,sheet,pins,footprint='',source='',note=''):
 return dict(ref=ref,value=value,sheet=sheet,pins=[dict(num=str(n),name=name,net=net,type=t) for n,(name,net,t) in pins.items()],footprint=footprint,source=source,note=note)
def two(ref,value,a,b,sheet='06-fm-dac',footprint=None,source='',note=''):
 return part(ref,value,sheet,{1:('1',a,'passive'),2:('2',b,'passive')},footprint or ('Capacitor_SMD:C_0805_2012Metric' if ref.startswith('C') else 'Resistor_SMD:R_0805_2012Metric'),source,note)
def pin(p,n):return next(x for x in p['pins'] if x['num']==str(n))
def make():
 old=ROOT/'low-cost-schematic-review-c'
 result={b:deepcopy(json.loads((old/b/'circuit.json').read_text())) for b in ['base','module','panel']}
 for d in result.values():d.update(revision='LC-YM3014-schematic-E',status='connected_schematic_not_pcb_or_hardware_acceptance',firmware_implemented=False,pcb_created=False,hardware_accepted=False)
 m=result['module']['parts'];by={x['ref']:x for x in m}
 for ref in ['RSMIXA','RSMIXB','RSMIXC']:
  pin(by[ref],2)['net']='AUDIO_R';by[ref]['note']='SSG passive average -> G40 pin39 CH2;never mixed into FM on pin37.'
 pin(by['JMOD'],39)['net']='AUDIO_R'
 by['JMOD']['note']='G40 existing order;37 CH1=FM,39 CH2=SSG;31/33/34 I2S retained. Split-analog profile;not stereo panning.'
 by['U16']['note']='Retained 5V-to-3V3 FM diagnostic receive taps. Normal E playback uses YM3014 and ADC,not this digital stream. No GP16..18 remap.'
 by['ULINK1']['note']='I2S and SPI TX retained. In E split-analog profile GP27 LINK_TX_DISABLE stays HIGH;DSP mix ignores moduleI2S. Future profiles explicit only.'
 m.extend([
 part('UDAC','YM3014B-F 16SOP / supplied','06-fm-dac',{
  1:('VDD','V5_MODULE','power_in'),2:('TO_BUFF','DAC_TO_BUFF','output'),3:('NC',None,'no_connect'),
  4:('LOAD','DAC_LOAD','input'),5:('NC',None,'no_connect'),6:('NC',None,'no_connect'),7:('SD','DAC_SD','input'),8:('NC',None,'no_connect'),
  9:('NC',None,'no_connect'),10:('CLOCK','DAC_CLK','input'),11:('NC',None,'no_connect'),12:('VSS',G,'power_in'),13:('NC',None,'no_connect'),
  14:('RB','DAC_RB','output'),15:('NC',None,'no_connect'),16:('MP','DAC_MP','input')},
  'P2LC:YM3014BF_SOP16_5.3x10.2_P1.27mm',YAMAHA,'16SOP only,not DIP8. VDD5V, RB10u and follower toMP per Yamaha basic circuit. 10bit mantissa+3bit exponent. DACclock fromY_CLK,not master. Sample source stock/marking/dimensions toverify.'),
 part('UAF','MCP6002-E/P','06-fm-dac',{
  1:('OUT_A','DAC_MP','output'),2:('IN_A-','DAC_MP','input'),3:('IN_A+','DAC_RB','input'),4:('VSS',G,'power_in'),
  5:('IN_B+','DAC_TO_BUFF','input'),6:('IN_B-','FM_BUF','input'),7:('OUT_B','FM_BUF','output'),8:('VDD','V5_MODULE','power_in')},
  'Package_DIP:DIP-8_W7.62mm',MICROCHIP,'A=RB voltage follower -> MP; B=TO_BUFF voltage follower. 5V single supply,RRIO,unity stable;100ohm output isolation. No LM358/TL072 substitution without bias/swing check.'),
 two('RFMSD','33','Y_SD','DAC_SD'),two('RFMCLK','33','Y_CLK','DAC_CLK'),two('RFMSH','33','Y_SH','DAC_LOAD'),
 two('RFMOUT','100','FM_BUF','AUDIO_L',note='Output isolation outside opamp feedback. G40CH1DC biased;AC coupling already on base. Not a headphone driver.'),
 two('CFMDAC','100n X7R 10V','V5_MODULE',G,note='Close toUDAC1/12.'),
 two('COPAMP','100n X7R 10V','V5_MODULE',G,note='Within2mm ofUAF8/4.'),
 two('CRB','10u 50V polar','DAC_RB',G,footprint='Capacitor_THT:CP_Radial_D5.0mm_P2.00mm',source='https://akizukidenshi.com/catalog/g/g117897/',note='Positive pin1=RB,negative2=GND. Yamaha reference bypass10uF. D5xH11mm;RB not MP. No bulk C directly on follower output.'),
 two('CANABULK','10u X7R 10V','V5_MODULE',G,note='Local5Vbulk;existingbag spare covers onepiece. No series supply resistor thatviolates4.75V DACminimum.')])
 return result
