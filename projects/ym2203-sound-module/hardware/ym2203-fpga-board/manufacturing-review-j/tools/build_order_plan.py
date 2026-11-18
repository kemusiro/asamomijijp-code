"""Plan five bare PCBs of each design and one fitted set; no CAD changes."""
import csv,hashlib,json,math,sys
from pathlib import Path

root=Path(__file__).resolve().parents[1]
out=Path(sys.argv[1]) if len(sys.argv)>1 else root/'procurement/order-5pcb-1set'
out.mkdir(parents=True,exist_ok=True)
source=root/'procurement/catalog.json';catalog=json.loads(source.read_text());rows=[]
for item in catalog['rows']:
 r={k:v for k,v in item.items() if k not in {'qty_five','order_one','order_five'}}
 pcb=r['kind']=='PCB';required=5 if pcb else r['qty_one'];used=r['qty_one'];pack=5 if pcb else r['pack_size']
 need=max(0,required+r['spare']-r['stock']);units=math.ceil(need/pack) if pack else None
 r.update(required_qty=required,used_qty=used,pack_size=pack,order_units=units,purchased_qty=units*pack if units is not None else None,remaining_qty=units*pack+r['stock']-used if units is not None else None,price_jpy=r['price_jpy'],known_subtotal_jpy=units*r['price_jpy'] if units is not None and r['price_jpy'] is not None else None)
 if pcb:
  r.update(unit='枚',pack_verified=True,sales_basis='今回の製造見積は5枚/ロット',note='今回は各5枚を1ロット発注し、1枚だけ実装。残り4枚は未実装予備。金額はPCB送料込み比較表を参照。')
 if r['id']=='J03':r['note']=r['note'].replace('1セット6本・5セット26本。','今回は6本。')
 if r['id']=='LCDWIRE':r['note']=r['note'].replace('5セットなら40ch=1本。','今回は40chのうち8ch使用。')
 rows.append(r)
plan={'schema_version':1,'checked':'2026-11-18','profile':{'pcb_each':5,'fitted_sets':1,'pcb_types':3,'bare_boards_ordered':15,'bare_boards_used':3,'bare_boards_spare':12,'stock_default':0,'header_spare_contacts_per_order':40},'catalog_source':'../catalog.json','catalog_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'rows':rows}
assert len(rows)==90
pcbs=[r for r in rows if r['kind']=='PCB'];parts=[r for r in rows if r['kind']!='PCB']
assert len(pcbs)==3 and sum(r['required_qty'] for r in pcbs)==15 and sum(r['remaining_qty'] for r in pcbs)==12
assert all(r['required_qty']==r['qty_one'] for r in parts)
assert next(r for r in rows if r['id']=='J02')['required_qty']==128
assert next(r for r in rows if r['id']=='M02')['required_qty']==1
assert next(r for r in rows if r['id']=='J03')['order_units']==6
assert sum(r['known_subtotal_jpy'] or 0 for r in rows if r['supplier']=='秋月')==6290
(out/'order-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
fields=['id','name','mpn','kind','supplier','supplier_code','required_qty','used_qty','unit','pack_size','pack_verified','stock','spare','order_units','purchased_qty','remaining_qty','price_jpy','known_subtotal_jpy','availability','selection','checked','url','source','note']
for name,items in [('order-bom.csv',rows),('akizuki-order.csv',[r for r in rows if r['supplier']=='秋月']),('other-suppliers.csv',[r for r in rows if r['supplier']!='秋月'])]:
 with (out/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(items)
print('PASS: PCB 5 x 3=15; fitted sets=1; unused bare PCBs=12; MCU receptacles=128; Akizuki known subtotal=6290 JPY')
