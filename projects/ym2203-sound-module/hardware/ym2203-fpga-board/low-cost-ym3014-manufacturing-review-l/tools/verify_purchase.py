# SPDX-License-Identifier: MIT
"""Check purchase completeness against the preserved K BOM and exported CSV."""
import csv, json, math, sys
from collections import Counter
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

root=Path(sys.argv[1]).resolve()
source=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root.parent/'low-cost-ym3014-pcb-review-k'
p=json.loads((root/'purchase-plan.json').read_text())
expected=[]
for board in ['base','module','panel']:
    with (source/board/'bom.csv').open() as f:
        expected += [board+':'+r['Reference'] for r in csv.DictReader(f)]
actual=[x for r in p['rows'] for x in r['refs']]
assert Counter(expected)==Counter(actual) and len(actual)==276
assert len(set(actual))==276
with (root/'purchase-plan.csv').open() as f: exported=list(csv.DictReader(f))
assert len(exported)==len(p['rows'])==85
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
assert totals['Mouser']/D('1.1')>=6000 and totals['Switch Science']>=3000 and totals['Akizuki']<11000
assert D(p['total_jpy'])==goods+p['parts_freight_jpy']+D(p['pcb_delivered_jpy'])+p['reserve_jpy']
assert D(p['pcb_delivered_jpy'])==(D(p['pcb_goods_usd'])+D(p['pcb_shipping_usd']))*p['budget_fx_jpy_per_usd']
print('PASS: K 276 refs, 85 purchase rows, packs/spares, CSV, vendor freight thresholds and total',p['total_jpy'])
