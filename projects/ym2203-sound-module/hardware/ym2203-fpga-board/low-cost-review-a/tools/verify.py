#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Check concept invariants and arithmetic, without CAD or bench acceptance."""
from pathlib import Path
from decimal import Decimal
import hashlib,json,sys
from build import calculate,outputs
P=Path(__file__).resolve().parents[1];HW=P.parent
def read(path):return json.loads(path.read_text())
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    p=read(P/'plan.json');g=read(HW/'clean-sheet-interface-review-g/gpio-proposal.json');s=read(HW/'clean-sheet-schematic-review-h/source-pins.json')
    assert p['current_design_preserved'] and not p['active_plan_changed']
    assert not p['compatibility']['firmware_applied'] and not p['compatibility']['bench_tested']
    assert not p['compatibility']['gpio_numbers_changed'] and not p['compatibility']['wire_protocol_changed']
    for old,new in [(g['base'],p['base_gpio']),(s['gpio'],p['sound_gpio'])]:
        assert [(r['gpio'],r['net'],r['function']) for r in old]==[(r['gpio'],r['net'],r['function']) for r in new]
        assert len({r['gpio'] for r in new})==len(new)
    assert len(p['base_gpio'])==44 and len(p['sound_gpio'])==28
    assert p['mcu']['edge_pin_count']==56 and len(p['mcu']['gpio_to_manufacturer_terminal'])==48
    assert len(set(p['mcu']['gpio_to_manufacturer_terminal'].values()))==48
    for gpio,terminal in [('24','JP7.2'),('25','JP7.3'),('47','J2.18')]:assert p['mcu']['gpio_to_manufacturer_terminal'][gpio]==terminal
    assert p['mcu']['reset']['edge_terminal'] is None and p['mcu']['reset']['must_not_replace_with_software_stop_only']
    assert set(p['mcu']['led_removal_candidate'])=={'R5 on GP24','R6 on GP25'}
    assert p['mcu']['flash']['product_page_mbit']==32 and not p['mcu']['flash']['verified_capacity']
    assert p['manufacturing']['min_via_drill_mm']==0.3 and p['manufacturing']['preferred_via_pad_mm']==0.6
    for key in ['via_in_pad','epoxy_fill','castellations_on_carrier']:assert not p['manufacturing'][key]
    panel=read(P/'panel-connector.json');new={r['signal']:r['gpio'] for r in panel['pins'] if r['gpio'] is not None}
    old={r['shield_net']:r['gpio'] for r in read(HW/'editor-shield-review-b/pins.json') if r['gpio'] is not None}
    old.update(SDA=42,SCL=43)
    assert new==old and len(new)==20
    assert len(panel['pins'])==40 and [r['pin'] for r in panel['pins']]==list(range(1,41))
    assert panel['interface_voltage']==3.3 and panel['cable_mm']==152
    host=p['compatibility']['host'];assert (host['signature'],host['address'],host['frequency_hz'],host['lease_ms'])==('YM22S002',66,100000,1000)
    assert (host['request_max'],host['status_bytes'],host['events_per_push'],host['queue_events'])==(208,64,32,1024)
    checks=0
    for board in p['boards']:
        w,h=board['size_mm']
        for label,x,y,bw,bh in board['blocks']:assert x>=0 and y>=0 and x+bw<=w and y+bh<=h,(board['id'],label)
        for i,a in enumerate(board['blocks']):
            for b in board['blocks'][i+1:]:
                assert a[1]+a[3]<=b[1] or b[1]+b[3]<=a[1] or a[2]+a[4]<=b[2] or b[2]+b[4]<=a[2],(a[0],b[0])
                checks+=1
    base_g=p['boards'][0]['blocks'][-1];sound_g=p['boards'][1]['blocks'][-1]
    assert (base_g[1],base_g[2])==(sound_g[1],sound_g[2]+20)
    q=read(P/'pcb-price-observations.json');assert not q['coupon_or_desktop_discount_used'] and q['new_quote_not_cam_approval']
    for b in q['boards']+[q['fallback_base']]:assert sum(Decimal(v) for v in b['detail'].values())==Decimal(b['price_usd'])
    assert sum(Decimal(b['price_usd']) for b in q['boards'])==Decimal('23.90')
    data=calculate();assert data['area']=={'old_mm2_per_set':48840,'target_mm2_per_set':25600,'reduction_percent':47.6}
    assert [r['rounded_budget_jpy'] for r in data['scenarios']]==[45000,50000,55000]
    assert data['scenarios'][0]['parts_goods_jpy']==23677
    for r in data['scenarios']:
        assert r['parts_goods_jpy']+r['pcb_goods_jpy']+r['parts_freight_allowance_jpy']+r['pcb_freight_allowance_jpy']==r['subtotal_jpy']
        assert r['subtotal_jpy']+r['reserve_jpy']==r['with_reserve_jpy']
    for name,expected in outputs().items():assert (P/name).read_text()==expected,('stale',name)
    for name,expected in read(P/'source-lock.json')['files'].items():assert sha(HW/name)==expected,('preserved file changed',name)
    for name,expected in read(P/'manifest.json')['files'].items():assert sha(P/name)==expected
    for f in P.rglob('*'):
        if not f.is_file() or '__pycache__' in f.parts:continue
        txt=f.read_text();assert all(x==x.rstrip() for x in txt.splitlines()),f
        if f.suffix!='.py':assert ('/'+'Users/') not in txt
    result={'result':'PASS','scope':'static concept/price/identity checks only','unchanged_base_gpio':44,'unchanged_source_gpio':28,
            'panel_gpio_preserved':20,'envelope_pairs_checked':checks,'budget_targets_jpy':[45000,50000,55000],
            'cad_erc_drc_run':False,'hardware_accepted':False,'firmware_implemented':False,'old_design_hashes_unchanged':True,
            'adoption_gates':['RUN breakout','LED load isolation','JEDEC and flash','thermal and solder/mating fit','detailed0.3mm-via routing','protocol and audio hardware regression']}
    if '--record' in sys.argv:(P/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    else:assert read(P/'verification.json')==result
    print(json.dumps(result,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
