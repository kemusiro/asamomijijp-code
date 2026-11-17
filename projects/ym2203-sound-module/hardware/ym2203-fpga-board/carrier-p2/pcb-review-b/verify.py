#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Compare routed board, independently exported netlist, and immutable P2 pin contract.
Run with KiCad Python after native ERC/DRC. Does not claim bench acceptance.
"""
import hashlib,json,math,sys,xml.etree.ElementTree as E
from pathlib import Path
import pcbnew as P
HERE=Path(__file__).resolve().parent; O=HERE/'schematic'
sys.path.insert(0,str(HERE));from design_b import make

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def check(write_report=True):
 b=P.LoadBoard(str(O/'p2-carrier-b.kicad_pcb'));d=make();parts={p['ref']:p for p in d['parts']};fps={f.GetReference():f for f in b.GetFootprints()}
 assert len(parts)==164 and len(fps)==172
 expected={}
 for ref,c in parts.items():
  pp={p['num']:p['net'] or '' for p in c['pins']};actual={p.GetNumber():('' if p.GetNetname().startswith('unconnected-') else p.GetNetname()) for p in fps[ref].Pads() if p.GetNumber()};assert pp==actual,(ref,pp,actual)
  for n,net in pp.items():
   if net:expected[ref,n]=net
 xml={}
 for net in E.parse(O/'netlist.xml').findall('.//nets/net'):
  for pin in net.findall('node'):xml[pin.get('ref'),pin.get('pin')]=net.get('name')
 # KiCad names unconnected pins separately. Compare connected electrical pins only.
 assert all(xml.get(k)==v for k,v in expected.items())
 places=json.loads((O/'placement-refs.json').read_text())
 for ref,place in places.items():
  f=fps[ref]
  assert abs(P.ToMM(f.GetPosition().x)-place['x_mm'])<1e-5 and abs(P.ToMM(f.GetPosition().y)-place['y_mm'])<1e-5
  assert abs(f.GetOrientationDegrees()-place['rotation_deg'])<1e-5
 envelopes=list(json.loads((O/'body-clearances.json').read_text())['bounds'].items())
 for i,(name,a) in enumerate(envelopes):
  for other,c in envelopes[i+1:]:
   assert not (a[0]<c[2]+.249 and a[2]+.249>c[0] and a[1]<c[3]+.249 and a[3]+.249>c[1]),(name,other)
 pins=json.loads((HERE.parent/'pins.json').read_text())
 mp={p.GetNumber():('' if p.GetNetname().startswith('unconnected-') else p.GetNetname()) for p in fps['MPGA'].Pads()}
 assert all(mp[r['module_pad']]==(r['net'] or '') for r in pins['gpio'])
 assert len([r for r in pins['gpio'] if r['net']])==47
 assert mp['B8']==''
 geo=json.loads((HERE.parent/'header-geometry.json').read_text())['derived_board_header_facts']
 for r in geo:
  pad=next(p for p in fps[r['ref']].Pads() if p.GetNumber()==str(r['pin']))
  assert abs(P.ToMM(pad.GetPosition().x)-10-r['x_mm'])<1e-5 and abs(P.ToMM(pad.GetPosition().y)-10-r['y_mm'])<1e-5
 assert b.GetCopperLayerCount()==4
 assert not any(t.GetLayer()==P.In1_Cu for t in b.GetTracks() if not isinstance(t,P.PCB_VIA))
 assert any(z.GetLayer()==P.In1_Cu and z.GetNetname()=='GND' and z.IsFilled() for z in b.Zones())
 assert abs(P.ToMM(b.GetBoardEdgesBoundingBox().GetWidth())-164.1)<1e-5 and abs(P.ToMM(b.GetBoardEdgesBoundingBox().GetHeight())-124.1)<1e-5 # includes0.1mm edge stroke
 # Assembly-sensitive exception: one tented0.45/0.20mm via, away from the U8 solder pad.
 small=[t for t in b.GetTracks() if isinstance(t,P.PCB_VIA) and t.GetDrillValue()==P.FromMM(.2)]
 assert len(small)==1 and small[0].GetWidth(P.F_Cu)==P.FromMM(.45)
 assert small[0].IsTented(P.F_Cu) and small[0].IsTented(P.B_Cu)
 pp={p.GetNumber():p for p in fps['C19'].Pads()};ym={p.GetNumber():p for p in fps['U12'].Pads()}
 assert math.hypot(P.ToMM(pp['1'].GetPosition().x-ym['21'].GetPosition().x),P.ToMM(pp['1'].GetPosition().y-ym['21'].GetPosition().y))<3
 for net in ['M_FM_SD','M_FM_CLK','M_FM_SH']:
  assert sum(P.ToMM(t.GetLength()) for t in b.GetTracks() if not isinstance(t,P.PCB_VIA) and t.GetNetname()==net)<70
 erc=json.loads((O/'erc.json').read_text());assert not any(s.get('violations') for s in erc['sheets'])
 drc=json.loads((O/'drc.json').read_text())
 project=json.loads((O/'p2-carrier-b.kicad_pro').read_text());assert not project['board']['design_settings'].get('drc_exclusions',[])
 assert not drc['violations'] and not drc['unconnected_items'] and not drc['schematic_parity'],drc
 assert {x['key'] for x in drc['ignored_checks']}=={'missing_courtyard','track_not_centered_on_via','tuning_profile_track_geometries','footprint_filters_mismatch','footprint_type_mismatch'} # KiCad10 defaults; recorded, not hidden
 # Keep USB VBUS detection supply separate from both external input and regulator outputs.
 assert mp['A3']=='V5_CARRIER' and mp['B4']=='V3V3'
 host={p.GetNumber():p.GetNetname() for p in fps['JHOST'].Pads()};assert host=={'1':'GND','2':'HOST_SDA','3':'HOST_SCL','4':'GND'}
 pads={p.GetNumber():p for p in fps['MPGA'].Pads()}
 assert all(P.ToMM(p.GetDrillSize().x)==1.2 and P.ToMM(p.GetSize().x)==2.05 for p in pads.values())
 r=dict(schema_version=1,date='2026-11-16',scope='native CAD parity/DRC plus design-budget checks; NOT hardware acceptance',kicad_version=P.GetBuildVersion(),electrical_components=len(parts),mounting_holes=8,connected_pad_net_pairs=len(expected),native_netlist_exact=True,body_envelopes_checked=len(envelopes),pcb_component_placements_exact=True,gpio_assigned=47,gpio_changes=False,uno_contacts_checked=len(geo),uno_origin_mm=[10,10],outline_mm=[164,124],copper_layers=4,ground_plane='In1.Cu; no routed signals',segments=sum(not isinstance(t,P.PCB_VIA) for t in b.GetTracks()),vias=sum(isinstance(t,P.PCB_VIA) for t in b.GetTracks()),erc_violations=0,drc_violations=0,drc_unconnected=0,schematic_parity_violations=0,ignored_drc_checks=drc['ignored_checks'],host_contract='unchanged: I2C0 GP20/21,0x42,100kHz,YM22S002,32events/PUSH,1000ms lease',firmware_ported=False,hardware_accepted=False,fabrication_released=False,pending=['Socket fitted sample and pin engagement','Actual current, voltage, ripple and thermal measurements','Fabricator stackup, USB impedance and final fabrication review','P2 C firmware port and hardware acceptance'],sha256={f:digest(O/f) for f in ['p2-carrier-b.kicad_pcb','netlist.xml','drc.json','erc.json','circuit.json','power-budget.json','mechanical-review.json','critical-routes.json','local-routes.json','placement-refs.json','body-clearances.json','power-fanouts.json','p2-b.ses','p2-carrier-b.kicad_pro']})
 if write_report:(O/'verification.json').write_text(json.dumps(r,indent=2)+'\n')
 else:assert json.loads((O/'verification.json').read_text())['sha256']==r['sha256']
 print(json.dumps(r,indent=2))
if __name__=='__main__':
 import argparse
 a=argparse.ArgumentParser();a.add_argument('--check-only',action='store_true');v=a.parse_args();check(not v.check_only)
