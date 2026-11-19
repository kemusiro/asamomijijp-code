# SPDX-License-Identifier: MIT
from pathlib import Path
from copy import deepcopy
import json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
V3='V3V3';V5='V5_CARRIER';G='GND'
def make():
 result={b:deepcopy(json.loads((HERE/'inputs'/(b+'-f.json')).read_text())) for b in ['base','module','panel']}
 for board,d in result.items():
  d.update(revision='LC-YM3014-PCB-K',date='2026-11-20',hardware_accepted=False,firmware_implemented=False,status='prototype_akizuki_clock_module_pcb_review')
  if board=='base':
   d['parts']=[p for p in d['parts'] if p['ref']!='Y1']
   p=next(p for p in d['parts'] if p['ref']=='U13')
   p.update(value='AE-Si5351A-B (110679)',footprint='P2LC:AE_Si5351A_B_10x10mm',source='https://akizukidenshi.com/goodsaffix/AE-Si5351A.PDF',note='25MHz crystal included;I2C0x60;CL8pF required;module top view pins1..8;3V3 both VDD/VDDO;no GPIO change;2.54mm standoff direct solder')
   p['pins']=[dict(num=str(n),name=name,net=net,type=typ) for n,name,net,typ in [(1,'VDDO',V3,'power_in'),(2,'SCL','SERVICE_SCL','input'),(3,'SDA','SERVICE_SDA','bidirectional'),(4,'GND',G,'power_in'),(5,'CLK0','SI_YM','output'),(6,'CLK1','SI_CLK1','output'),(7,'CLK2','SI_CLK2','output'),(8,'VDD',V3,'power_in')]]
  if board=='module':
   for p in d['parts']:
    if p['ref'] in ['U16','ULINK0','ULINK1']:p['value']='SN74LV4T125QPWRQ1';p['source']='https://www.ti.com/lit/ds/symlink/sn74lv4t125-q1.pdf';p['note']+=' Procurement J Q1 substitute;PW14 pinout retained;static checks only.'
    if p['ref']=='UTXOR':p['value']='SN74LVC1G32DBVRE4';p['note']+=' Procurement J E4 lead finish/order option;DBV5 retained.'
 return result
