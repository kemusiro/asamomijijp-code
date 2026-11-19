#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only checks for a layer strategy, not two-layer PCB acceptance."""
import argparse,hashlib,json
from pathlib import Path

HERE=Path(__file__).resolve().parent
def read(p):return json.loads(p.read_text())
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stable(a):return hashlib.sha256(json.dumps(a,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
def contract(plan):
 assert plan['primary_variant']=='base4-module2'
 assert plan['comparison_variant']=='base2-module2'
 v={v['id']:v for v in plan['variants']};assert set(v)=={'base4-module2','base2-module2'}
 assert v['base4-module2']['layers']=={'base':4,'module':2,'shield':2}
 assert v['base2-module2']['layers']=={'base':2,'module':2,'shield':2}
 assert all(not x['routed'] and not x['drc_passed'] and not x['hardware_accepted'] and x['quoted_total_usd'] is None for x in v.values())
 assert not plan['new_cad_created'] and not plan['existing_cad_modified'] and not plan['new_firmware_created'] and not plan['order_placed']
 assert plan['latest_validated_cad']['layers']=={'base':4,'module':4,'shield':2}
 assert not plan['comparison_assumptions']['gpio_change'] and not plan['comparison_assumptions']['connector_pin_change'] and not plan['comparison_assumptions']['schematic_net_change']
 assert plan['comparison_assumptions']['thickness_mm']==1.6

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,default=HERE.parent);args=ap.parse_args()
 h=args.hardware_root;plan=read(HERE/'plan.json');audit=read(HERE/'native-audit.json');manifest=read(HERE/'manifest.json')
 contract(plan)
 for name,sha in manifest['files'].items():assert digest(HERE/name)==sha,('Study output changed',name)
 for name,sha in manifest['preserved_inputs_sha256'].items():assert digest(h/name)==sha,('Design/source changed',name)
 for name,sha in audit['inputs_sha256'].items():assert digest(h/name)==sha,('Audited CAD changed',name)
 for name,sha in manifest['plan_preservation_sha256'].items():
  p=read(h/name);layer=p.pop('layer_study');assert stable(p)==sha,('Existing plan field changed',name)
  assert layer['plan']=='layer-study-review-a/plan.json' and layer['primary']==plan['primary_variant'] and layer['comparison']==plan['comparison_variant']
 original=read(h/'p2-modular-plan.json')['legacy'];assert original['host_source_modified'] is False
 for name,value in plan['preserved_requirements']['host'].items():
  actual=original[name] if name not in ['address','hz'] else read(h/'p2-modular-plan.json')['base']['host_i2c'][name]
  assert actual==value,('HOST requirement mismatch',name)
 prior=read(h/'clean-sheet-pcb-review-j/routing-review.json')['nets']
 for board,expected in [('base',{'F.Cu':1100,'B.Cu':273,'In2.Cu':682}),('module',{'F.Cu':731,'B.Cu':191,'In2.Cu':238})]:
  a=audit['boards'][board];assert a['copper_layers']==4
  assert {k:v['segments'] for k,v in a['track_layers'].items()}==expected
  assert sum(v['segments'] for v in a['track_layers'].values())==sum(n['segments'] for n in prior[board].values())
  assert sum(a['via_drills_mm_counts'].values())==sum(n['vias'] for n in prior[board].values())
  assert a['nets_using_inner2_including_power']==sorted(n for n,r in prior[board].items() if 'In2.Cu' in r['layers'])
  assert any(z['net']=='GND' and z['layers']==['In1.Cu'] for z in a['zones']) and 'In1.Cu' not in a['track_layers']
 print('PASS: primary 4/2, comparison 2/2; native layer inventory; preserved CAD/GPIO/HOST/plan fields. No two-layer DRC performed.')

if __name__=='__main__':main()
