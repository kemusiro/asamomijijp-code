#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Akizuki primary product page facts, checked 2026-11-18; no ordering API."""
import csv,json,math
from collections import Counter
from pathlib import Path
HERE=Path(__file__).resolve().parent
# Code, exact item, contents per sale unit, sale price incl tax, procurement note.
ROWS=[
('131019','M154-240240-RGB',1,840,'1.54inch240x240; use20261020 datasheet; no old Waveshare cable'),
('114827','RK09D117000B B10k',1,60,'center detent,6mm D shaft,30mm; collar footprint/sample fit pending'),
('114936','RE111F-4S1-152S4-15P-A',1,200,'SMD center-push; supplied black shaft,not a6mm D knob'),
('103568','24FC256-I/P',1,90,'DIP8 EEPROM32KiB;100kHz;64byte page,5ms max write'),
('117166','TVDP01-095BB1',1,15,'6x6mm;9.5mm high momentary'),
('116278','S-42',1,40,'6mm D knob,16mm diameter; A12mm limit superseded'),
('100167','PH-1x40SG',40,35,'cut32UNO+8shieldLCD+8moduleLCD pins;2strips,allow cut loss'),
('115868','20cm40P female-female cable',40,200,'8channels used; start SPI2MHz,128byte tiles; waveform bench pending'),
('116102','CF16J1KB 1k',100,170,'1/6W leaded;stock-common horizontal7.62mm footprint'),
('116272','RD16S 2K7 2.7k',100,100,'1/6W leaded,5%;stock-limited but currently available'),
('116472','RD16S 4K7 4.7k',100,100,'1/6W leaded,5%;stock-limited but currently available'),
('116103','RD16S 10K 10k',100,100,'1/6W leaded,5%'),
('108517','MFS25F33RB 33ohm',100,300,'small1/4W metal film,3.3x1.8mm,1%'),
('107549','CL21B105KPFNNNE 1uF10V',40,150,'2012 X7R;stock-limited but currently available'),
('117591','GRM219B31E106KA12 10uF25V',10,150,'2012 B; bulk decoupling'),
('113582','RDER71H104K0P1H03B 100nF50V',10,100,'radial X7R2.5mm pitch; replaces discontinued0805 items'),
('108138','RDER71H103K0K1H03B 10nF50V',10,100,'radial X7R5mm pitch; replaces discontinued0805 item')]
PRODUCTS={code:dict(code=code,part=part,units_per_pack=n,price_jpy_tax_included=price,availability='in_stock_as_listed',checked_on='2026-11-18',url='https://akizukidenshi.com/catalog/g/g'+code+'/',note=note) for code,part,n,price,note in ROWS}
def code_for_part(p):
 r=p['ref'];v=p['value']
 if r in ['J1','J2','J3','J4','J5']:return '100167'
 if r=='U1':return '103568'
 if r.startswith('RV'):return '114827'
 if r=='ENC1':return '114936'
 if r.startswith('SW'):return '117166'
 if r.startswith('R'):return {'1k':'116102','2.7k':'116272','4.7k':'116472','10k':'116103','33':'108517'}[v]
 if r.startswith('C'):return {'1uF':'107549','10uF':'117591','100nF':'113582','10nF':'108138'}[v]
 raise ValueError(r)
def build():
 d=json.loads((HERE/'circuit.json').read_text());counts=Counter();refs={c:[] for c in PRODUCTS}
 for p in d['parts']:
  code=code_for_part(p);counts[code]+=len(p['pins']) if p['ref'].startswith('J') else 1;refs[code].append(p['ref'])
 for code,n,ref in [('131019',1,'LCD module'),('116278',4,'RV knobs'),('100167',8,'LCD module male pins if not included'),('115868',8,'LCD harness channels')]:counts[code]+=n;refs[code].append(ref)
 rows=[]
 for code in PRODUCTS:
  q=dict(PRODUCTS[code]);q.update(required_units=counts[code],sale_units=math.ceil(counts[code]/q['units_per_pack']),references=refs[code]);q['extended_jpy']=q['sale_units']*q['price_jpy_tax_included'];rows.append(q)
 total=sum(q['extended_jpy'] for q in rows)
 result=dict(date='2026-11-18',supplier='Akizuki Denshi',items=rows,total_jpy=total,all_electrical_refs_mapped=len(d['parts']),excludes=['PCB fabrication','shipping','standoffs/washers/screws after actual mating','optional DIP socket','optional front panel'],not_an_order=True,stock_scope='primary product pages as retrieved; supplier stock/price can change')
 (HERE/'purchase-bom.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 with (HERE/'purchase-bom.csv').open('w',newline='') as f:
  w=csv.writer(f,lineterminator='\n');w.writerow(['Code','Part','Required_units','Units_per_sale','Buy_sale_units','Tax_included_JPY_per_sale','Subtotal_JPY','Availability_checked','URL','References','Note'])
  for q in rows:w.writerow([q['code'],q['part'],q['required_units'],q['units_per_pack'],q['sale_units'],q['price_jpy_tax_included'],q['extended_jpy'],'2026-11-18 in stock',q['url'],' '.join(q['references']),q['note']])
 lines=['# 秋月優先の購入部品表（review B）','','2026-11-18参照。全46参照を秋月商品へ対応付けた。商品ページの在庫あり表示を確認。','価格・在庫は注文時点で再確認する。発注はしていない。','','| 販売コード | 型番/用途 | 必要数 | 購入単位×数 | 税込小計 |','| --- | --- | ---: | --- | ---: |']
 for q in rows:lines.append(f"| [{q['code']}]({q['url']}) | {q['part']} | {q['required_units']} | {q['units_per_pack']}個入×{q['sale_units']} | {q['extended_jpy']:,}円 |")
 lines+=['',f'掲載部材の購入小計：**{total:,}円（税込）**。部品を持っていれば、不要な袋売り/ケーブル等は差し引ける。','PCB・送料・最終嵌合に合わせる支持材・任意DIPソケット・前面パネルは含まない。','LCDケーブルの8本は40本セットから分ける。encoderは付属専用shaftで操作し、RV用6mmノブを流用しない。','','`bom.csv`は回路参照単位、`purchase-bom.csv`は袋/本/セットの購入単位。LCDモジュールと4ノブも後者へ加えた。','旧品番117576/117818/115630は販売終了、115331は入荷未定または販売終了のため採用しない。','105772の照光encoderは2026-11-04に次回入荷分の仕様変更注記があるため選外。','メモリーはFRAMからEEPROMへ変更。保存の完了待ち・page境界・中断処理は[STORAGE.md](STORAGE.md)参照。']
 (HERE/'PURCHASING.md').write_text('\n'.join(lines)+'\n');print('purchase BOM',len(rows),'items;',total,'JPY;',len(d['parts']),'refs')
if __name__=='__main__':build()
