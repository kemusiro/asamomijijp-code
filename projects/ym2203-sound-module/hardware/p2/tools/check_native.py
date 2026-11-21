# SPDX-License-Identifier: MIT
"""Run with KiCad's Python; compare live pads to current local circuit contract."""
from pathlib import Path
import json,sys,subprocess,xml.etree.ElementTree as ET
import pcbnew as P
from geometry import geometry
ROOT=Path(__file__).resolve().parents[1]
names={'base':'p2-base-lc-t','module':'p2-ym2203-lc-t','panel':'p2-panel-lc-n'}
for b,name in names.items():
 d=ROOT/'cad'/b;parts={p['ref']:p for p in json.loads((d/'circuit.json').read_text())['parts']}
 board=P.LoadBoard(str(d/(name+'.kicad_pcb')));fps={p.GetReference():p for p in board.GetFootprints()}
 assert set(parts)=={n for n in fps if not (n.startswith('H') and n[1:].isdigit())}
 assert geometry(board)==json.loads((d/'electrical-geometry-before.json').read_text())
 for ref,part in parts.items():
  f=fps[ref];assert f.GetValue()==part['value'],(b,ref)
  assert str(f.GetFPID().GetLibNickname())+':'+str(f.GetFPID().GetLibItemName())==part['footprint'],(b,ref)
  actual={}
  for pad in f.Pads():
   if pad.GetNumber():actual.setdefault(pad.GetNumber(),set()).add(pad.GetNetname())
  expected_pins={p['num'] for p in part['pins']}
  mechanical={'MP'} if b=='panel' and ref in {'RV1','RV2','RV3','RV4'} else set()
  assert set(actual)-expected_pins<=mechanical and expected_pins<=set(actual),(b,ref)
  assert all(not pad.GetNetname() for pad in f.Pads() if pad.GetNumber() in mechanical),(b,ref,'mechanical tab connected')
  for pin in part['pins']:
   nets=actual[pin['num']]
   assert nets=={pin['net']} if pin['net'] is not None else len(nets)==1 and next(iter(nets)).startswith('unconnected-'),(b,ref,pin,nets)
 print('PASS native',b,'parts',len(parts),'layers',board.GetCopperLayerCount())
