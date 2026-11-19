#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Independent net-contract/quantity audit on native exported schematics."""
from pathlib import Path
from decimal import Decimal
import json,hashlib,math,sys
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent
def read(p):return json.loads(p.read_text())
def main():
    circuits={b:read(HERE/b/'circuit.json') for b in ['base','module','panel']}
    by={b:{p['ref']:p for p in d['parts']} for b,d in circuits.items()}
    def net(board,ref,num):return next(p['net'] for p in by[board][ref]['pins'] if p['num']==str(num))
    def expected(board,ref,num,n):assert net(board,ref,num)==n,(board,ref,num,n)
    g=read(ROOT/'low-cost-review-b/gpio-proposal.json')
    for b,ref,roles in [('base','UBASE',g['base_compact']),('panel','UPICO',g['panel'])]:
        actual={int(p['name'][2:]):p['net'] for p in by[b][ref]['pins'] if p['name'].startswith('GP') and p['net'] is not None}
        assert actual=={p['gpio']:p['net'] for p in roles},b
    src=read(ROOT/'clean-sheet-schematic-review-h/source-pins.json')['gpio']
    actual={int(p['name'][2:]):p['net'] for p in by['module']['USOURCE']['pins'] if p['name'].startswith('GP') and p['net'] is not None}
    assert actual=={p['gpio']:p['net'] for p in src}
    assert len(by['base']['UBASE']['pins'])==40
    assert len(by['panel']['UPICO']['pins'])==40
    expected('base','UBASE','J1.18','RUN_N')
    expected('base','UBASE','J1.19','GND')
    expected('base','UBASE','J2.19','V5_CARRIER')
    # Complete Picossci2B edge/debuginventory; J2.10 is GND, NOT GPIO40.
    m=by['module']['USOURCE']
    for gp in range(48):
        pad=(f'J1.{gp+4}' if gp<17 else f'JP6.{gp-16}' if gp<24 else f'JP7.{gp-22}' if gp<31 else f'J2.{gp-30+(gp>=40)}')
        p=next(x for x in m['pins'] if x['num']==pad)
        assert p['name']==f'GP{gp}',(gp,pad)
    expected('module','USOURCE','J2.10','GND')
    expected('module','USOURCE','SW1.S','CORE_RUN_N')
    for board,pins in by.items():
        assert len(pins)==len(circuits[board]['parts'])
        for p in pins.values():assert len({n['num'] for n in p['pins']})==len(p['pins'])
    # Native JSON and XML relationship is checked by generate.py; independently check ERC.
    native=read(HERE/'native-verification.json')
    assert native['kicad_version']=='10.0.5'
    for b in circuits:
        violations=[v for sh in read(HERE/b/'erc.json')['sheets'] for v in sh['violations']]
        assert not violations,(b,violations)
        assert native['boards'][b]['components']==len(by[b])
    old=read(ROOT/'clean-sheet-schematic-review-h/connector.json')
    for board in ['base','module']:
        for p in old['pins']:
            n=p[board+'_net']
            if board=='base':n={'PANEL_SDA':'SERVICE_SDA','PANEL_SCL':'SERVICE_SCL'}.get(n,n)
            expected(board,'JMOD',p['pin'],n)
    expected('base','UBASE','J2.7','HOST_SDA');expected('base','UBASE','J2.8','HOST_SCL')
    expected('base','UBASE','J2.10','BASE_STOP_N');expected('base','SWSTOP',1,'BASE_STOP_N')
    expected('base','UPANEL',25,None)
    expected('base','UMUTE',1,'M_DAC_ALLOW');expected('base','UMUTE',2,'M_LINE_ALLOW')
    expected('base','UMUTE',4,'DAC_XSMT');expected('base','U17',17,'DAC_XSMT')
    for r,n in [('RPDAC','M_DAC_ALLOW'),('RPLINE','M_LINE_ALLOW'),('RBEN','MOD_ENABLE')]:
        expected('base',r,1,n);expected('base',r,2,'GND')
    expected('module','URUNOD',2,'L_MOD_ENABLE');expected('module','URUNOD',4,'CORE_RUN_N')
    assert not any(p['ref'].startswith('JUNO') for p in by['base'].values())
    for board in ['base','module']:
        for p in by[board].values():
            assert not any((n['net'] or '').startswith('EXT_') for n in p['pins']) or p['ref'] in ['JPOWER','F1','C1','C2']
    # Two independent I2C links and local EEPROM bus, no added uplink pullups at panel.
    expected('base','JEDIT',1,'SERVICE_SCL');expected('base','JEDIT',2,'SERVICE_SDA')
    expected('base','JEDIT',3,'V3_AUX');expected('base','JEDIT',4,'GND')
    expected('panel','JUPLINK',1,'UPLINK_SCL');expected('panel','JUPLINK',2,'UPLINK_SDA')
    expected('panel','JUPLINK',3,'UPLINK_3V3');expected('panel','JUPLINK',4,'GND')
    expected('panel','UPICO',1,'UPLINK_SDA');expected('panel','UPICO',2,'UPLINK_SCL')
    expected('panel','UPICO',4,'EEPROM_SDA');expected('panel','UPICO',5,'EEPROM_SCL')
    expected('panel','U1',5,'EEPROM_SDA');expected('panel','U1',6,'EEPROM_SCL')
    for pinno,n in [(3,'KNOB_ADC'),(10,'MUX_B'),(11,'MUX_A'),(13,'KNOB1_ADC'),(14,'KNOB2_ADC'),(15,'KNOB3_ADC'),(12,'KNOB4_ADC')]:expected('panel','UMUX',pinno,n)
    for n in [6,7,8,9]:expected('panel','UMUX',n,'GND')
    expected('panel','DPOWER',2,'UPLINK_3V3');expected('panel','DPOWER',1,'PANEL_VSYS')
    expected('panel','UPICO',39,'PANEL_VSYS');expected('panel','UPICO',36,'PANEL_3V3')
    assert set(p['net'] for p in by['base']['JUSB']['pins'])=={'USB_VBUS_RAW','USB_DP','USB_DM','GND'}
    assert 'RCC1' not in by['base'] and 'RCC2' not in by['base']
    assert by['base']['URXDATA']['value']=='TC7SZ125F,LJ(CT'
    for n,v in [(1,'GND'),(2,'AV3V3'),(3,'ADC_L')]:expected('base','DCLAMPL',n,v)
    assert Decimal('10')*(1-Decimal('.2'))>=Decimal('4.7')
    for ref in ['CACL','CACR']:
        assert '50NXA10MEFC5X11' in by['base'][ref]['value']
        assert by['base'][ref]['footprint']=='Capacitor_THT:CP_Radial_D5.0mm_P2.00mm'
    # Source non-MCU pin nets have not changed at all.
    oldmod=read(ROOT/'clean-sheet-schematic-review-h/module/circuit.json')['parts']
    for p in oldmod:
        if p['ref'].startswith('JCORE'):continue
        assert p['pins']==by['module'][p['ref']]['pins'],p['ref']
    locks=read(HERE/'preservation.json')['files']
    for name,sha in locks.items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha,name
    q=read(HERE/'purchase-plan.json'); covered=[]
    for r in q['rows']:
        assert r['buy_packs']==math.ceil(max(0,r['used']-r['stock'])/r['pack']),r['id']
        assert r['purchased']==r['buy_packs']*r['pack']
        assert r['spare']==r['purchased']+r['stock']-r['used']
        assert Decimal(r['subtotal_jpy'])==Decimal(r['price_jpy_incl'])*r['buy_packs']
        covered+=r['refs']
    refs={b+':'+p['ref'] for b,d in circuits.items() for p in d['parts']}
    assert set(covered)==refs and len(covered)==len(refs)==q['installed_refs']
    for b,d in circuits.items():
        for p in d['parts']:
            r=p['ref']
            if r.startswith('R') and not (r.startswith('RV') and r[2:].isdigit()):
                row=next(x for x in q['rows'] if b+':'+r in x['refs'])
                assert row['mpn'].startswith('RC0805'),(b,r,row['mpn'])
    assert math.ceil(sum(Decimal(r['subtotal_jpy']) for r in q['rows']))==q['parts_goods_jpy']
    assert q['total_jpy']==sum(q[k] for k in ['parts_goods_jpy','parts_freight_jpy','pcb_goods_jpy','pcb_freight_allowance_jpy','reserve_jpy'])
    assert Decimal(q['vendors']['DigiKey']['goods_incl_jpy'])/Decimal('1.1')>=6000
    assert q['vendors']['DigiKey']['freight_jpy']==0
    assert q['pcb_each']==5 and q['populated_sets']==1
    assert q['total_jpy']<=31000 # approximately30k target, not cart guarantee
    report=dict(date='2026-11-19',result='PASS',scope='native ERC + static circuit/quantity contracts only',
                boards=native['boards'],base_gpio=27,panel_gpio=21,source_gpio=28,g40_contacts=40,
                preserved_files=len(locks),installed_refs=len(refs),purchase_rows=len(q['rows']),budget_jpy=q['total_jpy'],
                deferred_footprints=[b+':'+p['ref'] for b,d in circuits.items() for p in d['parts'] if not p['footprint']],
                pcb_or_firmware_implemented=False,hardware_accepted=False)
    if '--record' in sys.argv:(HERE/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    else:assert read(HERE/'verification.json')==report
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
