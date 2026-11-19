#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Derive review B procurement from the preserved J4/K2/B2 order snapshot."""
from pathlib import Path
import argparse, copy, csv, hashlib, itertools, json, math, shutil

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p, data): p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')

def capacitor_screen():
    # Engineering assumptions and visually read typical curves; NOT guaranteed limits.
    ratio = 10000*1.01/(6810*.99+10000*1.01)
    vleft = 5.25*ratio
    dc = max(abs(a-b) for a in [0,vleft] for b in [1.5,1.8])
    factors = {'nominal_uF':10, 'tolerance':.9, 'dc_typical_read_down':.95,
               'small_signal_ac_typical_read_down':.70, 'temperature_design_allowance':.85,
               'additional_design_reserve_not_aging_spec':.95}
    c = math.prod(factors.values())
    corners=[]
    for ru,rd,rl,rs,rin in itertools.product([6810*.99,6810*1.01],[10000*.99,10000*1.01],
                                          [2200*.99,2200*1.01],[0,4700],[10000,20000,40000]):
        rth = 1/(1/(ru+rs)+1/rd)
        rt = rth+rl+rin
        fc = 1/(2*math.pi*rt*c*1e-6)
        corners.append({'source_ohm':rs, 'input_ohm':rin, 'series_equivalent_ohm':rt,
                        'fc_hz':fc, 'relative_loss_20hz_db':10*math.log10(1+(fc/20)**2),
                        'five_tau_seconds_at_15uF':5*rt*15e-6})
    assert dc<2 and c>4.7
    assert max(q['five_tau_seconds_at_15uF'] for q in corners)<4
    return {'kind':'engineering screening, not manufacturer minimum or bench acceptance',
            'mpn':'GRM21BZ71C106KE15L','refs':['base:CACL','base:CACR'],
            'source_dc_assumption_v':[0,5.25],'adc_avdd_assumption_v':[3,3.6],
            'adc_bias_model':'AVDD/2','normal_powered_max_abs_cap_dc_v':dc,
            'unpowered_adc_left_node_bound_v':vleft,'dc_curve_screen_v':2,
            'source_resistance_assumption_ohm':[0,4700],
            'adc_input_resistance_screen_ohm':[10000,40000],
            'adc_input_resistance_manufacturer_typical_ohm':20000,
            'factors':factors,'screened_capacitance_uF':c,
            'largest_fc_hz':max(q['fc_hz'] for q in corners),
            'largest_relative_loss_20hz_db':max(q['relative_loss_20hz_db'] for q in corners),
            'largest_five_tau_seconds_at_15uF':max(q['five_tau_seconds_at_15uF'] for q in corners),
            'initial_muted_settling_candidate_seconds':4,
            'guaranteed_combined_minimum':False,'physical_measurement_completed':False,
            'notes':['DC/AC curves are typical and measured separately; their multiplication is a selection heuristic.',
                     '0.85 temperature factor is a design allowance, not independent Z7 guarantee at every bias.',
                     '0.95 reserve is not manufacturer aging or service-life data.',
                     'Input resistance 10..40k and maximum effective C 15uF are screening assumptions, not TI limits.',
                     'No hotplug, negative source DC or externally powered input qualification is claimed.'],
            'corners':corners}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--hardware-root',type=Path,default=Path(__file__).resolve().parents[2]);ap.add_argument('--output',type=Path,default=Path(__file__).resolve().parents[1]);a=ap.parse_args()
    h=a.hardware_root.resolve();o=a.output.resolve();o.mkdir(parents=True,exist_ok=True)
    prior=h/'primary-order-5pcb-1set';p=copy.deepcopy(json.loads((prior/'order-plan.json').read_text()));rows=p['rows']
    for r in rows:
        if r['id']=='PCB1':
            r.update(name='ベースL・4層製作基板',mpn='p2-base-l',fabrication_set='base-l4',gerber_zip='p2-base-l4-gerber.zip',
                     note='USB-CをC165948の2020-12-08図面へ修正済み。各5枚を1ロット発注、1枚実装・4枚予備。ENIG・外層/内層1oz。旧Jの価格は参考のみ、新Gerberの確定カート見積は未取得。')
        if r['id']=='J10':
            r.update(supplier_code='C165948',url='https://www.lcsc.com/product-detail/C165948.html',
                     source='https://datasheet.lcsc.com/datasheet/pdf/9e56b777c022540fcce7c7f67825f55e.pdf?productCode=C165948',
                     checked='2026-11-19',selection='指定型番・図面2020-12-08',
                     note='HRO TYPE-C-31-M-12 / C165948。16接点・信号は12か所のはんだ付け。ベースL推奨ランド照合済み。別版図面やUSB変換モジュールを代用しない。価格・在庫・販売単位と実物適合は発注時確認。')
        if r['id']=='C14':
            r.update(mpn='GRM21BZ71C106KE15L',package='2012 / 0805 / 10uF16V ±10% X7R(Murata)',
                     supplier_code='490-GRM21BZ71C106KE15LCT-ND',
                     url='https://www.digikey.jp/ja/products/detail/murata-electronics/GRM21BZ71C106KE15L/16602141',
                     source='https://www.farnell.com/datasheets/4127428.pdf',
                     note='ベースCACL/CACR。DC/小信号ACの代表曲線による試作採用、複合条件実測は未確認。CTを2個、Digi-Reel/3000個リール不要。在庫0、2026-11-24入荷表示は予定。税込表示61.60円/個、2個123.20円は表示価格による試算。仕様・代替店はCAPACITOR.md。',
                     availability='在庫0・入荷予定2026-11-24（未保証）',checked='2026-11-19',
                     selection='試作採用・複合条件実測未確認',pack_size=1,pack_verified=True,
                     price_jpy=61.6,order_units=2,purchased_qty=2,remaining_qty=0,known_subtotal_jpy=123.2)
    b=p['boards'][0];b.update(set='base-l4',name='p2-base-l',cad='clean-sheet-pcb-review-l/base/p2-base-l.kicad_pcb',gerbers='gerbers/base-l4',zip='p2-base-l4-gerber.zip')
    for b in p['boards']:
        src=h/'clean-sheet-pcb-review-l/manufacturing/gerbers' if b['purchase_id']=='PCB1' else prior/b['gerbers']
        shutil.copytree(src,o/b['gerbers'],dirs_exist_ok=True)
    parts=[r for r in rows if r['kind']!='PCB'];known=round(sum(r['known_subtotal_jpy'] or 0 for r in parts),2)
    p.update(checked='2026-11-19',procurement_review='B',known_parts_subtotal_jpy=known,
             parts_prices_researched_this_task=['C14'],parts_quantities_preserved=True,
             changed_rows=['PCB1','J10','C14'],new_gerber_cart_quote_obtained=False,
             sources_sha256={f'primary-order-5pcb-1set/{n}':sha(prior/n) for n in ['order-plan.json','reference-map.csv','assembly-vias.json','manifest.json']},
             quote_source='../manufacturing-review-k/procurement/comparison.json (historical J, not a quote for L)')
    for rel in ['clean-sheet-pcb-review-l/manifest.json','clean-sheet-pcb-review-l/manufacturing/cam-verification.json']:
        p['sources_sha256'][rel]=sha(h/rel)
    assert len(rows)==90 and len(parts)==87 and known==6413.2
    write(o/'order-plan.json',p)
    fields=['id','name','mpn','kind','supplier','supplier_code','required_qty','used_qty','unit','pack_size','pack_verified','stock','spare','order_units','purchased_qty','remaining_qty','price_jpy','known_subtotal_jpy','availability','selection','checked','url','source','note','fabrication_set','gerber_zip']
    for name,items in [('purchase-bom.csv',rows),('akizuki-order.csv',[r for r in rows if r['supplier']=='秋月']),('other-suppliers.csv',[r for r in rows if r['supplier']!='秋月'])]:
        with (o/name).open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore',lineterminator='\n');w.writeheader();w.writerows(items)
    shutil.copy2(prior/'reference-map.csv',o/'reference-map.csv')
    vias=json.loads((prior/'assembly-vias.json').read_text());vias['sites_by_board']['base-l4']=vias['sites_by_board'].pop('base-j4');write(o/'assembly-vias.json',vias)
    write(o/'capacitor-screen.json',capacitor_screen())
    write(o/'source-records.json',{'checked':'2026-11-19','sources':[
        {'url':'https://www.farnell.com/datasheets/4127428.pdf','document':'Murata Product Search Data Sheet, 4 pages, 2024-01-10, typical data',
         'sha256':'d110982b7921d9f755fe858e28fb6a0a7298e104d7d84b34d80c8a24a20d0506','visual_review':'specifications page 2; DC and AC curves page 3',
         'limitations':'Not the latest approval sheet. Murata PIM link returned 403. Approximate chart readings are not guaranteed limits.'},
        {'url':'https://www.ti.com/lit/ds/symlink/pcm1863.pdf','document':'TI SLAS831D, 2018-03, 7.3 / 9.3.1; AVDD/2 bias and 20k typical input'},
        {'url':next(r['url'] for r in rows if r['id']=='C14'),'observed':'CT 1-piece tier JPY56 ex tax /61.60 displayed incl tax, stock0, expected2026-11-24; final cart not obtained'},
        {'url':'https://www.lcsc.com/product-detail/C162430.html','observed':'Exact MPN alternate listing; stock, price and minimum quantity not confirmed'}]})
    print('PASS: L4/K2/B2 order; 90 rows, 85 unchanged component rows; C14 screen %.6fuF; entered-price subtotal %.2f JPY'%(capacitor_screen()['screened_capacitance_uF'],known))

if __name__=='__main__': main()
