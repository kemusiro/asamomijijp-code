#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Native-coordinate/copper regressions for the enlarged carrier; no bench claim."""
import argparse,unittest
from pathlib import Path
import pcbnew as P
from stack_checks import inspect,CONTROL_NETS
H=Path(__file__).resolve().parent
HW=H.parent
class StackTests(unittest.TestCase):
 def setUp(self):
  self.base=P.LoadBoard(str(H/'base/p2-base-j.kicad_pcb'))
  self.source=P.LoadBoard(str(H/'module/p2-ym2203-i.kicad_pcb'))
  self.by={f.GetReference():f for f in self.base.GetFootprints()}
 def inspect(self):return inspect(self.base,self.source,HW,H)
 def test_current_stack(self):
  d=self.inspect();self.assertEqual(d['contracts']['shield_mates'],32)
 def test_old_stop_location_rejected(self):
  self.by['SWSTOP'].SetPosition(P.VECTOR2I(P.FromMM(13),P.FromMM(84)))
  with self.assertRaisesRegex(AssertionError,'stacked board'):self.inspect()
 def test_wrong_control_net_rejected(self):
  p=next(p for p in self.by['SWTEST'].Pads() if p.GetNumber()=='1')
  p.SetNetCode(self.base.FindNet('STOP_N').GetNetCode())
  with self.assertRaisesRegex(AssertionError,'electrical'):self.inspect()
 def test_source_connector_offset_rejected(self):
  f=self.by['JMOD'];f.SetPosition(f.GetPosition()+P.VECTOR2I(P.FromMM(.5),0))
  with self.assertRaisesRegex(AssertionError,'placement'):self.inspect()
 def test_unrelated_usb_route_edit_rejected(self):
  t=next(t for t in self.base.GetTracks() if not isinstance(t,P.PCB_VIA) and t.GetNetname() in ['USB_DP','USB_DM'])
  t.SetWidth(t.GetWidth()+P.FromMM(.01))
  with self.assertRaisesRegex(AssertionError,'copper'):self.inspect()
 def test_control_backside_rejected(self):
  self.by['SWCLOCK'].Flip(self.by['SWCLOCK'].GetPosition(),True)
  with self.assertRaisesRegex(AssertionError,'placement'):self.inspect()
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--hardware-root',type=Path,default=HW);args=a.parse_args();HW=args.hardware_root;unittest.main(argv=['test_stack.py'])
