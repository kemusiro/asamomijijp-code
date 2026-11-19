# SPDX-License-Identifier: MIT
"""Build a Mouser-only overseas procurement review from the preserved H plan."""
import copy, csv, json, math
from collections import Counter
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def money(n):
    return str(D(n).quantize(D('.01'), rounding=ROUND_HALF_UP))

def build():
    baseline = json.loads((ROOT/'baseline-plan.json').read_text())
    evidence = json.loads((ROOT/'price-observations.json').read_text())
    plan = copy.deepcopy(baseline)
    by = {r['id']: r for r in plan['rows']}
    expected = {r['id'] for r in baseline['rows'] if r['supplier'] in ('DigiKey', 'Mouser')}
    assert expected == {r['id'] for r in evidence['selected']} and len(expected) == 43
    changes, table = [], []
    for obs in evidence['selected']:
        row = by[obs['id']]
        old = copy.deepcopy(row)
        assert obs['minimum'] == obs['multiple'] == 1
        need = max(0, row['used'] - row['stock'])
        # A higher price break may cost less overall; buy only the best quoted lot.
        candidates = [(max(need, q, obs['minimum']), D(str(u)), q) for q, u in obs['tiers']]
        quantity, unit, tier = min(candidates, key=lambda x: (x[0]*x[1], x[0]))
        fx = D(str(evidence['fx_budget_jpy'][obs['currency']]))
        price_incl = unit * fx * (D(1)+D(str(evidence['jct_rate'])))
        status = '在庫0表示・取り寄せ、納期要照会' if obs['stock'] == 0 else f'掲載在庫{obs["stock"]:,}・未引当'
        note = 'カットテープを選択。有料MouseReel/完全リールは注文しない。'
        if row['id'] in ('MUX','ADC','U06'):
            note = 'チューブ品を1個単位で購入。工場包装数の一括購入は不要。'
        if row['id'] in ('S01','STACK12','LCD12'):
            note = 'バルク1個単位。寸法・ねじ規格を維持。'
        if row['id'] == 'R_1.33k':
            note += ' RCからACへ同仕様代替。1.33kΩ±1%、0.125W、0805/2012、2.0×1.25mm、厚さ0.5±0.1mm。CAD変更なし。'
        if obs['currency'] != 'JPY':
            note += f' {obs["currency"]}掲載価格×予算換算{fx}円＋消費税10%。日本円カート単価は未取得。'
        if row['id'] == 'C_22u':
            note += ' 元MPNを維持。NRNDの既存注意も継承し、1210を0805へ置換しない。'
        if quantity > need:
            note += f' 必要{need}個に対し{quantity}個購入の方が、確認した数量帯では安価。'
        note += ' ' + obs.get('note', '')
        price_label = f'{unit} {obs["currency"]}/個、{tier}個帯、税別'
        row.update(supplier='Mouser', mpn=obs['mpn'], pack=1, order_target=quantity,
                   buy_packs=quantity, purchased=quantity, spare=row['stock']+quantity-row['used'],
                   price_jpy_incl=str(price_incl), subtotal_jpy=money(price_incl*quantity),
                   url=obs['url'], availability=status,
                   evidence=f'2026-11-19 {obs["method"]}; {price_label}',
                   price_checked='2026-11-19', note=note.strip(),
                   source_currency=obs['currency'], source_unit_price_excl=str(unit),
                   stock_observed=obs['stock'], minimum_order=obs['minimum'], order_multiple=obs['multiple'],
                   stock_source_url=obs.get('stock_url',obs['url']), pack_source_url=obs.get('pack_url',obs['url']))
        changes.append(dict(id=row['id'], old_mpn=old['mpn'], new_mpn=row['mpn'], old_supplier=old['supplier'],
                            new_supplier='Mouser', old_subtotal_jpy=old['subtotal_jpy'], new_subtotal_jpy=row['subtotal_jpy'],
                            delta_jpy=money(D(row['subtotal_jpy'])-D(old['subtotal_jpy'])), quantity=quantity))
        table.append(dict(ID=row['id'], MPN=row['mpn'], 必要数=row['used'], 注文数=quantity,
                          掲載在庫=obs['stock'], 最低発注数=obs['minimum'], 発注倍数=obs['multiple'],
                          通貨=obs['currency'], 税別単価=str(unit), 適用数量帯=tier,
                          税込換算小計円=row['subtotal_jpy'], 取得方法=obs['method'], 収録時期=obs.get('crawled') or '',
                          価格URL=obs['url'], 在庫URL=obs.get('stock_url',obs['url']),
                          販売単位URL=obs.get('pack_url',obs['url']), 注意=row['note']))
    totals = {v: money(sum(D(r['subtotal_jpy']) for r in plan['rows'] if r['supplier']==v))
              for v in sorted({r['supplier'] for r in plan['rows']})}
    goods = sum(D(t) for t in totals.values())
    net = sum(D(r['source_unit_price_excl'])*r['purchased']*D(str(evidence['fx_budget_jpy'][r['source_currency']]))
              for r in plan['rows'] if r['id'] in expected)
    assert net > 6000  # conservative: qualify using tax-exclusive product subtotal
    plan.update(source='LC-H preserved plan / LC-F and LC-G unchanged', review='LC-I',
                status='catalog_estimate_3_backorders_fx_not_final_checkout',
                vendors=totals, parts_goods_jpy=money(goods), parts_freight_jpy=550,
                freight_by_vendor_jpy={'Akizuki':550,'Switch Science':0,'Mouser':0},
                mouser_freight_status='JPY one-order normal shipment >6000 before tax, conditional free shipping; confirm backorder handling in cart',
                reserve_jpy=2000, pending_price_ids=[], availability_flags=['U01','U10','U17'],
                fx_price_ids=[r['id'] for r in evidence['selected'] if r['currency']!='JPY'],
                scarce_ids=['C_2.2u'], baseline_total_jpy=baseline['total_jpy'],
                mouser_goods_excl_budget_jpy=money(net),
                source_fx_budget_jpy=evidence['fx_budget_jpy'],
                cart_checks=['U01/U10/U17 zero stock and delivery date; alternative packaging not reserved',
                             'Mouser JPY/DDP cart prices for converted USD/EUR rows and normal free shipping/backorder handling',
                             'C_2.2u Akizuki scarce stock inherited from H; not rechecked in this 43-row review',
                             'PCB final CAM/cart, OCS price, tax/customs differences use general reserve'])
    plan['total_jpy']=money(goods+plan['parts_freight_jpy']+D(plan['pcb_delivered_jpy'])+plan['reserve_jpy'])
    plan['budget_variance_jpy']=money(D(plan['total_jpy'])-plan['budget_jpy'])
    for filename, value in [('purchase-plan.json',plan),('changes.json',changes)]:
        (ROOT/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    with (ROOT/'mouser-43.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=table[0].keys());writer.writeheader();writer.writerows(table)
    with (ROOT/'mouser-order.csv').open('w',newline='') as f:
        writer=csv.writer(f);writer.writerow(['Manufacturer Part Number','Quantity','Customer Reference'])
        writer.writerows((r['MPN'],r['注文数'],r['ID']) for r in table)
    print(json.dumps({k:plan[k] for k in ['vendors','parts_goods_jpy','parts_freight_jpy','pcb_delivered_jpy','reserve_jpy','total_jpy','availability_flags']},ensure_ascii=False,indent=2))

if __name__=='__main__':
    build()
