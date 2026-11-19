# SPDX-License-Identifier: MIT
from pathlib import Path
from copy import deepcopy
import json
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
V3='V3V3';V5='V5_CARRIER';G='GND'
def make():
 result={b:deepcopy(json.loads((ROOT/'low-cost-ym3014-schematic-review-e'/b/'circuit.json').read_text())) for b in ['base','module','panel']}
 for board,d in result.items():
  d.update(revision='LC-YM3014-PCB-F',date='2026-11-19',pcb_created=True,hardware_accepted=False,firmware_implemented=False,status='prototype_pcb_review_not_hardware_acceptance')
  for p in d['parts']:
   if p['ref']=='UBASE':p['footprint']='P2LC:Picossci2A_DirectSolder'
   if p['ref']=='USOURCE':p['footprint']='P2LC:Picossci2B_DirectSolder_DebugWire'
   if p['ref']=='JUSB':p['footprint']='P2LC:USB_B_Neltron_5075BR_04_WH'
   if p['ref'] in ['JEDIT','JUPLINK']:p['footprint']='P2LC:Grove_110990037_RA'
   if p['ref']=='JMOD':p['footprint']='P2LC:G40_Female_Top' if board=='base' else 'P2LC:G40_Male_Underside'
 return result
