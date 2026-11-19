# SPDX-License-Identifier: MIT
"""Verify procurement calculations, scope preservation and the unchanged F BOM."""
import csv, hashlib, json, math, sys
import zipfile, xml.etree.ElementTree as ET
from collections import Counter
from decimal import Decimal as D, ROUND_HALF_UP
from pathlib import Path

root=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[1]
cad=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else root.parent/'low-cost-ym3014-pcb-review-f'
p=json.loads((root/'purchase-plan.json').read_text())
h=json.loads((root/'baseline-plan.json').read_text())
obs=json.loads((root/'price-observations.json').read_text())
ids={'U01','U10','U17'}
assert ids=={r['id'] for r in obs['selected']}
overseas={r['id'] for r in h['rows'] if r['supplier']=='Mouser'}
assert len(overseas)==43
assert len(p['rows'])==len(h['rows'])==86
assert p['pcb_each']==5 and p['populated_sets']==1
for old,new in zip(h['rows'],p['rows']):
    assert (old['id'],old['refs'],old['used'],old['stock'])==(new['id'],new['refs'],new['used'],new['stock'])
    if old['id'] not in ids:assert old==new
    else:
        assert new['supplier']=='Mouser'
        expected={'U01':'SI5351A-B-GTR','U10':'SN74LV4T125QPWRQ1','U17':'SN74LVC1G32DBVRE4'}
        assert new['mpn']==expected[old['id']]
expected=[]
for board in ('base','module','panel'):
    with (cad/board/'bom.csv').open() as f: expected += [board+':'+r['Reference'] for r in csv.DictReader(f)]
actual=[ref for r in p['rows'] for ref in r['refs']]
assert Counter(actual)==Counter(expected) and len(actual)==len(set(actual))==277
with (root/'purchase-plan.csv').open() as f: exported=list(csv.DictReader(f))
assert len(exported)==86
totals={}
for r,c in zip(p['rows'],exported):
    assert r['id']==c['ID']
    assert r['buy_packs']==math.ceil(max(0,r['order_target']-r['stock'])/r['pack'])==int(c['包装数'])
    assert r['purchased']==r['buy_packs']*r['pack']==int(c['購入個数'])
    assert r['spare']==r['stock']+r['purchased']-r['used']==int(c['余り'])>=0
    subtotal=(D(r['price_jpy_incl'])*r['buy_packs']).quantize(D('.01'),rounding=ROUND_HALF_UP)
    assert subtotal==D(r['subtotal_jpy'])==D(c['小計円'])
    totals[r['supplier']]=totals.get(r['supplier'],D(0))+subtotal
assert {k:str(v) for k,v in totals.items()}==p['vendors']
assert 'DigiKey' not in totals and totals['Mouser']>6000
assert D(p['mouser_goods_excl_budget_jpy'])>6000
assert totals['Akizuki']==D(h['vendors']['Akizuki']) and totals['Switch Science']==D(h['vendors']['Switch Science'])
assert p['parts_freight_jpy']==sum(p['freight_by_vendor_jpy'].values())==550
assert D(p['total_jpy'])==sum(totals.values())+550+D(p['pcb_delivered_jpy'])+p['reserve_jpy']
assert D(p['pcb_delivered_jpy'])==(D(p['pcb_goods_usd'])+D(p['pcb_shipping_usd']))*p['budget_fx_jpy_per_usd']
assert p['availability_flags']==[r['id'] for r in obs['selected'] if r['stock']==0]==['U01']
assert len([r for r in obs['selected'] if r['stock']>0])==2
for o in obs['selected']:
    r=next(r for r in p['rows'] if r['id']==o['id'])
    q=r['purchased']
    tier=next(D(str(u)) for t,u in reversed(o['tiers']) if t<=q)
    assert D(r['source_unit_price_excl'])==tier
    assert D(r['price_jpy_incl'])==tier*D(str(obs['fx_budget_jpy'][o['currency']]))*D('1.10')
assert all(r['minimum']==r['multiple']==1 and r['tiers'] and r['url'].startswith('https://') for r in obs['selected'])
assert len(p['fx_price_ids'])==19
assert {r['id'] for r in p['rows'] if r.get('source_currency','JPY')!='JPY'}==set(p['fx_price_ids'])
with (root/'mouser-order.csv').open() as f: order=list(csv.DictReader(f))
assert len(order)==43 and {r['Customer Reference'] for r in order}==overseas
for r in order:assert int(r['Quantity'])==next(p for p in p['rows'] if p['id']==r['Customer Reference'])['purchased']
book=root/'local-output/outputs/review-j/purchase-plan.xlsx'
if book.exists():
    ns={'m':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(book) as z:
        sheets=ET.fromstring(z.read('xl/workbook.xml')).findall('m:sheets/m:sheet',ns)
        assert [s.attrib['name'] for s in sheets]==['Summary','Purchase']
        cells=ET.fromstring(z.read('xl/worksheets/sheet1.xml')).findall('.//m:c',ns)
        values={c.attrib['r']:c.find('m:v',ns).text for c in cells if c.find('m:v',ns) is not None}
        assert abs(D(values['B12'])-D(p['total_jpy']))<D('.0001')
        for file in ('xl/worksheets/sheet1.xml','xl/worksheets/sheet2.xml'):
            assert not any(c.attrib.get('t')=='e' for c in ET.fromstring(z.read(file)).findall('.//m:c',ns))
snapshot=root/'baseline-sha256.json'
if snapshot.exists():
    saved=json.loads(snapshot.read_text())
    for relative,digest in saved.items():assert hashlib.sha256((cad.parent/relative).read_bytes()).hexdigest()==digest,relative
module=json.loads((cad/'module/circuit.json').read_text())
parts={r['ref']:r for r in module['parts']}
for ref in ('U16','ULINK0','ULINK1'):
 r=parts[ref];pins={x['num']:x['net'] for x in r['pins']}
 assert r['footprint']=='Package_SO:TSSOP-14_4.4x5mm_P0.65mm' and pins['14']=='MCU_3V3' and pins['7']=='GND'
r=parts['UTXOR'];pins={x['num']:x['net'] for x in r['pins']}
assert r['footprint']=='Package_TO_SOT_SMD:SOT-23-5' and pins['5']=='MCU_3V3' and pins['3']=='GND'
option=json.loads((root/'stock-priority-option.json').read_text())
assert option['requires_pcb_revision'] and not option['pcb_changed']
assert D(option['total_before_crystal_deduction_jpy'])==D(p['total_jpy'])-D('412.94')+650
assert D(option['total_after_X01_deduction_jpy'])==D(option['total_before_crystal_deduction_jpy'])-D('95.04')
assert option['vendors']['Mouser']=='7498.92' and option['vendors']['Akizuki']=='8125.00'
for a,b in zip(p['rows'],option['rows']):
 if a['id']!='U01':assert a==b
assert D(p['total_jpy'])==D('27216.46') and D(p['total_jpy'])<p['budget_jpy']
print('PASS: 277 refs, 86 rows, 3 reviewed / 83 preserved, 43 Mouser rows, 2 alternatives / 1 zero, PCB pin checks, totals',p['total_jpy'],option['total_before_crystal_deduction_jpy'])
