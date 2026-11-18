#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only verification of the adopted three-board order and one component set."""
from pathlib import Path
import argparse,csv,hashlib,json,math,zipfile
H=Path(__file__).resolve().parents[1]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
def read(p):return json.loads(p.read_text())
def main():
 a=argparse.ArgumentParser();a.add_argument('--hardware-root',type=Path,default=H.parent);a.add_argument('--outputs',type=Path);args=a.parse_args();hw=args.hardware_root;p=read(H/'order-plan.json');assert p['selection']=='base4-module2' and p['selection_confirmed_by_user'] and not p['order_placed'];assert p['profile']['pcb_each']==5 and p['profile']['fitted_sets']==1
 for rel,digest in p['sources_sha256'].items():assert sha(hw/rel)==digest,('Source changed',rel)
 for rel,digest in read(H/'manifest.json')['files'].items():assert sha(H/rel)==digest,('Output changed',rel)
 old=read(hw/'manufacturing-review-j/procurement/order-5pcb-1set/order-plan.json');parts=[r for r in p['rows'] if r['kind']!='PCB'];assert [{k:v for k,v in r.items() if k not in ['fabrication_set','gerber_zip']} for r in parts]==[r for r in old['rows'] if r['kind']!='PCB'];assert len(parts)==87 and len(p['rows'])==90
 assert [(q['set'],q['layers'],q['quantity'],q['fitted'],q['spare']) for q in p['boards']]==[('base-j4',4,5,1,4),('module-k2',2,5,1,4),('shield-b2',2,5,1,4)]
 for b in p['boards']:
  src=hw/'manufacturing-review-k/gerbers'/b['set'];dest=H/b['gerbers'];assert {q.name:sha(q) for q in src.iterdir() if q.is_file()}=={q.name:sha(q) for q in dest.iterdir() if q.is_file()};assert read(dest/(b['name']+'-job.gbrjob'))['GeneralSpecs']['LayerNumber']==b['layers']
 for r in p['rows']:
  units=math.ceil(max(0,r['required_qty']+r['spare']-r['stock'])/r['pack_size']) if r['pack_size'] else None;assert r['order_units']==units;assert r['remaining_qty']==(units*r['pack_size']+r['stock']-r['used_qty'] if units is not None else None)
 with (H/'purchase-bom.csv').open() as f:rows=list(csv.DictReader(f));assert len(rows)==90
 for q,r in zip(rows,p['rows']):
  for k in ['id','mpn','required_qty','used_qty','order_units','remaining_qty','fabrication_set','gerber_zip']:assert q[k]==('' if r[k] is None else str(r[k])),(r['id'],k)
 for name,supplier in [('akizuki-order.csv',True),('other-suppliers.csv',False)]:
  with (H/name).open() as f:q=list(csv.DictReader(f));assert [r['id'] for r in q]==[r['id'] for r in p['rows'] if (r['supplier']=='秋月')==supplier]
 assert sha(H/'reference-map.csv')==sha(hw/'manufacturing-review-j/procurement/reference-map.csv');assert sum(r['known_subtotal_jpy'] or 0 for r in parts)==6290;assert sum(len(v) for v in read(H/'assembly-vias.json')['sites_by_board'].values())==7
 check=read(H/'workbook-check.json');saved=read(H/'workbook-verification.json');assert check['pcb_ordered']==15 and check['pcb_spare']==12 and check['input_recalculation_checks']==6 and saved['saved_error_cells']==0 and saved['references']==274
 if args.outputs:
  out=args.outputs
  for name,digest in read(H/'archive-manifest.json')['files'].items():assert sha(out/name)==digest,('Binary output changed',name)
  assert sha(out/'p2-primary-4-2-order.xlsx')==saved['workbook_sha256']
  for b in p['boards']:
   with zipfile.ZipFile(out/b['zip']) as z:assert z.testzip() is None;assert {n:z.read(n) for n in z.namelist()}=={q.name:q.read_bytes() for q in (H/b['gerbers']).iterdir() if q.is_file()}
  with zipfile.ZipFile(out/'p2-primary-order-5pcb-1set.zip') as z:
   assert z.testzip() is None
   assert sorted(n for n in z.namelist() if n.endswith('-gerber.zip'))==sorted(b['zip'] for b in p['boards'])
   assert 'p2-base-k2-gerber.zip' not in z.namelist()
   for b in p['boards']:assert z.read(b['zip'])==(out/b['zip']).read_bytes()
   for name in ['README.md','purchase-bom.csv','akizuki-order.csv','other-suppliers.csv','reference-map.csv','assembly-vias.json','order-plan.json']:assert z.read(name)==(H/name).read_bytes()
   assert z.read('p2-primary-4-2-order.xlsx')==(out/'p2-primary-4-2-order.xlsx').read_bytes()
 print('PASS: adopted J4/K2/B2, 15 PCBs / 3 fitted / 12 spare, 87 unchanged component rows, 90-line BOM, 274 refs, 7 prefill vias, workbook and selected CAM archives')
if __name__=='__main__':main()
