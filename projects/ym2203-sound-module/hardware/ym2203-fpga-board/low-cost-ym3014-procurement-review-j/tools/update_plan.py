# SPDX-License-Identifier: MIT
"""Apply three targeted purchasing observations to the preserved review I plan."""
import csv,json
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=json.loads((root/'baseline-plan.json').read_text())
obs=json.loads((root/'price-observations.json').read_text())
changes=[]
for o in obs['selected']:
 r=next(r for r in p['rows'] if r['id']==o['id']);old=dict(r)
 unit=D(str(o['tiers'][0][1]))*D('1.10')
 r.update(mpn=o['mpn'],url=o['url'],price_jpy_incl=str(unit),subtotal_jpy=str((unit*r['buy_packs']).quantize(D('.01'),rounding=ROUND_HALF_UP)),availability=o['availability'],evidence=o['evidence'],note=o['note'],price_checked=o['price_checked'],source_currency='JPY',source_unit_price_excl=str(o['tiers'][0][1]),stock_observed=o['stock'],minimum_order=1,order_multiple=1,stock_source_url=o.get('stock_url',o['url']),pack_source_url=o['url'],review_checked='2026-11-20')
 changes.append({'id':r['id'],'previous_mpn':old['mpn'],'selected_mpn':r['mpn'],'old_subtotal_jpy':old['subtotal_jpy'],'new_subtotal_jpy':r['subtotal_jpy'],'decision':o['decision']})
vendors={}
for r in p['rows']:vendors[r['supplier']]=vendors.get(r['supplier'],D(0))+D(r['subtotal_jpy'])
p.update(date='2026-11-20',review='J',source='review I preserved; three zero-stock rows reviewed',status='two catalog-compatible alternatives selected; clock remains unavailable; not an order quote',baseline_total_jpy=p['total_jpy'],vendors={k:str(v) for k,v in vendors.items()},parts_goods_jpy=str(sum(vendors.values())))
p['total_jpy']=str(sum(vendors.values())+D(str(p['parts_freight_jpy']))+D(str(p['pcb_delivered_jpy']))+D(str(p['reserve_jpy'])))
p['budget_variance_jpy']=str(D(p['budget_jpy'])-D(p['total_jpy']))
p['availability_flags']=['U01']
p['fx_price_ids']=[r['id'] for r in p['rows'] if r.get('source_currency','JPY')!='JPY']
p['mouser_goods_excl_budget_jpy']=str((vendors['Mouser']/D('1.1')).quantize(D('.01'),rounding=ROUND_HALF_UP))
p['cart_checks']=['U01 Si5351A-B-GTR/GT availability and delivery date remain unresolved','U10 Q1 stock18 is a two-day indexed observation; recheck three pieces in Japan cart','U17 E4 stock1656 from one-week index; JPY112.9 price from older Japan index; recheck cart','19 inherited foreign-currency estimates and final Japanese cart prices','Normal single Mouser order free-shipping condition; backorder split shipment not confirmed','PCB CAM/freight/import costs and inherited Akizuki C_2.2u stock']
(root/'purchase-plan.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
(root/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
with (root/'mouser-order.csv').open('w',newline='') as f:
 w=csv.writer(f);w.writerow(['Manufacturer Part Number','Quantity','Customer Reference'])
 for r in p['rows']:
  if r['supplier']=='Mouser':w.writerow([r['mpn'],r['purchased'],r['id']])
with (root/'baseline-mouser-43.csv').open() as f: rows=list(csv.DictReader(f)); fields=list(rows[0])
for r in rows:
 if r['ID'] not in {o['id'] for o in obs['selected']}:continue
 o=next(o for o in obs['selected'] if o['id']==r['ID']);new=next(n for n in p['rows'] if n['id']==r['ID'])
 r.update(MPN=o['mpn'],掲載在庫=o['stock'],通貨='JPY',税別単価=o['tiers'][0][1],適用数量帯=1,税込換算小計円=new['subtotal_jpy'],取得方法=o['method'],収録時期=o['crawled'],価格URL=o['url'],在庫URL=o.get('stock_url',o['url']),販売単位URL=o['url'],注意=o['note'])
with (root/'mouser-43.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
print(p['vendors'],p['total_jpy'])
