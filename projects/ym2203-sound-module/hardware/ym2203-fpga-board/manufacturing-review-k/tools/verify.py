#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify published text files, unchanged source CAD, one-set BOM and quote arithmetic."""
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import hashlib,json,argparse,zipfile
H=Path(__file__).resolve().parents[1];HW=H.parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest();read=lambda p:json.loads(p.read_text());D=lambda x:Decimal(str(x))
def main():
 global HW
 ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,default=HW);ap.add_argument('--archives',type=Path);a=ap.parse_args();HW=a.hardware_root.resolve()
 m=read(H/'verification/manifest.json')
 for rel,d in m['files'].items():assert sha(H/rel)==d,('Output modified',rel)
 for rel,d in read(H/'verification/source-manifest.json').items():assert sha(HW/rel)==d,('Source modified',rel)
 boards=read(H/'boards.json');cam=read(H/'verification/cam-verification.json')['boards'];eq=read(H/'verification/source-equivalence.json');assert set(boards)==set(cam)==set(eq)
 assert {k:v['copper_layers'] for k,v in cam.items()}=={'base-j4':4,'base-k2':2,'module-k2':2,'shield-b2':2}
 for k,c in boards.items():
  d=read(H/f'verification/{k}/drc.json');e=read(H/f'verification/{k}/erc.json');assert not any(d[n] for n in ['violations','unconnected_items','schematic_parity']);assert not any(s['violations'] for s in e['sheets']);assert cam[k]['cam_matches_native'] and eq[k]['physical_pad_track_zone_geometry_unchanged'];g=H/'gerbers'/k
  assert len(list(g.glob('*.g1')))==len(list(g.glob('*.g2')))==int(c['layers']==4)
  assert all(not list(g.glob(ext)) for ext in ['*.svg','*.zip','*.g3','*.g4'])
  assert read(g/(c['name']+'-job.gbrjob'))['GeneralSpecs']['LayerNumber']==c['layers']
 p=read(H/'procurement/order-profile.json');src=HW/'manufacturing-review-j/procurement/order-5pcb-1set/order-plan.json';assert sha(src)==p['parts_source_sha256'];old=read(src);assert p['parts']==[r for r in old['rows'] if not r['id'].startswith('PCB')];assert len(p['parts'])==87 and p['pcb_each']==5 and p['fitted_sets']==1;assert p['per_variant']=={'pcb_types':3,'ordered':15,'used':3,'spare':12};assert p['known_parts_subtotal_jpy_previous_record']==sum(r['known_subtotal_jpy'] or 0 for r in p['parts'])==6290
 o=read(H/'procurement/observations.json');c=read(H/'procurement/comparison.json');assert o['destination']=='Japan' and not any(o[k] for k in ['gerber_uploaded','cart_created','order_placed']);assert not c['parts_cost_included'] and not c['tax_and_clearance_included'] and c['quote_not_checkout'];assert not c['fx_is_live'];assert len(o['vendors'])==2
 for variant,v in p['variants'].items():
  assert v['boards']==(['base-j4','module-k2','shield-b2'] if variant=='primary' else ['base-k2','module-k2','shield-b2'])
  for vendor,x in o['vendors'].items():
   money=sum(D(x['boards'][k]['price_usd']) for k in v['boards']);assert all(x['boards'][k]['quantity']==5 for k in v['boards']);s=c['variants'][variant]['vendors'][vendor];assert money==D(s['pcb_total_usd'])==D(x['freight'][variant]['goods_usd'])
   for r in s['rates']:
    assert D(r['delivered_usd'])==money+D(r['cost_usd']);assert r['delivered_jpy']==int((D(r['delivered_usd'])*D(o['fx_assumption_jpy_per_usd'])).quantize(D(1),rounding=ROUND_HALF_UP))
   assert s['cheapest_inspected']==min(s['rates'],key=lambda r:r['delivered_usd'])
 v=read(H/'verification/hand-assembly-vias.json');assert sum(len(v['sites_by_board'][k]) for k in p['variants']['primary']['boards'])==v['primary_count']==7;assert sum(len(v['sites_by_board'][k]) for k in p['variants']['comparison']['boards'])==v['comparison_count']==6
 if a.archives:
  ar=read(H/'verification/archive-manifest.json')
  for name,digest in ar['files'].items():
   p=a.archives/name;assert sha(p)==digest,('ZIP SHA mismatch',name)
   with zipfile.ZipFile(p) as z:assert z.testzip() is None
  for key,name in ar['per_board_zip_names'].items():
   with zipfile.ZipFile(a.archives/name) as z:
    expected={p.name:p.read_bytes() for p in (H/'gerbers'/key).iterdir() if p.is_file()};assert {n:z.read(n) for n in z.namelist()}==expected,('Wrong CAM zip',key)
  for variant,label in [('primary','4-2'),('comparison','2-2')]:
   with zipfile.ZipFile(a.archives/f'p2-{variant}-{label}.zip') as z:
    for key in read(H/'procurement/order-profile.json')['variants'][variant]['boards']:
     name=ar['per_board_zip_names'][key];assert z.read(name)==(a.archives/name).read_bytes()
  print('PASS: six ZIP CRC/SHA checks; four individual CAM sets and both order bundles')
 print('PASS:',len(m['files']),'output hashes;',len(read(H/'verification/source-manifest.json')),'unchanged CAD inputs; 4 native/CAM sets; 87 shared parts; 2 order variants and quote arithmetic')
if __name__=='__main__':main()
