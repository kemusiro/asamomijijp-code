#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reconcile J purchasing quantities with the K CAD and retained pack sizes."""
from pathlib import Path
from decimal import Decimal as D,ROUND_HALF_UP
from collections import Counter
import json,csv,math,os
H=Path(__file__).resolve().parents[1];R=Path(os.environ.get('P2_REFERENCE_ROOT',str(H.parent)))
p=json.loads((H/'inputs/purchase-j.json').read_text());p['rows']=[r for r in p['rows'] if r['id']!='X01']
r=next(r for r in p['rows'] if r['id']=='U01');r.update(supplier='Akizuki',mpn='AE-Si5351A-B (110679)',price_jpy_incl='650.00',subtotal_jpy='650.00',url='https://akizukidenshi.com/catalog/g/g110679',availability='在庫あり・通販購入制限10セット。未引当',evidence='2026-11-20 秋月商品ページ・公式モジュール図面',note='K専用8Pランド、25MHz内蔵、I2C0x60、CL8pF。裸U13/Y1を置換。2.54mmヘッダーで浮かせて実装。',stock_observed=None,purchase_limit=10,price_checked='2026-11-20',source_currency='JPY',source_unit_price_excl='591',source_price_incl_is_authoritative=True,stock_source_url='https://akizukidenshi.com/catalog/g/g110679',pack_source_url='https://akizukidenshi.com/catalog/g/g110679')
r=next(r for r in p['rows'] if r['id']=='HDR');r.update(used=95,order_target=95,spare=25,note=r['note']+' K clockmodule8additionalcontacts;3x40 remain120,25spare incl cutloss; no extra header purchase cost.')
vendors={}
for r in p['rows']:
 assert r['buy_packs']==math.ceil(max(0,r['order_target']-r['stock'])/r['pack'])
 assert r['spare']==r['purchased']+r['stock']-r['used']>=0
 vendors[r['supplier']]=vendors.get(r['supplier'],D(0))+D(r['subtotal_jpy'])
refs=[ref for r in p['rows'] for ref in r['refs']];cad=[b+':'+r['ref'] for b in ['base','module','panel'] for r in json.loads((H/b/'circuit.json').read_text())['parts']]
assert Counter(refs)==Counter(cad) and len(refs)==276 and len(p['rows'])==85
p.update(date='2026-11-20',review='PCB-K',source='procurement J + Akizuki clockmodule adoption; X01 removed, HDR spare8 consumed',status='CAD reconciled procurement estimate; not reserved stock or final CAM quote',installed_refs=276,availability_flags=[],baseline_total_jpy=p['total_jpy'],vendors={k:str(v) for k,v in vendors.items()},parts_goods_jpy=str(sum(vendors.values())))
p['total_jpy']=str(sum(vendors.values())+D(p['pcb_delivered_jpy'])+p['parts_freight_jpy']+p['reserve_jpy']);p['budget_variance_jpy']=str(D(p['budget_jpy'])-D(p['total_jpy']));p['mouser_goods_excl_budget_jpy']=str((vendors['Mouser']/D('1.10')).quantize(D('.01'),rounding=ROUND_HALF_UP));p['fx_price_ids']=[r['id'] for r in p['rows'] if r.get('source_currency','JPY')!='JPY']
p['cart_checks']=['Akizuki module and inherited capacitor C_2.2u availability at checkout','Mouser Q1/E4 current stock and JPY cart prices; inherited other40 observations are not refreshed','18 inherited foreign-currency prices; budget FX USD160/EUR200, not market quotations','Single Mouser normal shipment free above6000JPY excl tax; final Japanese delivery cart not confirmed','K board CAM total and import charges; same dimensions/layers/standard0.3mmvias/HASL assumed']
assert p['pcb_each']==5 and p['populated_sets']==1 and D(p['total_jpy'])==D('27358.48')<30000
assert vendors['Mouser']==D('7403.88') and D(p['mouser_goods_excl_budget_jpy'])>6000
(H/'purchase-plan.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n')
fields=['id','supplier','mpn','used','stock','order_target','pack','buy_packs','purchased','spare','price_jpy_incl','subtotal_jpy','availability','url','refs','note']
with (H/'purchase-plan.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
 for r in p['rows']:w.writerow({**r,'refs':';'.join(r['refs'])})
print('PASS K purchasing:85lines/276refs,clockmodule+header8/Y1removed,total',p['total_jpy'])
