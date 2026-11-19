#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""One populated set, five PCBs/type; catalog observations and explicit caps."""
from pathlib import Path
from collections import defaultdict
from decimal import Decimal, ROUND_CEILING
import json,csv,math
HERE=Path(__file__).resolve().parent
ROOT=HERE.parent

def build():
    old=json.loads((ROOT/'procurement-review-d/budget.json').read_text())
    oldby={x['id']:x for x in old['parts_rows']}
    order=json.loads((ROOT/'primary-order-review-b/order-plan.json').read_text())
    refid={ref.replace('shield:','panel:'):x['id'] for x in order['rows'] for ref in x.get('refs',[])}
    parts={b+':'+p['ref']:p for b in ['base','module','panel'] for p in json.loads((HERE/b/'circuit.json').read_text())['parts']}
    rows=[];used=set()
    def add(key,mpn,vendor,qty,pack,price,url,refs=(),evidence='catalog_observation',note='',stock=0):
        vendor={'秋月':'Akizuki','スイッチサイエンス':'Switch Science'}.get(vendor,vendor)
        assert not used.intersection(refs),key
        used.update(refs)
        buys=math.ceil(max(0,qty-stock)/pack) if qty else 0
        rows.append(dict(id=key,mpn=mpn,supplier=vendor,used=qty,stock=stock,pack=pack,buy_packs=buys,purchased=buys*pack,spare=buys*pack+stock-qty,
                         price_jpy_incl=str(price),subtotal_jpy=str(Decimal(str(price))*buys),url=url,refs=list(refs),evidence=evidence,note=note))
    def inherit(key,refs,override_qty=None):
        o=oldby[key];q=override_qty if override_qty is not None else len(refs)
        pr=Decimal(str(o['price']))
        if o['currency']=='USD':raise ValueError('overseas vendor not retained '+key)
        if o['tax']=='excluded':pr*=Decimal('1.1')
        add(key,o['offered_mpn'],o['supplier'],q,o['pack'],pr,o['url'],refs,'saved_procurement_D_catalog_observation',o['note'],1 if key=='M03' else 0)
    add('MBASE','Picossci 2 RP2350A SSCI-097956','Switch Science',1,1,1760,'https://www.switch-science.com/products/9795',['base:UBASE'])
    add('MSOURCE','Picossci 2B SSCI-105071','Switch Science',1,1,2310,'https://www.switch-science.com/products/10507',['module:USOURCE'])
    add('MPANEL','Pico SC0915','Akizuki',1,1,800,'https://akizukidenshi.com/catalog/g/g116132/',['panel:UPICO'])
    add('S40','2227MC-40-06 round DIP40 600mil','Akizuki',1,1,110,'https://akizukidenshi.com/catalog/g/g100034/',note='RealDIPYMpins only;not0.64mmsquareMCUpins.')
    add('SOCKPICO','FH-1x20SG /103077','Akizuki',2,1,50,'https://akizukidenshi.com/catalog/g/g103077/',note='Two20pinPicosockets;module pinstrips inHDR.')
    add('GROVE','110990037','Akizuki',2,10,150,'https://akizukidenshi.com/catalog/g/g112634/',['base:JEDIT','panel:JUPLINK'])
    add('GROVECABLE','DG01032-0064-03 150mm','Akizuki',1,1,110,'https://akizukidenshi.com/catalog/g/g116938/')
    add('MUX','CD74HC4051E','DigiKey',1,1,199.1,'https://www.digikey.jp/ja/products/detail/texas-instruments/CD74HC4051E/475938',['panel:UMUX'])
    add('DPOWER','1N5819','Akizuki',1,10,100,'https://akizukidenshi.com/catalog/g/g117244/',['panel:DPOWER'])
    add('DAC','PCM5102APWR','DigiKey',1,1,686.4,'https://www.digikey.jp/ja/products/detail/texas-instruments/PCM5102APWR/3727211',['base:U17'],note='624JPY ex;sameIC cheaper supplier;CT notDigiReel.')
    add('ADC','PCM1863DBT','DigiKey',1,1,1236.4,'https://www.digikey.jp/ja/products/detail/texas-instruments/PCM1863DBT/4895616',['base:UADC'],note='1124JPY ex current observation')
    add('RX','TC7SZ125F,LJ(CT','DigiKey',1,1,30.8,'https://www.digikey.jp/en/products/detail/toshiba-semiconductor-and-storage/TC7SZ125F-LJ-CT/870689',['base:URXDATA'],note='28JPYex;SMV pin1OE2A3GND4Y5V;5.5Vtolerant/Ioff;F not FU.')
    add('CLAMP','BAT54S-QR','DigiKey',2,1,29.7,'https://www.digikey.jp/ja/products/detail/nexperia-usa-inc/BAT54S-QR/24630583',['base:DCLAMPL','base:DCLAMPR'],note='27JPYex active stock;1anode/2cathode/3midpoint unchanged.')
    add('ADCAC','50NXA10MEFC5X11 NP10u50V','Akizuki',2,1,20,'https://akizukidenshi.com/catalog/g/g130142/',['base:CACL','base:CACR'],note='D5xH11mm;P2.0mm;nonpolar;minimum8uF at20%tolerance,notX7RDCderating.')
    add('YM_DAC','YM3014B-F 16SOP / user supplied','User supplied',1,1,0,'https://bitsavers.trailing-edge.com/components/yamaha/YM3014B_199403.pdf',['module:UDAC'],evidence='user_supplied_not_new_purchase',stock=1)
    add('OPAMP','MCP6002-E/P 8PDIP','Akizuki',1,1,80,'https://akizukidenshi.com/catalog/g/g130011/',['module:UAF'],evidence='catalog_2026-11-19_stock290',note='2followers:RBtoMP,TO_BUFFtoFM_BUF;no socket required.')
    add('RB_CAP','50PX10MEFC5X11 10u50V polar','Akizuki',1,1,10,'https://akizukidenshi.com/catalog/g/g117897/',['module:CRB'],evidence='catalog_2026-11-19',note='D5xH11 P2mm;positive toRB. Exact placement pending.')
    add('DIP','EDS104SZ','Akizuki',1,1,100,'https://akizukidenshi.com/catalog/g/g100586/',['base:SWCLOCK'])
    # No exotic precision is needed for ordinary bias/pullup/LED/series resistors.
    rg=defaultdict(list)
    for ref,p in parts.items():
        if p['ref'].startswith('R') and not (p['ref'].startswith('RV') and p['ref'][2:].isdigit()):
            rg[p['value'].split()[0]].append(ref)
    suffix={'0':'RC0805JR-070RL','33':'RC0805FR-0733RL','100':'RC0805FR-07100RL','470':'RC0805FR-07470RL','1k':'RC0805FR-071KL','1.33k':'RC0805FR-071K33L','2.2k':'RC0805FR-072K2L','2.7k':'RC0805FR-072K7L','4.7k':'RC0805FR-074K7L','5.1k':'RC0805FR-075K1L','6.8k':'RC0805FR-076K8L','10k':'RC0805FR-0710KL','47k':'RC0805FR-0747KL','68k':'RC0805FR-0768KL','100k':'RC0805FR-07100KL'}
    for value,refs in sorted(rg.items()):
        # Per-value allowance, not claiming identical actual prices across resistance values.
        q=len(refs);rate=Decimal('8') if q>=10 else Decimal('35')
        add('R_'+value,suffix[value]+(' /0805 jumper' if value=='0' else ' /0805 thick film 1%'), 'DigiKey',q,1,rate,'https://www.digikey.jp/ja/products/detail/yageo/RC0805FR-0710KL/730482',refs,'family_price_cap_NOT_each_MPN_quote','Max8JPYincl for10+pcs/value;35JPYinclfor<10;eachvalue stock/cart reconfirm. No0.1%thinfilm.')
    # Common capacitor quantities; every installed ref accounted for.
    cg=defaultdict(list)
    for ref,p in parts.items():
        if p['ref'].startswith('C') and ref not in used:
            cg[p['value'].split()[0].replace('F','')].append(ref)
    caps={
      '100n':('CC0805KRX7R9BB104 X7R50V','DigiKey',1,17.82,'https://www.digikey.jp/ja/products/detail/yageo/CC0805KRX7R9BB104/302874','catalog_observation_10plus_tier'),
      '10u':('GRM21BR71A106KE51 X7R10V','Akizuki',10,150,'https://akizukidenshi.com/catalog/g/g117593/','saved_procurement_D_catalog_observation'),
      '2.2u':('GRM21BR71E225KE11 X7R25V','Akizuki',10,100,'https://akizukidenshi.com/catalog/g/g114788/','saved_procurement_D_catalog_observation'),
      '1u':('C2012X7R1H105K125AB /0805 X7R50V','DigiKey',1,42.9,'https://www.digikey.jp/ja/products/detail/tdk/C2012X7R1H105K125AB/2733619','catalog_observation'),
      '4.7u':('GRM21BR71C475KE51 X7R16V','Akizuki',20,100,'https://akizukidenshi.com/catalog/g/g131147/','saved_procurement_D_catalog_observation'),
      '22u':('C3225X7R1C226K250AC /1210 X7R16V','DigiKey',1,143,'https://www.digikey.jp/ja/products?keywords=C3225X7R1C226K250AC','indexed_primary_equivalent_130JPYex'),
      '1n':('CC0805JRNPO9BN102 C0G','DigiKey',1,115.5,'https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN102','saved_procurement_D_catalog_observation'),
      '100p':('CC0805JRNPO9BN101 C0G','DigiKey',1,41.8,'https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN101','saved_procurement_D_catalog_observation'),
      '2.2n':('C0805C222J5GACTU C0G','DigiKey',1,132,'https://www.digikey.jp/ja/products?keywords=C0805C222J5GACTU','saved_procurement_D_catalog_observation'),
      '470p':('CC0805JRNPO9BN471 C0G','DigiKey',1,30.8,'https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN471','saved_procurement_D_catalog_observation'),
      '10n':('CC0805KRX7R9BB103 X7R50V','DigiKey',1,35,'https://www.digikey.jp/ja/products?keywords=CC0805KRX7R9BB103','allowance_NOT_current_MPN_quote'),
      '100u':('16MH5100MEFC6.3X5','Akizuki',1,20,'https://akizukidenshi.com/catalog/g/g105002/','saved_procurement_D_catalog_observation')}
    for value,refs in sorted(cg.items()):
        mpn,v,pack,pr,u,e=caps[value];add('C_'+value,mpn,v,len(refs),pack,pr,u,refs,e)
    # Installed references whose identities did not change from H/editorB.
    groups=defaultdict(list)
    for ref,p in parts.items():
        if ref not in used:groups[refid.get(ref,'NEW')].append(ref)
    for key,refs in groups.items():
        if key=='NEW':raise ValueError('unmapped '+str(refs))
        if key=='J03':
            contacts=sum(len(parts[r]['pins']) for r in refs)+40+8
            add('HDR','PH-1x40SG','Akizuki',contacts+8,40,35,'https://akizukidenshi.com/catalog/g/g100167/',refs,note=f'{contacts}contacts includesPico40+LCDmodule8;8contacts cutloss allowance.')
        elif key=='J04':add(key,'FH-2x20SG','Akizuki',1,1,80,'https://akizukidenshi.com/catalog/g/g100085/',refs)
        elif key=='J05':add(key,'PH-2x20SG','Akizuki',1,1,50,'https://akizukidenshi.com/catalog/g/g100080/',refs)
        elif key=='J10':add(key,'5075BR-04-WH USB TypeB','Akizuki',1,1,50,'https://akizukidenshi.com/catalog/g/g100161/',refs,note='USB2FSdata,notpoweronly;TypeB cable needed;50JPYcatalog.')
        elif key=='S01':
            # Keep known tact switch, no low-price unknown mechanical substitution.
            inherit(key,refs)
        else:inherit(key,refs)
    # External functions and assembly, no MCU single-pin receptacles/shims/UNO.
    for key in ['LCD','KNOB','LCDWIRE','E01','E02','E03','E13','WIRE22','DCADAPT','SLEEVING']:
        q=oldby[key]['used']
        inherit(key,[],q)
    add('USB_CABLE','LDUC1025D15 USB2 TypeA-to-TypeB 1.5m','Akizuki',1,1,110,'https://akizukidenshi.com/catalog/g/g117015/',note='Replaces oldA-Ccable. PCwithonlyUSB-C requiresadapter or C-Bcable,not assumed supplied.')
    add('MECH','ordinary M3 supports/screws + M2 LCDsupports/screws','Akizuki',1,1,1000,'https://akizukidenshi.com/catalog/c/cspacer/',evidence='allowance_NOT_fixed_height_BOM',note='3boards12mounts+4LCD;no precision shims. Height andprices finalatPCB stage.')
    add('KEY','G40 insulating pin6 block','Akizuki',1,1,50,'',evidence='allowance_not_catalog_part',note='Nonconductive pin6block+opposingmale6removed;no rareSamtecaccessory.')
    assert used==set(parts),(set(parts)-used)
    vendors=defaultdict(Decimal)
    for r in rows:vendors[r['supplier']]+=Decimal(r['subtotal_jpy'])
    # DK threshold against ex-tax commodity value; generous 2k shipping fallback.
    dk_ship=0 if vendors['DigiKey']/Decimal('1.1')>=6000 else 2000
    freight={'Akizuki':550,'Switch Science':0 if vendors['Switch Science']>=3000 else 200,'DigiKey':dk_ship}
    assert set(vendors)<=set(freight)|{'Rev Cから流用','User supplied'}
    goods=sum(vendors.values());rounded=math.ceil(goods)
    pcb=3824;pcb_ship=3500;reserve=2500
    result=dict(date='2026-11-19',status='engineering_budget_not_final_cart_order',pcb_each=5,populated_sets=1,ym_reuse=True,ym3014_supplied=True,rows=rows,
                installed_refs=len(used),vendors={v:{'goods_incl_jpy':str(x),'freight_jpy':freight.get(v,0)} for v,x in vendors.items()},
                parts_goods_jpy=rounded,parts_freight_jpy=sum(freight.values()),pcb_goods_jpy=pcb,pcb_freight_allowance_jpy=pcb_ship,reserve_jpy=reserve,
                total_jpy=rounded+sum(freight.values())+pcb+pcb_ship+reserve,
                old_LCB_total_jpy=44466,saved_review_C_total_jpy=29751,all_rows_are_current_cart_quote=False,
                pcb_basis='LC-A anonymous same-dimension100mm4L +100x80and100x76twoLayer quotes;noLC-EGerber/CAM yet',
                excludes=['PCBA','tools','case','labor','future source boards','replacement YM2203'],
                shipping_sources=['https://www.digikey.jp/ja/help-support/delivery-information/delivery-time-and-cost','https://www.switch-science.com/policies/legal-notice'],
                note='planning_non_marketplace_catalog_parts;per-MPNstock/cart_recheck_required;SSCI4070JPYsmallparcelgroupfree;DKthreshold recalculated;PCB3500andreserve2500planning,not observednewfreight')
    (HERE/'purchase-plan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    with (HERE/'purchase-plan.csv').open('w',newline='') as f:
        w=csv.writer(f,lineterminator='\n');w.writerow(['ID','Part','Vendor','Used','Reuse_stock','Units_per_pack','Buy_packs','Purchased','Spare','JPY_incl_per_pack','Subtotal_JPY','Evidence','URL','Refs','Note'])
        for r in rows:w.writerow([r[k] if k!='refs' else ' '.join(r[k]) for k in ['id','mpn','supplier','used','stock','pack','buy_packs','purchased','spare','price_jpy_incl','subtotal_jpy','evidence','url','refs','note']])
    print(json.dumps({k:v for k,v in result.items() if k not in ['rows','shipping_sources']},ensure_ascii=False,indent=2))
    return result
if __name__=='__main__':build()
