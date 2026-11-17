# SPDX-License-Identifier: MIT
"""Review B power refinement; GPIO and external HOST wire protocol unchanged."""
import importlib.util
from pathlib import Path
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p2_review_a_design',HERE.parent/'design.py');a=importlib.util.module_from_spec(spec);spec.loader.exec_module(a)
V3,V5,G=a.V3,a.V5,a.G

def make(pin_manifest=None):
 d=a.make(pin_manifest or HERE.parent/'pins.json');p={r['ref']:r for r in d['parts']}
 # Dedicated low-noise 3V3 AUX for DAC and shield supply; never tie two regulator outputs.
 for ref in ['FB1','U17','C33','C35']:
  for pin in p[ref]['pins']:
   if pin['net']==V3:pin['net']='V3_AUX'
 for pin in p['JUNO_PWR']['pins']:
  if pin['num']=='4':pin['net']='V3_AUX'
 p['JUNO_PWR']['note']+=' 3V3 power from independent AUX LDO; IOREF remains PGA logic rail; shield3V3 limit100mA provisional.'
 def part(ref,value,pins,fp,note='',source=''):
  q=dict(ref=ref,value=value,sheet='02-power-usb',pins=[dict(num=str(n),name=t[0],net=t[1],type=t[2]) for n,t in pins.items()],footprint=fp,source=source,note=note);d['parts'].append(q)
 part('UAUX','TLV75533PDBVR',{1:('IN',V5,'power_in'),2:('GND',G,'power_in'),3:('EN',V5,'input'),4:('NC',None,'no_connect'),5:('OUT','V3_AUX','power_out')},'Package_TO_SOT_SMD:SOT-23-5','500mA rated; designed load145mA, shield3V3<=100mA; do NOT parallel with PGA regulator','https://www.ti.com/lit/ds/symlink/tlv755p.pdf')
 for ref,n in [('CAUXIN',V5),('CAUXOUT','V3_AUX')]:
  part(ref,'4.7u X7R 10V',{1:('1',n,'passive'),2:('2',G,'passive')},'Capacitor_SMD:C_0805_2012Metric','Effective capacitance>=1uF after DC bias and tolerance, adjacent to regulator')
 for ref,n in [('RI2SD','DAC_DIN'),('RI2SB','DAC_BCK'),('RI2SL','DAC_LRCK')]:
  part(ref,'100k',{1:('1',n,'passive'),2:('2',G,'passive')},'Resistor_SMD:R_0805_2012Metric','Default low while PGA IO rail is absent; DAC XSMT remains low')
 d.update(variant='P2 revision2.1 reviewB routed prototype',status='PCB verification candidate, no fabrication authorization or hardware acceptance')
 d['limits'] += ['AUX LDO supplies DAC and shield3V3; IOREF remains PGA3V3','47 native GPIO and HOST0x42/100kHz unchanged','PGA socket:64 individual0.64mm-square compatible receptacles; no four-strip housing collision']
 return d
