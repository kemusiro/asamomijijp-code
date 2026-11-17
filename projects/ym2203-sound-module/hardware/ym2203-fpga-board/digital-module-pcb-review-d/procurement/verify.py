#!/usr/bin/env python3
"""Validate purchase coverage against the unchanged review-D electrical BOMs."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path


def verify(folder, design):
    data = json.loads((folder / 'catalog.json').read_text())
    rows = data['rows']
    by_id = {r['id']: r for r in rows}
    assert len(by_id) == len(rows) == 80
    expected = {}
    for board in ('base', 'module'):
        p = design / board / 'bom.csv'
        assert hashlib.sha256(p.read_bytes()).hexdigest() == data['source_bom_sha256'][f'{board}/bom.csv']
        for row in csv.DictReader(p.open()):
            expected[(board, row['Reference'])] = row
    actual = {(r['board'], r['reference']): r for r in data['implementation']}
    assert len(actual) == len(data['implementation']) == len(expected) == 292
    for key, row in expected.items():
        assert actual[key]['value'] == row['Value']
        assert actual[key]['footprint'] == row['Footprint']
        assert set(actual[key]['purchase_ids']) <= set(by_id)
        if not actual[key]['purchase_ids']:
            assert row['Footprint'].startswith(('Jumper:', 'TestPoint:'))
            assert actual[key]['reason']
    assert sum(not r['purchase_ids'] for r in actual.values()) == 8
    assert all(r['qty_one'] > 0 for r in rows)
    for row in rows:
        assert row['qty_one'] == sum(row[k] for k in ('qty_base', 'qty_module', 'qty_external'))
        assert row['qty_five'] == row['qty_one'] * 5
        assert row['pack_size'] >= 1
        for sets, suffix in ((1, 'one'), (5, 'five')):
            assert row[f'order_units_{suffix}'] == math.ceil(sets * row['qty_one'] / row['pack_size'])
        assert row['url'].startswith('https://')
    # Independent counts protect expansion of logical sockets and joined values.
    counts = {'M01': 1, 'M02': 1, 'M03': 1, 'J01': 1, 'J02': 128, 'J03': 150,
              'J06': 2, 'J07': 1, 'J08': 1, 'J09': 1, 'S01': 6, 'LED01': 7,
              'U04': 2, 'U07': 2, 'U09': 6, 'U10': 7, 'U11': 2, 'U13': 2,
              'R01': 34, 'R02': 40, 'R03': 10, 'R13': 6,
              'C01': 43, 'C02': 9, 'C03': 5, 'C04': 2, 'C05': 5, 'C13': 4}
    for key, count in counts.items():
        assert by_id[key]['qty_one'] == count, key
    assert by_id['J03']['qty_base'] == 18
    assert by_id['J03']['qty_module'] == 4
    assert by_id['J03']['qty_external'] == 128
    assert by_id['J03']['order_units_one'] == 4
    assert by_id['J03']['order_units_five'] == 19
    assert by_id['J01']['order_units_one'] == 1  # ten sockets, not ten packs
    assert by_id['S01']['mpn'] == 'SKHHALA010'  # H4.3, not SKHHARA010 H5.0
    assert by_id['U05']['mpn'] == 'CD74HC4053M'
    assert by_id['D01']['mpn'] == 'BAT54S,215'
    assert by_id['F01']['mpn'] == 'MF-MSMF150/16X-2'
    # CSV is a consumable purchasing artifact and must match every catalog row.
    purchase_csv = list(csv.DictReader((folder / 'purchasing-bom.csv').open(encoding='utf-8-sig')))
    assert len(purchase_csv) == 80
    for row in purchase_csv:
        original = by_id[row['id']]
        assert row['mpn'] == original['mpn']
        assert int(row['qty_one']) == original['qty_one']
        assert int(row['order_units_five']) == original['order_units_five']
    result = dict(result='PASS', revision=data['revision'], purchase_rows=80,
                  implementation_refs=292, base_refs=147, module_refs=145,
                  no_buy_refs=8, akizuki_rows=sum(r['supplier'] == '秋月' for r in rows),
                  electrical_boms_unchanged=True, bench_acceptance=False,
                  package_quantities_unverified=sum(not r['pack_verified'] for r in rows))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--design-root', type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    result = verify(Path(__file__).resolve().parent, args.design_root)
    report = json.dumps(result, ensure_ascii=False, indent=2) + '\n'
    if args.output:
        args.output.write_text(report)
    print(report, end='')
