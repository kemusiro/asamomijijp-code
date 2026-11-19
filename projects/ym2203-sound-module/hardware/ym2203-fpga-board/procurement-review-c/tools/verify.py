#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check procurement arithmetic and preserve the input fabrication/BOM snapshots."""
from pathlib import Path
from decimal import Decimal
import hashlib
import json
from build_report import calculated, outputs, order_units

P = Path(__file__).resolve().parents[1]
HW = P.parent


def read(path):
    return json.loads(path.read_text())


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    lock = read(P/'source-lock.json')
    for name, expected in lock['files'].items():
        assert digest(HW/name) == expected, ('input modified',name)
    archive = read(HW/'primary-order-review-b/archive-manifest.json')['files']
    assert all(archive[name] == sha for name,sha in lock['fabrication_zip_sha256'].items())
    original = read(HW/'primary-order-review-b/order-plan.json')
    base = {r['id']:r for r in original['rows']}
    observed = read(P/'parts-observations.json')
    assert not observed['purchases_made'] and not observed['stock_reserved'] and not observed['cart_quote_complete']
    rows = observed['rows']
    assert {r['id'] for r in rows} == {r['id'] for r in base.values() if not r['pack_verified']} | {'C14'}
    assert len(rows) == 57 and len({r['id'] for r in rows}) == 57
    assert observed['original_order_plan_sha256'] == digest(HW/'primary-order-review-b/order-plan.json')
    assert sum(r['unit_confirmed'] for r in rows) == 39
    for row in rows:
        old = base[row['id']]
        assert row['required_qty'] == old['required_qty'] and row['used_qty'] == old['used_qty']
        assert row['original_mpn'] == old['mpn']
        assert row['unit_confirmed'] == (row['minimum_sales_units'] is not None)
        if row['unit_confirmed']:
            assert all(isinstance(row[k],int) and row[k]>0 for k in
                       ['minimum_sales_units','multiple_sales_units','pieces_per_sales_unit'])
        else:
            assert row['multiple_sales_units'] is None and row['pieces_per_sales_unit'] is None
        if row['price_per_sales_unit'] is not None:
            assert row['price_per_sales_unit'] > 0 and row['currency'] in {'JPY','USD'}
        assert row['evidence_mode'] in {'indexed_catalog','live_product','pending'}
    calculations = {r['id']:r for r in calculated(P)}
    for id, expected in {'J02':(128,128,0),'J10':(5,5,4),'C14':(5,5,3),'H03':(3,30,8),
                         'S02':(1,1,0),'H02':(50,50,46),'H04':(1,10,2)}.items():
        row = calculations[id]
        assert (row['sales_units'],row['purchased_pieces'],row['remaining']) == expected,(id,row)
    assert Decimal(calculations['J02']['line_goods_reference']) == Decimal('12788.48')
    assert Decimal(calculations['R08']['line_goods_reference']) == Decimal('126.0')
    # Edge cases matter when a future measured stock quantity reduces an order to zero.
    assert order_units(0,5,5,1)==0 and order_units(6,5,5,1)==10
    assert order_units(22,1,1,10)==3 and order_units(1,None,None,None) is None
    for id in ['C01','C09','H06','M03']:
        assert calculations[id]['sales_units'] is None
    for row in calculations.values():
        assert not row['availability_confirmed_for_checkout'] and row['not_an_order']
        if row['purchased_pieces'] is not None:
            assert row['purchased_pieces'] >= row['required'] and row['remaining'] >= 0
    quotes = read(P/'pcb-quotes.json')
    assert quotes['pcb_each']==5 and quotes['fitted_sets']==1
    assert quotes['pcb_ordered']==15 and quotes['pcb_spare']==12
    assert [(b['size_mm'],b['layers'],b['quantity']) for b in quotes['boards']] == [([220,142],4,5),([100,100],2,5),([76,100],2,5)]
    assert quotes['jpy_per_usd_assumption']==160 and not quotes['exchange_rate_is_market_quote']
    jlc, pcbway = quotes['vendors']
    for fee_parts, total in zip(jlc['components_usd'],jlc['board_prices']):
        assert sum(Decimal(str(x)) for x in fee_parts.values()) == Decimal(str(total))
    assert sum(Decimal(str(x)) for x in jlc['board_prices']) == Decimal('227.36')
    assert sum(Decimal(str(x)) for x in pcbway['board_prices']) == Decimal('252.98')
    assert jlc['shipping_weight_kg'] >= sum(jlc['display_weights_kg'])
    assert 220*142*5 + 100*100*5 + 76*100*5 == 220*222*5
    totals = read(P/'comparison.json')
    assert (totals[0]['total_usd'],totals[0]['reference_jpy']) == ('237.05',37928)
    assert (totals[3]['total_usd'],totals[3]['reference_jpy']) == ('271.49',43438)
    assert not read(P/'candidates.json')['cad_or_bom_changed']
    for name, expected in outputs(P).items():
        assert (P/name).read_text()==expected,('derived output stale',name)
    manifest = read(P/'manifest.json')
    for name, sha in manifest['files'].items():
        assert digest(P/name)==sha,('review C changed',name)
    print('PASS: review C; 57 observations, 39 sales conditions, 18 pending; 6 freight comparisons; original CAD/BOM/CAM unchanged')


if __name__=='__main__':
    main()
