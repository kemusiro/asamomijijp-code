#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prepare the selected J4/K2/B2 purchase quantities without changing historical records."""
from pathlib import Path
import argparse,csv,hashlib,json,copy

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]);a=ap.parse_args();h=a.hardware_root.resolve();o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
 oldpath=h/'manufacturing-review-j/procurement/order-5pcb-1set/order-plan.json';old=json.loads(oldpath.read_text());rows=copy.deepcopy(old['rows']);cfg=json.loads((h/'manufacturing-review-k/boards.json').read_text());selected=[('PCB1','base-j4','ベースJ・4層'),('PCB2','module-k2','YM2203音源K・2層'),('PCB3','shield-b2','開口なし音色編集シールドB・2層')];boards=[]
 for ident,key,label in selected:
  r=next(q for q in rows if q['id']==ident);c=cfg[key];r.update(name=label+'製作基板',mpn=c['name'],supplier='PCB製造業者（JLCPCB / PCBWay見積）',package='FR-4 1.6mm / '+str(c['layers'])+'層',fabrication_set=key,gerber_zip='p2-'+key+'-gerber.zip',note='各5枚を1ロット発注、1枚実装・4枚予備。ENIG・外層1oz'+('・内層1oz' if c['layers']==4 else '')+'。USD製造/送料は主案見積を参照。Gerber ZIPを個別指定。')
  boards.append({'purchase_id':ident,'set':key,'name':c['name'],'layers':c['layers'],'quantity':5,'fitted':1,'spare':4,'cad':c['dir']+'/'+c['name']+'.kicad_pcb','gerbers':'gerbers/'+key,'zip':r['gerber_zip']})
 for r in rows:
  r.setdefault('fabrication_set','');r.setdefault('gerber_zip','')
 parts=[q for q in rows if q['kind']!='PCB'];previous=[q for q in old['rows'] if q['kind']!='PCB'];assert [{k:v for k,v in q.items() if k not in ['fabrication_set','gerber_zip']} for q in parts]==previous
 catalog=json.loads((h/'manufacturing-review-j/procurement/catalog.json').read_text());known=sum(q['known_subtotal_jpy'] or 0 for q in parts);assert len(rows)==90 and len(parts)==87 and known==6290
 sources=['manufacturing-review-j/procurement/order-5pcb-1set/order-plan.json','manufacturing-review-j/procurement/catalog.json','manufacturing-review-j/procurement/reference-map.csv','manufacturing-review-k/boards.json','manufacturing-review-k/procurement/comparison.json']
 data={'schema_version':1,'checked':'2026-11-18','selection':'base4-module2','selection_confirmed_by_user':True,'profile':old['profile'],'boards':boards,'rows':rows,'pcb_only_refs':catalog['pcb_only_refs'],'known_parts_subtotal_jpy':known,'parts_prices_researched_this_task':False,'parts_quantities_preserved':True,'sources_sha256':{p:hashlib.sha256((h/p).read_bytes()).hexdigest() for p in sources},'quote_source':'../manufacturing-review-k/procurement/comparison.json','order_placed':False}
 (o/'order-plan.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
 fields=['id','name','mpn','kind','supplier','supplier_code','required_qty','used_qty','unit','pack_size','pack_verified','stock','spare','order_units','purchased_qty','remaining_qty','price_jpy','known_subtotal_jpy','availability','selection','checked','url','source','note','fabrication_set','gerber_zip']
 for name,items in [('purchase-bom.csv',rows),('akizuki-order.csv',[q for q in rows if q['supplier']=='秋月']),('other-suppliers.csv',[q for q in rows if q['supplier']!='秋月'])]:
  with (o/name).open('w',encoding='utf-8',newline='') as f:
   writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');writer.writeheader();writer.writerows(items)
 (o/'reference-map.csv').write_bytes((h/'manufacturing-review-j/procurement/reference-map.csv').read_bytes())
 print('PASS: selected J4/K2/B2; PCB 5x3; one unchanged parts set; 90 purchase rows; known subtotal',known)
if __name__=='__main__':main()
