#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Derive sales-unit arithmetic and a readable research matrix, without repricing B."""
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
import argparse
import json
import math

HERE = Path(__file__).resolve().parents[1]


def read(path):
    return json.loads(path.read_text())


def order_units(required, minimum, multiple, pack):
    if minimum is None:
        return None
    if required <= 0:
        return 0
    return math.ceil(max(math.ceil(required / pack), minimum) / multiple) * multiple


def calculated(root):
    records = read(root / 'parts-observations.json')['rows']
    result = []
    for record in records:
        units = order_units(record['required_qty'], record['minimum_sales_units'],
                            record['multiple_sales_units'], record['pieces_per_sales_unit'])
        bought = units * record['pieces_per_sales_unit'] if units is not None else None
        price = record['price_per_sales_unit']
        total = str(Decimal(str(price)) * units) if price is not None and units is not None else None
        result.append(dict(id=record['id'], required=record['required_qty'], sales_units=units,
                           purchased_pieces=bought, remaining=bought - record['used_qty'] if bought is not None else None,
                           line_goods_reference=total, currency=record['currency'],
                           not_an_order=True, availability_confirmed_for_checkout=False))
    return result


def report(root, computed):
    data = read(root / 'parts-observations.json')
    indexed = {row['id']: row for row in computed}
    lines = ['# 部品調達確認表 review C', '',
             '2026-11-19。購入資料Bの販売単位未確認56行と、C14の同一型番の別調達先を対象にした57行。',
             '「単位確認」は購入可能・在庫確保・代替採用を意味しない。索引価格は当日価格の保証ではない。',
             '旧CSV/Excelは保存記録のまま。この表とJSONが追加調査の正本であり、未確認項目へ値1や価格0を補わない。', '',
             '| ID | 元の指定／候補 | 必要 | 店・販売コード | 販売条件 | 計算上の購入／余り | 価格条件 | 入手状況・残る確認 |',
             '| --- | --- | ---: | --- | --- | --- | --- | --- |']
    for row in data['rows']:
        calc = indexed[row['id']]
        unit = (f"{row['pieces_per_sales_unit']}個/販売単位、最小{row['minimum_sales_units']}単位、倍数{row['multiple_sales_units']}単位"
                if row['unit_confirmed'] else '最小数/倍数/入数は未確定')
        count = (f"{calc['sales_units']}単位={calc['purchased_pieces']}個／余{calc['remaining']}個"
                 if calc['sales_units'] is not None else '未確定')
        price = (f"{row['price_per_sales_unit']} {row['currency']}/販売単位、{row['tax_basis']}"
                 if row['price_per_sales_unit'] is not None else '未確定')
        source = f"[{row['supplier_sku'] or row['supplier']}]({row['url']})" if row['url'] else row['supplier']
        mpn = row['original_mpn']
        if row['offered_mpn'] != mpn:
            mpn += ' →候補 ' + row['offered_mpn']
        qualifier = '候補・未採用。' if row['selection'] == 'candidate_not_adopted' else ''
        lines.append(f"| {row['id']} | {mpn} | {row['required_qty']} | {row['supplier']} {source} | {unit} | {count} | {price} | {qualifier}{row['stock_observation']}。{row['note']} |")
    confirmed = sum(r['unit_confirmed'] for r in data['rows'])
    originally_unresolved = [r for r in data['rows'] if r['id'] != 'C14']
    count_b = sum(r['unit_confirmed'] for r in originally_unresolved)
    lines += ['', f'販売条件を確認できた行は対象57行中{confirmed}行（元の未確認56行中{count_b}行）。',
              '販売単位が判明していても、在庫0・取寄・海外送料未確定・候補未採用の行は発注確定ではない。',
              '', '## 数量計算の読み方', '',
              '- まず必要個数を販売単位の入数で切り上げ、最低販売数以上・販売倍数の次の整数倍へ切り上げる。',
              '- J10は5単位×1個、H03は3単位×10本。どちらも「5個入りの袋」と解釈しない。',
              '- 製造元標準リール数と、代理店のカットテープ最小数を区別する。PK-01-06のwheelも販売入数確認までは空欄。',
              '- 候補品の購入数は比較用の計算に限る。H02は50個必要という意味ではなくMOQのため余剰46個が出る。',
              '- 手持ち数量は全て従来どおり0。実際に確認した在庫だけを将来控除する。',
              '- 商品代参照額は税・通貨・段階単価が混在するため、57行を足して全体総額とはしない。', '']
    return '\n'.join(lines)


def pcb_report(root):
    quote = read(root / 'pcb-quotes.json')
    fx = Decimal(str(quote['jpy_per_usd_assumption']))
    lines = ['# L4/K2/B2 各5枚の製造・送料比較 review C', '',
             '2026-11-19、匿名の入力式計算機で再確認。Gerberのアップロード・実カート・CAM審査・注文は未実施。',
             '比較するのはベースL 220×142mm/4層、音源K 100×100mm/2層、開口なしシールドB 76×100mm/2層、各5枚。',
             '厚み1.6mm、ENIG 1µinch、外層1oz、ベース内層1oz、緑/白。PCBA・ステンシル・樹脂充填なし。',
             '材料は各社の標準選択が異なる。重量/梱包を同じと仮定した厳密同条件の確定見積ではない。', '',
             '| 業者 | ベース5枚 | 音源5枚 | シールド5枚 | 製造計 | 配送 | 送料 | 製造＋送料 | 円参考 |',
             '| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: | ---: |']
    result = []
    for vendor in quote['vendors']:
        prices = [Decimal(str(x)) for x in vendor['board_prices']]
        manufacture = sum(prices)
        for freight in vendor['freight']:
            total = manufacture + Decimal(str(freight['usd']))
            jpy = int((total * fx).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            lines.append('| ' + ' | '.join([vendor['name']] + [f'{v:.2f}' for v in prices] +
                         [f'{manufacture:.2f}',freight['service'],f"{freight['usd']:.2f}",f'{total:.2f}',f'{jpy:,}円']) + ' |')
            result.append(dict(vendor=vendor['name'], service=freight['service'], manufacture_usd=str(manufacture),
                               freight_usd=str(freight['usd']), total_usd=str(total), reference_jpy=jpy))
    lines += ['', 'USD表示。円換算は**1 USD=160円を置いた比較用仮定**であり、現在の為替やカード決済レートではない。',
              '輸入税・通関立替料・カード手数料・部品代/部品送料は含まない。配送先は日本の選択までで、郵便番号別の追加料は未検証。', '',
              '## 送料の算出範囲', '',
              '- [JLCPCB製造計算機](https://cart.jlcpcb.com/quote)で基板別に入力。表示重量0.66+0.29+0.25=1.20kg。',
              '  [送料計算機](https://jlcpcb.com/shipping)では梱包余裕を持ち1.30kg・日本を指定。UPS 9.69 USD、DHL 21.60 USD、OCS 10.09 USD。',
              '  3種類の同梱カートは未作成。無償表示でも重量/寸法対象外のOCS NEP/FICPは採用しない。',
              '- [PCBWay計算機](https://www.pcbway.com/orderonline.aspx)で3基板を個別算出。送料だけは総面積244200mm²相当の220×222mm×5枚を使い、表示0.85kgで確認。',
              '  SF 18.51 USD、DHL 25.18 USD、FedEx-IP 19.83 USD。**220×222mmを製造発注するわけではない**。3ロット同梱の確定重量は未確認。',
              '  Email deliveryの0 USD、商品90/80 USD以下に限定される配送は比較から除外。',
              '- 上記は本日Lの寸法・穴径で入力し直した観測。過去のJ見積の単なるラベル変更ではない。ただしGerber由来の工場追加費はまだ反映されない。',
              '', '## 製造条件と残る確認', '',
              '- JLC：ベースTG155、音源KB6165F-TG155、シールドTG135。0.2mm穴のベース/音源には小径穴・Kelvin検査等の加算あり。',
              '- PCBWay：S1000H TG150、ベース/音源5/5mil・0.2mm穴、シールド6/6mil・0.3mm穴。',
              '- JLCのPluggedはソルダーマスク処理であり樹脂充填ではない。7か所の手埋めビア条件を除去した見積ではない。',
              '- 標準製造日数はJLCベース/音源3〜4日・シールド3日、PCBWayベース4〜5日・音源/シールド3〜4日。輸送日数は別。',
              '- 製造ZIPのSHAはsource-lock.jsonで結び付けた。入稿前に個別ZIPを使い、合本ZIPをパネルとして発注しない。',
              '- 最終額は各社へ3ZIPを個別指定した同梱カートとCAM審査で確定させる。今回の金額に発注保証はない。', '']
    return '\n'.join(lines), result


def outputs(root):
    computed = calculated(root)
    pcbs, totals = pcb_report(root)
    return {'parts-calculated.json':json.dumps(computed,ensure_ascii=False,indent=2)+'\n',
            'comparison.json':json.dumps(totals,ensure_ascii=False,indent=2)+'\n',
            'PARTS.md':report(root,computed), 'PCB-QUOTES.md':pcbs}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--check',action='store_true')
    args = parser.parse_args()
    for name, value in outputs(HERE).items():
        path = HERE / name
        if args.check:
            assert path.read_text() == value, name
        else:
            path.write_text(value)
    print('PASS: procurement C derived reports' if args.check else 'Generated procurement C derived reports')


if __name__ == '__main__':
    main()
