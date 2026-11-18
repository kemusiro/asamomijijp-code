"""Read-only verification of the manufacturing candidate and native BOM coverage."""
import argparse,collections,csv,hashlib,json,math
from pathlib import Path

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path);a=ap.parse_args()
 p=Path(__file__).resolve().parents[1];h=a.hardware_root.resolve() if a.hardware_root else p.parent
 manifest=json.loads((p/'verification/manifest.json').read_text())
 for name,sha in manifest['files'].items():assert hashlib.sha256((p/name).read_bytes()).hexdigest()==sha,('Changed output',name)
 sources=json.loads((p/'verification/source-manifest.json').read_text())
 for name,sha in sources['files'].items():assert hashlib.sha256((h/name).read_bytes()).hexdigest()==sha,('Changed source',name)
 data=json.loads((p/'procurement/catalog.json').read_text());rows=data['rows'];ids={r['id']:r for r in rows};assert len(ids)==len(rows)==90
 maps=list(csv.DictReader((p/'procurement/reference-map.csv').open()))
 expected={}
 for board,path in [('base','clean-sheet-pcb-review-j/base/bom.csv'),('module','clean-sheet-pcb-review-j/module/bom.csv'),('shield','editor-shield-review-b/bom.csv')]:
  for r in csv.DictReader((h/path).open()):expected[(board,r['Reference'])]=(r['Value'],r['Footprint'])
 got={}
 for r in maps:
  key=(r['board'],r['reference']);assert key not in got,('Duplicate BOM ref',key)
  got[key]=(r['value'],r['footprint']);assert r['purchase_id'] in ids or r['purchase_id']=='PCB-COPPER'
 assert got==expected and len(got)==274
 for r in rows:
  qty=sum(r['qty_'+k] for k in ['base','module','shield','external'])
  assert qty>0 and qty==r['qty_one'] and qty*5==r['qty_five']
  for n,label in [(1,'one'),(5,'five')]:
   expected=math.ceil(max(0,qty*n+r['spare']-r['stock'])/r['pack_size']) if r['pack_size'] else None
   assert r['order_'+label]==expected,(r['id'],label)
  if r['pack_verified']:assert r['pack_size']>0
 assert ids['M02']['qty_module']==1 and len(ids['M02']['refs'])==4
 assert ids['J02']['qty_one']==128 and ids['J03']['qty_one']==199
 assert ids['J03']['order_one']==6 and ids['J03']['order_five']==26
 assert ids['J04']['mpn']=='SSW-120-02-G-D' and ids['J05']['mpn']=='TSW-120-07-G-D'
 observations=json.loads((p/'procurement/supplier-observations.json').read_text())
 for r in rows:
  if r['supplier']=='秋月':
   ob=observations[r['supplier_code']]
   assert r['pack_size']==ob['units_per_sale'] and r['price_jpy']==ob['price_jpy'] and r['url']==ob['url']
 cam=json.loads((p/'verification/cam-verification.json').read_text())
 assert all(v['cam_matches_native'] for v in cam['boards'].values())
 counts={k:(v['outline_mm'],v['copper_layers']) for k,v in cam['boards'].items()}
 assert counts=={'base':([220,142],4),'module':([100,100],4),'shield':([76,100],2)}
 print(f'PASS: {len(manifest["files"])} output hashes; {len(sources["files"])} input hashes; 274 native refs; 90 purchase rows; 30 Akizuki observations; 3 CAM boards')

if __name__=='__main__':main()
