# SPDX-License-Identifier: MIT
"""Apply the 14-row procurement review to a preserved review G snapshot."""
import copy, hashlib, json, math
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
baseline=json.loads((ROOT/'baseline-plan.json').read_text())
plan=copy.deepcopy(baseline)
updates=json.loads((ROOT/'price-observations.json').read_text())
by={r['id']:r for r in plan['rows']}
changes=[]
for u in updates['selected']:
    row=by[u['id']];before=copy.deepcopy(row)
    for key in ['mpn','supplier','pack','price_jpy_incl','url','availability','note']:
        if key in u:row[key]=u[key]
    row['evidence']='2026-11-19 '+u['observation_method']
    row['price_checked']='2026-11-19'
    row['buy_packs']=max(0,math.ceil((row['order_target']-row['stock'])/row['pack']))
    row['purchased']=row['buy_packs']*row['pack']
    row['spare']=row['stock']+row['purchased']-row['used']
    row['subtotal_jpy']=str((D(row['price_jpy_incl'])*row['buy_packs']).quantize(D('.01'),rounding=ROUND_HALF_UP))
    changes.append({'id':row['id'],'old_mpn':before['mpn'],'new_mpn':row['mpn'],'old_supplier':before['supplier'],'new_supplier':row['supplier'],'old_subtotal_jpy':before['subtotal_jpy'],'new_subtotal_jpy':row['subtotal_jpy'],'delta_jpy':str(D(row['subtotal_jpy'])-D(before['subtotal_jpy'])),'url':row['url']})
assert len(changes)==14
assert set(u['id'] for u in updates['selected'])==set(baseline['pending_price_ids']+baseline['availability_flags'])
assert [(r['id'],r['refs'],r['used']) for r in plan['rows']]==[(r['id'],r['refs'],r['used']) for r in baseline['rows']]
plan['vendors']={v:str(sum(D(r['subtotal_jpy']) for r in plan['rows'] if r['supplier']==v)) for v in sorted({r['supplier'] for r in plan['rows']})}
goods=sum(D(x) for x in plan['vendors'].values())
plan.update(source='LC-G preserved purchase plan / LC-F unchanged CAD',review='LC-H',status='public_catalog_review_not_reserved_or_final_cart',parts_goods_jpy=str(goods),parts_freight_jpy=3050,freight_by_vendor_jpy={'Akizuki':550,'DigiKey':0,'Switch Science':0,'Mouser':2500},mouser_freight_status='unquoted budget allowance, not a published tariff',reserve_jpy=2000,pending_price_ids=[],availability_flags=[],scarce_ids=['C_2.2u'],cart_checks=['U07 Mouser product stock/price and small-order delivery charge','C_2.2u Akizuki scarce stock','PCB final CAM cart/tax'],baseline_total_jpy=baseline['total_jpy'])
plan['total_jpy']=str(goods+plan['parts_freight_jpy']+D(plan['pcb_delivered_jpy'])+plan['reserve_jpy'])
plan['budget_variance_jpy']=str(D(plan['total_jpy'])-plan['budget_jpy'])
(ROOT/'purchase-plan.json').write_text(json.dumps(plan,ensure_ascii=False,indent=2)+'\n')
(ROOT/'changes.json').write_text(json.dumps(changes,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:plan[k] for k in ['vendors','parts_goods_jpy','parts_freight_jpy','reserve_jpy','total_jpy','budget_variance_jpy']},ensure_ascii=False,indent=2))
