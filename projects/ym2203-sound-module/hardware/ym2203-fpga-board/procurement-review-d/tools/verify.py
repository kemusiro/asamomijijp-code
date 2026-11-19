#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Validate price/quantity coverage, shipping assumptions, and immutable CAD inputs."""
from pathlib import Path
from decimal import Decimal
import hashlib, json
import re
from build_budget import calculate, outputs, units
P=Path(__file__).resolve().parents[1]; HW=P.parent
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    plan=read(P/'purchase-plan.json'); d=calculate(); rows={r['id']:r for r in d['parts_rows']}
    source=read(HW/'primary-order-review-b/order-plan.json')
    originals={r['id']:r for r in source['rows'] if not r['id'].startswith('PCB')}
    assert len(originals)==87 and len(rows)==96
    assert {c for r in rows.values() for c in r['covers']}==set(originals)
    assert plan['pcb_each']==5 and plan['fitted_sets']==1
    assert plan['assumptions']['ym2203_source']=='Rev Cから1個流用、ユーザー回答'
    assert not plan['assumptions']['new_hardware_acceptance'] and not plan['assumptions']['purchases_made']
    for r in rows.values():
        assert all(isinstance(r[k],int) and r[k]>0 for k in ['pack','minimum','multiple'])
        assert r['order_units']==0 or (r['order_units']>=r['minimum'] and r['order_units']%r['multiple']==0)
        assert r['stock']+r['purchased_units']>=r['required']+r['spare_target']
        assert r['remaining_units']>=0
        assert r['currency'] in ['JPY','USD'] and r['tax'] in ['included','excluded','import_excluded']
        assert r['price']>0 or (r['id']=='M03' and r['order_units']==0)
        assert r['stock']==(1 if r['id']=='M03' else 0)
        assert r['evidence'] and r['availability'] and r['checked']
        for cover in r['covers']: assert cover in originals
        if len(r['covers'])==1 and r['id'] in originals:
            old=originals[r['id']]
            assert r['original_mpn']==old['mpn']
            assert r['required']==old['required_qty']
    for id,expected in {'M03':(0,0,0),'J02':(128,128,0),'J03':(6,240,41),'H02':(50,50,46),
                        'H04':(1,10,2),'C01':(28,28,0),'C09':(2,2,0),'C06':(5,5,4),
                        'U14':(10,10,9),'D01':(20,20,18),'R07':(10,10,4),'QIPIN':(2,20,3)}.items():
        r=rows[id]; assert (r['order_units'],r['purchased_units'],r['remaining_units'])==expected
    assert units(0,1,20,20)==0 and units(21,1,20,20)==40 and units(22,10,1,1)==3
    assert Decimal(rows['R07']['line_goods'])==63
    assert rows['C01']['offered_mpn']=='C0805C104K5RACTU'
    assert rows['C09']['offered_mpn']=='C0805C222J5GACTU'
    boards={'base':HW/'clean-sheet-pcb-review-l/base/p2-base-l.kicad_pcb',
            'module':HW/'clean-sheet-pcb-review-k/module/p2-ym2203-k.kicad_pcb'}
    footprints={}
    for board,path in boards.items():
        for block in path.read_text().split('(footprint ')[1:]:
            ref=re.search(r'\(property "Reference" "([^"]+)"',block)
            if ref: footprints[board+':'+ref[1]]=block.splitlines()[0]
    for id in ['C01','C09']:
        for ref in originals[id]['refs']:
            assert 'Capacitor_SMD:C_0805_2012Metric' in footprints[ref],(id,ref)
    assert rows['QIPIN']['required']==2+9+6
    vendors={v['supplier']:v for v in d['vendors']}
    assert Decimal(vendors['LCSC']['goods'])==Decimal('5.09')
    assert Decimal(vendors['Waveshare']['goods'])==Decimal('5.99')
    assert Decimal(vendors['秋月']['gross'])<11000
    assert Decimal(vendors['マルツ']['gross'])/Decimal('1.1')>=3000
    assert Decimal(vendors['DigiKey']['goods'])>=6000
    assert Decimal(vendors['共立エレショップ']['gross'])<7500
    assert Decimal(vendors['モノタロウ']['gross'])/Decimal('1.1')<3500
    fre=read(P/'freight-observations.json')
    assert not fre['orders_placed'] and not fre['terms_accepted'] and not fre['postcode_or_address_entered']
    lc=fre['international'][1]
    assert Decimal(lc['goods_usd'])+Decimal(lc['fee_usd'])+Decimal(lc['handling_usd'])-Decimal(lc['display_discount_usd'])==Decimal(lc['display_total_usd'])
    for id,q in lc['items'].items(): assert next(r['order_units'] for r in rows.values() if r['sku']==id and r['supplier']=='LCSC')==q
    for name,expected in outputs().items(): assert (P/name).read_text()==expected,('stale output',name)
    for quote in d['pcb_comparison']:
        assert quote['pcb_delivered_jpy']+quote['parts_delivered_jpy']==quote['subtotal_jpy']
        assert quote['subtotal_jpy']+quote['reserve_jpy']==quote['with_reserve_jpy']
    assert sum(v['delivered_jpy'] for v in d['vendors'])==d['parts_delivered_jpy']
    lock=read(P/'source-lock.json')
    for name,expected in lock['files'].items(): assert sha(HW/name)==expected,('changed source',name)
    archives=read(HW/'primary-order-review-b/archive-manifest.json')['files']
    for name,expected in lock['fabrication_zip_sha256'].items(): assert archives[name]==expected
    for name,expected in read(P/'manifest.json')['files'].items(): assert sha(P/name)==expected
    for file in P.rglob('*'):
        if file.is_file() and '__pycache__' not in file.parts:
            text=file.read_text()
            if file.suffix!='.py': assert ('/'+'Users/') not in text
            assert all(line==line.rstrip() for line in text.splitlines()),file
    print('PASS: D; 87 original BOM lines covered by 96 purchasing lines, 18 former pending lines priced; quantities, sales packs, shipping, currency/tax separation and preserved B/C/CAD hashes verified')
if __name__=='__main__': main()
