"""Build review-J + rectangular-shield procurement from exact native BOM refs."""
import csv, hashlib, json, math, sys
from collections import Counter
from pathlib import Path
from urllib.parse import quote

ROOT=Path(sys.argv[1]); OUT=Path(sys.argv[2]);OUT.mkdir(parents=True,exist_ok=True)
H=ROOT/'projects/ym2203-sound-module/hardware/ym2203-fpga-board'
paths={'base':H/'clean-sheet-pcb-review-j/base/bom.csv','module':H/'clean-sheet-pcb-review-j/module/bom.csv','shield':H/'editor-shield-review-b/bom.csv'}
boms={k:list(csv.DictReader(v.open())) for k,v in paths.items()}
old=json.loads((H/'digital-module-pcb-review-d/procurement/catalog.json').read_text())['rows'];old={r['id']:r for r in old}
obs_path=OUT/'supplier-observations.json'
if not obs_path.exists():obs_path=H/'manufacturing-review-j/procurement/supplier-observations.json'
obs=json.loads(obs_path.read_text())
rows=[];mapping=[];covered=set()
def refs(board,*values):return [board+':'+r['Reference'] for r in boms[board] if r['Value'] in values]
def named(board,*names):return [board+':'+n for n in names]
def add(id,primary=(),oldid=None,**kw):
 source=old.get(oldid,{})
 r={k:source.get(k,'') for k in ['name','mpn','package','supplier','supplier_code','url','note','source']}
 r.update({'id':id,'kind':'実装','unit':'個','pack_size':None,'pack_verified':False,'price_jpy':None,'availability':'候補型番・在庫/販売単位を発注時確認','checked':None,'selection':'指定型番','qty_base':0,'qty_module':0,'qty_shield':0,'qty_external':0,'spare':0,'stock':0})
 r.update(kw);r['refs']=list(primary)
 if 'qty_base' not in kw and 'qty_module' not in kw and 'qty_shield' not in kw:
  for board in boms:r['qty_'+board]=sum(x.startswith(board+':') for x in primary)
 for ref in primary:
  assert ref not in covered,('Duplicate reference',ref);covered.add(ref)
  board,name=ref.split(':');native=next(x for x in boms[board] if x['Reference']==name)
  mapping.append({'board':board,'reference':name,'value':native['Value'],'footprint':native['Footprint'],'purchase_id':id})
 if r['supplier']=='秋月' and r['supplier_code'] in obs:
  o=obs[r['supplier_code']];r.update(price_jpy=o['price_jpy'],availability=o['availability'],checked=o['checked'],pack_verified=True)
 if not r['url'] and r['supplier']=='DigiKey':r['url']='https://www.digikey.jp/ja/products?keywords='+quote(r['mpn'])
 if r['mpn'] and not r['name']:r['name']=r['mpn']
 if r['supplier']=='DigiKey':r['note']+=' / 価格・在庫・カットテープ最小単位は未見積。'
 n=sum(r['qty_'+k] for k in ['base','module','shield','external']);r['qty_one']=n;r['qty_five']=n*5
 for sets,label in [(1,'one'),(5,'five')]:
  need=max(0,n*sets+r['spare']-r['stock']);r['order_'+label]=math.ceil(need/r['pack_size']) if r['pack_size'] else None
 rows.append(r);return r

add('M01',named('base','MPGA'),oldid='M01',qty_base=1,qty_module=0,qty_shield=0,note='PIM722。秋月/Waveshareの同形代替を確認できずPimoroni指定。オスピン別計上。',availability='Pimoroni商品掲載確認・在庫/価格/販売単位は発注時確認',checked='2026-11-18')
add('M02',named('module','JCORE1','JCORE2','JCORE3','JCORE4'),oldid='M02',qty_base=0,qty_module=1,qty_shield=0,url='https://www.waveshare.com/product/raspberry-pi/core2350b.htm',note='Core2350B0-Kit：PSRAMなし＋USB adapter＋FFC。4つのJCOREは1枚のMCUを表す。0MB品を選択。',availability='公式商品構成確認・在庫/価格/販売単位は発注時確認',checked='2026-11-18')
add('M03',named('module','U12'),oldid='M03',url='',selection='手持ち優先・新規調達未確定',note='YM2203C DIP40。Rev Cの手持ちを転用する場合は手持ち欄=1。中古の真贋/動作は未保証。')
add('J01',oldid='J01',qty_module=1,pack_size=10,note='U12用。1袋10個。IC本体M03と別。')
add('J02',oldid='J02',qty_base=64,qty_module=64,selection='初回少数で嵌合高さ確認',note='0300-2は0.64mm角ピン対応。PCB穴1.20mm。MCU下面9.5mm治具で実装、挿入3.5～4.5mm。128個/セット。汎用四辺ソケット不可。',source='https://media.digikey.com/pdf/Data%20Sheets/Mill%20Max%20PDFs/Pin_Receptacles_FOR%200%2C64-0%2C94.pdf')
headers=named('base','JHOST','JSWD','JPOWER','JPOT','JLINE')+named('module','JSWD')+named('shield','J1','J2','J3','J4','J5')
add('J03',headers,oldid='J03',qty_base=82,qty_module=69,qty_shield=40,qty_external=8,pack_size=40,unit='接点',spare=40,note='199接点/セット=MCU128＋ベース18＋音源SWD5＋シールド40＋LCD8。切出し予備40接点/注文を初期設定。1セット6本・5セット26本。MCU四隅の樹脂は干渉回避。')
add('J04',named('base','JMOD'),oldid='J04',mpn='SSW-120-02-G-D',package='2×20 / 2.54mm / 高8.51mm',url='https://www.digikey.jp/ja/products?keywords=SSW-120-02-G-D',note='G40の6番を塞ぐ。旧32接点版は不可。TSW-120と嵌合、基板面間11.05mm公称・10.5mm以上。')
add('J05',named('module','JMOD'),oldid='J05',mpn='TSW-120-07-G-D',package='2×20 / 2.54mm / 嵌合5.84mm',url='https://www.digikey.jp/ja/products?keywords=TSW-120-07-G-D',note='音源基板の裏面に実装。6番抜去。SSW-120とセット、高さ違いの代用品不可。')
for id,names,oldid in [('J06',['JUNO_D0','JUNO_PWR'],'J06'),('J07',['JUNO_D8'],'J07'),('J08',['JUNO_A'],'J08'),('J09',['JUNO_SPI'],'J09')]:add(id,named('base',*names),oldid=oldid,note='UNO R3形状/3.3V。シールド側はJ03のオスピン。ICSPはシールドに挿入しない。')
add('J10',named('base','JUSB'),oldid='J10',note='HROの指定12接点品。秋月/WaveshareのUSB変換モジュールは代用不可。実装図/アンカー穴と照合して発注。')

ics=[('U01','Si5351A-B-GT','U01'),('U02','PCM5102APWR','U02'),('U03','PCM1863DBT','U03'),('U06','MCP23017-E/SO','U06'),('U08','SN74LVC1G17DBVR','U08'),('U09','SN74LVC1G08DBVR','U09'),('U14','SN74LVC1G125DBVR','U14'),('U16','USBLC6-2SC6','U16'),('D01','BAT54S,215','D01')]
for id,v,oldid in ics:
 pr=refs('base',v);pkg=next(r['Footprint'] for r in boms['base'] if r['Value']==v)
 kw={}
 if id=='U03':kw['name']='共通アナログL/R ADC'
 if id=='U14':kw['name']='音源I2Sデータ受信バッファ'
 add(id,pr,oldid=oldid,package=pkg,note='IC単体の指定パッケージ。秋月のDIPキット/変換基板では代用不可。'+('シリーズ接続のBAT54S、A/C品不可。' if id=='D01' else ''),**kw)
add('U07',refs('base','TLV1117LV33DCYR'),name='ADC系3.3Vレギュレーター',mpn='TLV1117LV33DCYR',package='SOT-223-4',supplier='DigiKey',source='https://www.ti.com/lit/ds/symlink/tlv1117lv.pdf',note='旧review DのTLV75533ではない。TLV1117LV33固定品。')
for id,v,oldid in [('U10','SN74LV4T125PWR','U10'),('U11','SN74LVC8T245PWR','U11'),('U13','SN74LVC1G07DBVR','U13')]:
 add(id,refs('module',v),oldid=oldid,note='音源側の5V変換/オープンドレイン。現行設計で必要、削除不可。')
add('U17',refs('module','SN74LVC1G32DBVR'),name='送信音声経路OR',mpn='SN74LVC1G32DBVR',package='SOT-23-5',supplier='DigiKey',source='https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf')
add('X01',refs('base','25MHz CL10pF +/-20ppm'),oldid='X01',selection='候補・注文時仕様照合',source='https://abracon.com/Resonators/abm8.pdf',note='ABM8-25.000MHZ-10-B1U-T：3.2×2.5mm/4pad、水晶25MHz・CL10pF・初期±10ppm/温度±10ppm。発振器ではない。メーカー図面/公差を注文時照合。')
add('F01',refs('base','MF-MSMF200/16X-2 / 2A hold@23C'),oldid='F01',mpn='MF-MSMF200/16X-2',url='https://www.digikey.jp/ja/products?keywords=MF-MSMF200%2F16X-2',note='1812、2A hold@23℃・16V。旧Dの1.5A品は使わない。温度ディレーティングあり。')
add('L01',refs('base','BLM21PG601SN1 / 600R@100MHz'),oldid='L01')
add('S01',named('base','SWRESET','SWBOOT','SWSTOP','SWTEST'),oldid='S01',name='ベースタクト4個共通',note='6×6mm/4端子、操作部4.3mm。2端子/5mm高の秋月品では置換しない。')
add('S02',named('base','SWCLOCK'),oldid='S02',selection='候補・注文時外形照合',availability='共立取寄せ候補・単位/納期再確認',note='CTS209-4LPST、4極/2.54ピッチ/列間7.62mm。共立は10個単位候補、確定後に販売数10を入力。高さ≤8mm。EDS104等を無照合で代用しない。')
add('LED01',named('base',*[f'DLED{i}' for i in range(7)]),oldid='LED01',pack_size=1)
for id,values,oldid in [
 ('R01',['10k','10k 1%'],'R01'),('R02',['100k'],'R02'),('R03',['1k'],'R03'),('R04',['5.1k 1%'],'R04'),('R05',['47k 0.1%'],'R05'),('R06',['68k 0.1%'],'R06'),('R07',['2.2k','2.2k 1%'],'R07'),('R08',['33'],'R08'),('R09',['470'],'R09'),('R11',['100'],'R11'),('R12',['0'],'R12'),('R14',['1.33k 1%'],'R14')]:
 kw={}
 if id in ['R01','R02','R03','R11']:kw={'pack_size':5,'note':'2012(0805)。±0.1%品で通常/1%指定も集約。0603(1608)品への置換不可。'}
 add(id,refs('base',*values)+refs('module',*values),oldid=oldid,**kw)
add('R17',refs('base','6.81k 1%'),name='ADC入力減衰抵抗',mpn='RC0805FR-076K81L',package='2012 / 0805 / ±1%',supplier='DigiKey',note='ADC入力の左右比を維持。')
for id,values,oldid in [
 ('C01',['100n X7R 10V'],'C01'),('C02',['10u 10V','10u X7R 10V'],'C02'),('C03',['2.2u X7R 10V'],'C03'),('C04',['1u X7R 10V'],'C04'),('C05',['4.7u X7R 10V'],'C05'),('C06',['22u X7R 10V'],'C06'),('C07',['1n C0G'],'C07'),('C08',['100p C0G'],'C08'),('C09',['2.2n C0G'],'C09'),('C11',['470p C0G'],'C11'),('C12',['100u 10V'],'C12')]:
 kw={}
 if id in ['C02','C03']:kw['pack_size']=10
 if id=='C04':kw['pack_size']=40
 if id=='C05':kw['pack_size']=20
 if id=='C12':kw['pack_size']=1
 add(id,refs('base',*values)+refs('module',*values),oldid=oldid,**kw)
add('C14',refs('base','10u X7R 16V / effective>=4.7u'),name='ADC入力AC結合MLCC',mpn='GRM21BR71C106KE51L（候補）',package='2012 / 0805 / 10uF16V X7R',supplier='DigiKey',url='https://www.digikey.jp/ja/products?keywords=GRM21BR71C106KE51L',source='https://www.ti.com/lit/ds/symlink/pcm1863.pdf',selection='DCバイアス曲線確認が必要',note='CACL/CACR。実使用DCバイアス・公差・温度で有効4.7uF以上を確認して確定。名目10uFだけでは合格にしない。秋月117591(B25V)は無条件代用不可。')

# Shield catalogue uses its already chosen native parts; merge identical 1uF only.
add('EPU',refs('shield','24FC256-I/P'),name='音色保存EEPROM',mpn='24FC256-I/P',package='DIP8 / 7.62mm',supplier='秋月',supplier_code='103568',url='https://akizukidenshi.com/catalog/g/g103568/',pack_size=1,note='基板へ直接実装を基本。32KiB/64byte page、5ms書込待ち。')
add('EPOT',refs('shield','B10K RK09D117000B'),name='編集ボリュームB10k',mpn='RK09D117000B',package='6mm D軸 / 30mm / センタークリック',supplier='秋月',supplier_code='114827',url='https://akizukidenshi.com/catalog/g/g114827/',pack_size=1,selection='指定品・初回端子/ツマミ高さ確認',note='4個。S-42ノブは別。LCD下の部品/リードを既存高さ条件内に収める。')
add('EENC',refs('shield','ALPHA RE111F-4S1-152S4-15P-A'),name='プッシュ付きロータリーエンコーダー',mpn='RE111F-4S1-152S4-15P-A',package='表面実装 / 専用黒軸付属',supplier='秋月',supplier_code='114936',url='https://akizukidenshi.com/catalog/g/g114936/',pack_size=1,note='6mm Dノブを追加購入しない。NPTH長穴あり。')
add('ESW',named('shield',*[f'SW{i}' for i in range(1,7)]),name='編集/STOPタクト',mpn='TVDP01-095BB1',package='6×6mm / 高9.5mm',supplier='秋月',supplier_code='117166',url='https://akizukidenshi.com/catalog/g/g117166/',pack_size=1,note='ベースの4.3mm品S01とは別。')
shield_defs=[('ER1','1k','CF16J1KB','116102',100),('ER2','2.7k','RD16S 2K7','116272',100),('ER3','4.7k','RD16S 4K7','116472',100),('ER4','10k','RD16S 10K','116103',100),('ER5','33','MFS25F33RB','108517',100),('EC1','1uF','CL21B105KPFNNNE','107549',40),('EC2','10uF','GRM219B31E106KA12','117591',10),('EC3','100nF','RDER71H104K0P1H03B','113582',10),('EC4','10nF','RDER71H103K0K1H03B','108138',10)]
for id,val,mpn,code,pack in shield_defs:
 if id=='EC1':
  r=next(x for x in rows if x['id']=='C04');r['qty_shield']=1;r['refs']+=refs('shield',val)
  for ref in refs('shield',val):
   assert ref not in covered;covered.add(ref);board,n=ref.split(':');x=next(x for x in boms[board] if x['Reference']==n);mapping.append({'board':board,'reference':n,'value':val,'footprint':x['Footprint'],'purchase_id':'C04'})
  r['qty_one']+=1;r['qty_five']+=5;r['order_one']=math.ceil(r['qty_one']/pack);r['order_five']=math.ceil(r['qty_five']/pack)
 else:add(id,refs('shield',val),name='シールド '+val,mpn=mpn,package=next(x['Footprint'] for x in boms['shield'] if x['Value']==val),supplier='秋月',supplier_code=code,url='https://akizukidenshi.com/catalog/g/g'+code+'/',pack_size=pack,note='既存シールド採用品。リード部品は裏面突出3mm以下で切断。')
add('LCD',name='カラーディスプレイ',mpn='M154-240240-RGB',package='1.54inch / 240×240 / 20261020仕様',supplier='秋月',supplier_code='131019',url='https://akizukidenshi.com/catalog/g/g131019/',qty_shield=1,pack_size=1,note='現行LCD維持。旧1.3inch/Waveshare機械寸法とは混用しない。12mm支柱×4は別。')
add('KNOB',name='編集ボリューム用ノブ',mpn='S-42',package='6mm D軸 / 外径16mm',supplier='秋月',supplier_code='116278',url='https://akizukidenshi.com/catalog/g/g116278/',qty_shield=4,pack_size=1)
add('LCDWIRE',name='LCDハーネス',mpn='コネクター付ケーブル20cm40Pメスメス',package='2.54mm / 40chから8ch使用',supplier='秋月',supplier_code='115868',url='https://akizukidenshi.com/catalog/g/g115868/',qty_shield=8,pack_size=40,unit='ch',note='最低1セット1本(8ch分)から切出し。5セットなら40ch=1本。長さ20cm、SPIは初期2MHzで実機確認。')

add('E01',oldid='E01',qty_external=1,pack_size=1,note='基板外6pin JPOTへ配線。2連A10k音量つまみ。')
add('E02',oldid='E02',qty_external=1,pack_size=1,note='基板外3pin JLINEへ配線、ヘッドホン直結用ではなくライン出力。')
add('E03',oldid='E03',qty_external=1,kind='機構/配線',selection='軸形状で確定',note='外部音量E01の6mmローレット軸用。シールド用D軸S-42とは別。裸軸で使用する場合は手持ち欄=1で控除。')
for id,name,mpn,n,note in [
 ('H01','基板間/底脚支柱','M3 両メネジ10mm＋高さ調整ワッシャー',11,'音源4＋シールド3＋底脚4。面間11.05/11.01mm公称に調整、10.5mm未満不可。底脚10mm。金属支柱は裸配線と接触させない。'),
 ('H02','LCD支柱','M2 両メネジ12mm',4,'LCD穴2.2mm×4。12mm面間を維持。M3ネジ不可。'),
 ('H03','M3固定ネジ','M3×6mm',22,'音源8＋シールド6＋底脚8。ねじ込み量/底付きは現物確認。H11にはネジを入れない。'),
 ('H04','LCD固定ネジ','M2×4mm',8,'上下各4、ねじ込み量は支柱図面で確認。'),
 ('H05','M3高さ調整ワッシャー','M3用 1mm＋0.05～0.1mmシム',7,'音源4＋シールド3。コネクタ嵌合を実測して調整、支柱で基板を引き曲げない。'),
 ('H06','G40誤挿入防止','2.54mmソケット用6番キー栓',1,'JMOD雌6番を塞ぎ雄6番抜去。単なる外観目印では代用しない。'),
 ('E09','電源ハーネス','2.54mm 2極メス＋短い2A配線',1,'JPOWERへ。端子極性確認。'),
 ('E10','音量/ラインハーネス','2.54mm 6極/3極メス＋シールド線',1,'JPOT6極/JLINE3極。音声の戻りを電源大電流配線と分ける。'),
 ('E11','HOST接続ハーネス','2.54mm 4極メス・3.3V I2C',1,'JHOST。Rev C既存HOST ABIを維持、5V信号は禁止。'),
 ('E12','USB接続ケーブル','PC側適合⇔USB-C データ対応',1,'USB-MIDI/CDC/WYM1用。'),
 ('E13','外部5V電源','安定化5.0～5.1V / 2A以上',1,'既存電源を流用する場合は手持ち控除。USBと外部電源経路は回路どおり。')]:
 kw={}
 if id=='H01':kw={'supplier_code':'107313','pack_size':1};mpn='FB3-10';supplier='秋月';url='https://akizukidenshi.com/catalog/g/g107313/'
 else:supplier='秋月優先・仕様調達';url='https://akizukidenshi.com/catalog/c/cscrewspa/' if id.startswith('H') else 'https://akizukidenshi.com/'
 add(id,name=name,mpn=mpn,package='基板外/機構',supplier=supplier,url=url,qty_external=n,kind='機構/配線',selection='仕様品・現物寸法で確定',note=note,**kw)
for id,board,mpn in [('PCB1','base','p2-base-j'),('PCB2','module','p2-ym2203-i'),('PCB3','shield','p2-editor-b')]:add(id,name=board+'製作基板',mpn=mpn,package='FR4/1.6mm',supplier='PCB製造業者',qty_external=1,kind='PCB',selection='製造ZIP別添',note='数量/製造単位は業者見積。部品通販とは別。')

nonpurchased=named('base','JP_SDA','JP_SCL','JP5V')
for ref in nonpurchased:
 assert ref not in covered;covered.add(ref);board,n=ref.split(':');r=next(x for x in boms[board] if x['Reference']==n)
 mapping.append({'board':board,'reference':n,'value':r['Value'],'footprint':r['Footprint'],'purchase_id':'PCB-COPPER'})
expected={k+':'+r['Reference'] for k,rs in boms.items() for r in rs};assert covered==expected,(expected-covered,covered-expected)
assert len(mapping)==274
assert {k:len(v) for k,v in boms.items()}=={'base':152,'module':76,'shield':46}
data={'schema_version':1,'revision':'review J base + unchanged review I source + rectangular editor B','checked':'2026-11-18','scope':'1セット=ベース1枚＋音源1枚＋開口なしシールド1枚。初期手持ち0、ヘッダーのみ注文当たり40接点予備。','prices':'円価格は確認できた秋月の税込販売単位価格だけ。未見積を0円にしない。送料/為替/業者費/他店価格を含む総額ではない。','source_bom_sha256':{str(p.relative_to(H)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths.values()},'rows':rows,'primary_reference_count':274,'pcb_only_refs':nonpurchased}
(OUT/'catalog.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
with (OUT/'reference-map.csv').open('w',newline='',encoding='utf-8') as f:
 w=csv.DictWriter(f,fieldnames=list(mapping[0]));w.writeheader();w.writerows(sorted(mapping,key=lambda r:(r['board'],r['reference'])))
fields=['id','name','mpn','package','supplier','supplier_code','qty_base','qty_module','qty_shield','qty_external','unit','qty_one','qty_five','pack_size','pack_verified','spare','stock','order_one','order_five','price_jpy','availability','selection','checked','url','source','note']
for filename,subset in [('purchase-bom.csv',rows),('akizuki-order.csv',[r for r in rows if r['supplier']=='秋月']),('other-suppliers.csv',[r for r in rows if r['supplier']!='秋月'])]:
 with (OUT/filename).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(subset)
print('Purchase lines:',len(rows),'reference coverage:',len(mapping),'Akizuki:',sum(r['supplier']=='秋月' for r in rows))
print('Quantities:',[(r['id'],r['qty_one'],r['qty_five'],r['order_one'],r['order_five']) for r in rows if r['id'] in ['J02','J03','C04','LCDWIRE']])
