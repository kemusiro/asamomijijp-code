#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only review B quantities, provenance, CAM and saved-workbook checks."""
from pathlib import Path
import argparse, csv, hashlib, json, math, zipfile
from build_order import capacitor_screen
H=Path(__file__).resolve().parents[1]
def read(p): return json.loads(p.read_text())
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def files(d): return {p.name:sha(p) for p in d.iterdir() if p.is_file()}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,default=H.parent);ap.add_argument('--outputs',type=Path);a=ap.parse_args();hw=a.hardware_root;p=read(H/'order-plan.json')
    assert p['selection']=='base4-module2' and p['procurement_review']=='B' and not p['order_placed']
    assert p['profile']['pcb_each']==5 and p['profile']['fitted_sets']==1
    for rel,digest in p['sources_sha256'].items(): assert sha(hw/rel)==digest,('Source changed',rel)
    for rel,digest in read(H/'manifest.json')['files'].items(): assert sha(H/rel)==digest,('Delivery changed',rel)
    old=read(hw/'primary-order-5pcb-1set/order-plan.json');oldrows={r['id']:r for r in old['rows']};changed=[]
    assert len(p['rows'])==90 and len({r['id'] for r in p['rows']})==90
    for r in p['rows']:
        before=oldrows[r['id']]
        if r!=before: changed.append(r['id'])
        for k in ['required_qty','used_qty','qty_base','qty_module','qty_shield','qty_external','spare','stock','refs']:
            assert r[k]==before[k],(r['id'],k)
        units=math.ceil(max(0,r['required_qty']+r['spare']-r['stock'])/r['pack_size']) if r['pack_size'] else None
        assert r['order_units']==units
        assert r['purchased_qty']==(units*r['pack_size'] if units is not None else None)
        assert r['remaining_qty']==(units*r['pack_size']+r['stock']-r['used_qty'] if units is not None else None)
    assert set(changed)=={'PCB1','J10','C14'}
    ids={r['id']:r for r in p['rows']};cap=ids['C14'];assert cap['mpn']=='GRM21BZ71C106KE15L' and cap['refs']==['base:CACL','base:CACR'] and cap['order_units']==2
    assert ids['J10']['supplier_code']=='C165948' and ids['J03']['order_units']==6 and ids['J03']['remaining_qty']==41
    assert len([r for r in p['rows'] if r['kind']!='PCB'])==87
    assert math.isclose(sum(r['known_subtotal_jpy'] or 0 for r in p['rows']),6413.2)
    assert sum(r['price_jpy'] is None for r in p['rows'])==59
    assert [(b['set'],b['layers'],b['quantity'],b['fitted'],b['spare']) for b in p['boards']]==[('base-l4',4,5,1,4),('module-k2',2,5,1,4),('shield-b2',2,5,1,4)]
    for b in p['boards']:
        src=hw/'clean-sheet-pcb-review-l/manufacturing/gerbers' if b['purchase_id']=='PCB1' else hw/'primary-order-5pcb-1set'/b['gerbers']
        dest=H/b['gerbers'];assert files(src)==files(dest)
        assert read(dest/(b['name']+'-job.gbrjob'))['GeneralSpecs']['LayerNumber']==b['layers']
    for name,expected in [('purchase-bom.csv',p['rows']),('akizuki-order.csv',[r for r in p['rows'] if r['supplier']=='秋月']),('other-suppliers.csv',[r for r in p['rows'] if r['supplier']!='秋月'])]:
        with (H/name).open() as f: rows=list(csv.DictReader(f))
        assert len(rows)==len(expected)
        for c,r in zip(rows,expected):
            for k,v in c.items(): assert v==('' if r[k] is None else str(r[k])),(r['id'],k)
    assert sha(H/'reference-map.csv')==sha(hw/'primary-order-5pcb-1set/reference-map.csv')
    v=read(H/'assembly-vias.json');assert sum(map(len,v['sites_by_board'].values()))==7
    oldv=read(hw/'primary-order-5pcb-1set/assembly-vias.json');assert v['sites_by_board']['base-l4']==oldv['sites_by_board']['base-j4']
    screen=read(H/'capacitor-screen.json');assert screen==capacitor_screen() and not screen['guaranteed_combined_minimum'] and not screen['physical_measurement_completed']
    assert 4.7<screen['screened_capacitance_uF']<5 and screen['largest_relative_loss_20hz_db']<.05
    fit=read(H/'fit-record.json');assert not fit['physical_checks_performed'] and all(r['status']=='pending' and r['measurement'] is None for r in fit['checks'])
    saved=read(H/'workbook-verification.json');check=read(H/'workbook-check.json')
    assert check['input_recalculation_checks']==7 and check['unpriced_rows']==59 and saved['saved_error_cells']==0 and saved['references']==274
    assert check['pcb_ordered']==15 and check['pcb_spare']==12
    if a.outputs:
        out=a.outputs
        for name,digest in read(H/'archive-manifest.json')['files'].items(): assert sha(out/name)==digest
        assert sha(out/'p2-primary-l4-k2-order.xlsx')==saved['workbook_sha256']
        for b in p['boards']:
            with zipfile.ZipFile(out/b['zip']) as z:
                assert z.testzip() is None and {n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist()}==files(H/b['gerbers'])
        with zipfile.ZipFile(out/'p2-primary-review-b-5pcb-1set.zip') as z:
            assert z.testzip() is None
            assert sorted(n for n in z.namelist() if n.endswith('-gerber.zip'))==sorted(b['zip'] for b in p['boards'])
            assert all('base-j4' not in n and 'base-k2' not in n for n in z.namelist())
            for b in p['boards']: assert z.read(b['zip'])==(out/b['zip']).read_bytes()
            for n in ['README.md','purchase-bom.csv','akizuki-order.csv','other-suppliers.csv','reference-map.csv','assembly-vias.json','order-plan.json','CAPACITOR.md','FIT-CHECK.md','capacitor-screen.json','fit-record.json','source-records.json']:
                assert z.read(n)==(H/n).read_bytes()
            assert z.read('p2-primary-l4-k2-order.xlsx')==(out/'p2-primary-l4-k2-order.xlsx').read_bytes()
    print('PASS: L4/K2/B2, 15 PCBs/1 fitted set, 90 BOM rows/274 refs, 85 unchanged components, C14 screen, pending physical fit, selected CAM and saved workbook')

if __name__=='__main__': main()
