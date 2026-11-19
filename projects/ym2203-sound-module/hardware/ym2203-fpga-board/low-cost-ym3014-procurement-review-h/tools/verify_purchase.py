# SPDX-License-Identifier: MIT
"""Check purchase completeness against the preserved F BOM and exported CSV."""
import csv, json, math, sys
from collections import Counter
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

root=Path(sys.argv[1]).resolve()
source=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root.parent/'low-cost-ym3014-pcb-review-f'
p=json.loads((root/'purchase-plan.json').read_text())
expected=[]
for board in ['base','module','panel']:
    with (source/board/'bom.csv').open() as f:
        expected += [board+':'+r['Reference'] for r in csv.DictReader(f)]
actual=[x for r in p['rows'] for x in r['refs']]
assert Counter(expected)==Counter(actual) and len(actual)==277
assert len(set(actual))==277
with (root/'purchase-plan.csv').open() as f: exported=list(csv.DictReader(f))
assert len(exported)==len(p['rows'])==86
totals={}
for r,c in zip(p['rows'],exported):
    assert r['id']==c['ID']
    count=max(0,math.ceil((r['order_target']-r['stock'])/r['pack']))
    assert count==r['buy_packs']==int(c['包装数'])
    assert r['purchased']==count*r['pack']==int(c['購入個数'])
    assert r['spare']==r['stock']+r['purchased']-r['used']==int(c['余り'])>=0
    cost=(D(r['price_jpy_incl'])*count).quantize(D('.01'),rounding=ROUND_HALF_UP)
    assert cost==D(r['subtotal_jpy'])==D(c['小計円'])
    totals[r['supplier']]=totals.get(r['supplier'],D(0))+cost
assert {k:str(v) for k,v in totals.items()}==p['vendors']
goods=sum(totals.values()); assert goods==D(p['parts_goods_jpy'])
assert totals['DigiKey']>=6000 and totals['Switch Science']>=3000 and totals['Akizuki']<11000
assert totals['Mouser']<6000 and p['freight_by_vendor_jpy']['Mouser']==2500
assert p['parts_freight_jpy']==sum(p['freight_by_vendor_jpy'].values())
baseline=json.loads((root/'baseline-plan.json').read_text())
observations=json.loads((root/'price-observations.json').read_text())
changed={r['id'] for r in observations['selected']}
assert changed==set(baseline['pending_price_ids']+baseline['availability_flags']) and len(changed)==14
for old,new in zip(baseline['rows'],p['rows']):
    assert old['id']==new['id'] and old['refs']==new['refs'] and old['used']==new['used']
    if old['id'] not in changed:assert old==new
assert p['pending_price_ids']==[] and p['availability_flags']==[]
assert D(p['total_jpy'])==goods+p['parts_freight_jpy']+D(p['pcb_delivered_jpy'])+p['reserve_jpy']
assert D(p['pcb_delivered_jpy'])==(D(p['pcb_goods_usd'])+D(p['pcb_shipping_usd']))*p['budget_fx_jpy_per_usd']
print('PASS: F 277 refs, 86 purchase rows, packs/spares, CSV, vendor freight thresholds and total',p['total_jpy'])
