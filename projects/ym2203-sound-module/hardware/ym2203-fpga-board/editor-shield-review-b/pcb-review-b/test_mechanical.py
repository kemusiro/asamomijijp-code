# SPDX-License-Identifier: MIT
"""Native CAD defect injection: reject a hidden lead, a tall part and a reopened window."""
import copy,json,unittest,os
from pathlib import Path
import pcbnew as P
from mechanical import inspect
H=Path(__file__).resolve().parent
BASE=Path(os.environ.get('P2_BASE_REFERENCE',str(H.parent.parent/'clean-sheet-pcb-review-i/base/p2-base-i.kicad_pcb')))
class NativeMechanicalTests(unittest.TestCase):
 def setUp(self):
  self.board=P.LoadBoard(str(H/'p2-editor-b.kicad_pcb'));self.base=P.LoadBoard(str(BASE));self.inp=json.loads((H/'mechanical-inputs.json').read_text())
 def test_original_rectangular_stack(self):
  r=inspect(self.board,self.base,self.inp);self.assertEqual(r['large_openings'],0);self.assertEqual(len(r['covered_controls']),3)
 def test_lead_moved_under_dip_is_rejected(self):
  rv=next(f for f in self.board.GetFootprints() if f.GetReference()=='RV1');p=next(p for p in rv.Pads() if p.GetNumber()=='1');p.SetPosition(P.VECTOR2I(P.FromMM(67),P.FromMM(80)))
  with self.assertRaisesRegex(AssertionError,'lead over covered SWCLOCK'):inspect(self.board,self.base,self.inp)
 def test_unapproved_tall_control_is_rejected(self):
  self.inp['covered_control_height_limit_mm']=9.5
  with self.assertRaisesRegex(AssertionError,'Z clearance'):inspect(self.board,self.base,self.inp)
 def test_extra_cut_edge_is_rejected(self):
  s=P.PCB_SHAPE();s.SetShape(P.SHAPE_T_SEGMENT);s.SetStart(P.VECTOR2I(P.FromMM(60),P.FromMM(71)));s.SetEnd(P.VECTOR2I(P.FromMM(78),P.FromMM(71)));s.SetLayer(P.Edge_Cuts);self.board.Add(s)
  with self.assertRaisesRegex(AssertionError,'four straight outer edges'):inspect(self.board,self.base,self.inp)
if __name__=='__main__':unittest.main()
