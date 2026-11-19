#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recompute preserved anonymous calculator observations without live prices or credentials."""
from pathlib import Path
from decimal import Decimal,ROUND_HALF_UP
import json
H=Path(__file__).resolve().parents[1];Q=H/'procurement';D=lambda v:Decimal(str(v))
def main():
 obs=json.loads((Q/'observations.json').read_text());profile=json.loads((Q/'order-profile.json').read_text());assert profile['pcb_each']==5 and profile['fitted_sets']==1;result={'checked':obs['checked'],'currency':'USD','fx_assumption_jpy_per_usd':obs['fx_assumption_jpy_per_usd'],'fx_is_live':False,'parts_cost_included':False,'tax_and_clearance_included':False,'quote_not_checkout':True,'variants':{}}
 for variant,p in profile['variants'].items():
  assert len(p['boards'])==3;out={}
  for vendor,v in obs['vendors'].items():
   rows=[v['boards'][k] for k in p['boards']];assert all(q['quantity']==5 for q in rows);total=sum(D(q['price_usd']) for q in rows);ship=v['freight'][variant];assert total==D(ship['goods_usd']);rates=[]
   for m in ship['methods']:
    if not m['available'] or m['cost_usd'] is None:continue
    cost=D(m['cost_usd']);assert cost>0;allin=total+cost;rates.append({**m,'pcb_usd':float(total),'delivered_usd':float(allin),'delivered_jpy':int((allin*D(obs['fx_assumption_jpy_per_usd'])).quantize(D(1),rounding=ROUND_HALF_UP))})
   assert rates;best=min(rates,key=lambda q:q['delivered_usd']);out[vendor]={'pcb_total_usd':float(total),'rates':rates,'cheapest_inspected':best}
  result['variants'][variant]={'label':p['label'],'boards':p['boards'],'vendors':out}
 result['same_vendor_savings_usd']={v:float(D(result['variants']['primary']['vendors'][v]['cheapest_inspected']['delivered_usd'])-D(result['variants']['comparison']['vendors'][v]['cheapest_inspected']['delivered_usd'])) for v in obs['vendors']}
 (Q/'comparison.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
 lines=['# review K：各5枚・部品1セットの送料込み比較','','2026-11-18。未ログインの公式計算器を再入力した記録。Gerber送信・カート作成・発注は行っていない。','**製造費は入力値による試算、送料は日本向け同梱の推定で、住所を入れた決済画面の確定額ではない。**','','## 比較する構成','','- 主案：ベースJ 4層＋音源K 2層＋開口なしシールドB 2層。','- 比較案：ベースK 2層＋音源K 2層＋同じシールドB 2層。','- 各設計5枚、合計15枚。実装は各1枚、予備12枚。部品は両案共通の1セット。','- FR-4、1.6mm、緑マスク・白シルク、ENIG 1µinch、外層1oz。4層の内層1oz。','- 単体基板、工場標準積層。PCBA・ペースト・ステンシル・管理インピーダンス・樹脂充填/銅蓋・クーポンなし。','','## 基板製造費（各行5枚分、USD）','','| 基板 | 寸法mm | 層 | 最小穴mm | JLCPCB | PCBWay |','| --- | --- | ---: | ---: | ---: | ---: |']
 labels={'base-j4':'主案ベースJ','base-k2':'比較ベースK','module-k2':'共通音源K','shield-b2':'共通シールドB'}
 for key in labels:
  a=obs['vendors']['JLCPCB']['boards'][key];b=obs['vendors']['PCBWay']['boards'][key];lines.append(f"| {labels[key]} | {'×'.join(str(v) for v in a['dimensions_mm'])} | {a['layers']} | {a['min_hole_mm']:.2f} | {a['price_usd']:.2f} | {b['price_usd']:.2f} |")
 for variant,label in [('primary','主案の製造費合計'),('comparison','比較案の製造費合計')]:
  v=result['variants'][variant]['vendors'];lines.append(f"| **{label}** | | | | **{v['JLCPCB']['pcb_total_usd']:.2f}** | **{v['PCBWay']['pcb_total_usd']:.2f}** |")
 lines+=['','JLCPCBの0.2mm穴では、2層でもTG155材・Kelvin検査・Pluggedが指定される。2層ではKB材の指定とPluggedの料金も含む。','例：比較ベースは基本/面積4.00＋15.10、ENIG20.20、Plugged16.80、小径穴20.42、Kelvin18.61、TG155材4.08、KB指定4.08＝103.29 USD。','音源KもPlugged16.62、小径穴17.78、Kelvin17.20等を含み80.42 USD。2層の標準特価だけを使った見積ではない。','4層ベースはTG155、2層音源/ベースはKB6165F TG155、シールドはTG135。PCBWayは標準S1000H TG150。材料銘柄は同一ではない。','PCBWayはベース・音源を5/5mil・0.2mm穴、シールドを6/6mil・0.3mm穴で入力した。','Pluggedはソルダーマスク処理で、樹脂充填・銅蓋ではない。パッド内ビアの手作業先埋め条件は[製造資料](../README.md)を参照。','','## 日本向け送料込み（部品代・税別）','','1 USD＝160円を比較用の固定仮定とする。当日の為替やカード決済レートではない。','','| 業者・通常配送 | 主案 USD | 主案 円換算 | 比較案 USD | 比較案 円換算 |','| --- | ---: | ---: | ---: | ---: |']
 for vendor,pick in [('JLCPCB','UPS Worldwide Express Saver'),('JLCPCB','DHL Express'),('PCBWay','SF Express'),('PCBWay','DHL')]:
  rr=[next(m for m in result['variants'][v]['vendors'][vendor]['rates'] if m['name']==pick) for v in ['primary','comparison']];a,b=rr;lines.append(f"| {vendor} / {pick} | {a['delivered_usd']:.2f} | {a['delivered_jpy']:,}円 | {b['delivered_usd']:.2f} | {b['delivered_jpy']:,}円 |")
 lines+=['','主案は調べた通常配送ではJLCPCB/UPSが37,928円、比較案はPCBWay/SFが33,992円。両案の最安同士の差は3,936円。','同じ業者内でベースを2層化するとJLCPCBで22.15 USD（3,544円）、PCBWayで59.04 USD（約9,446円）安い。','費用差だけでは、2層ベースのUSB帰路・電源/熱・音声ノイズの実測結果を判断できない。主案4/2は維持する。','','## 送料の根拠と精度','','- 配送国はJapan。提供済み郵便番号を公開データに保存せず、郵便番号固有の遠隔地料金は未確認。','- JLCPCB：各ロットの包装込み表示0.6615＋0.2940＋0.2520＝1.2075kg、PCB重量0.82kg、最大220×142mm、各案の製造費を入力。','  送料は両案ともUPS9.69、DHL21.60 USD。実カートで3ロット同梱が確定した送料ではない。','- PCBWay：総面積244,200mm²・板厚1.6mmを同じにした送料用の面積等価入力220×222mm×5枚。重量表示0.85kg。','  220×222mmのパネルを製造する指定ではない。両案ともSF18.51、DHL25.18 USD。','- JLCPCBの通常UPS/DHL/FedEx/OCS/SFと、PCBWayのDHL/FedEx-IP/SF/OCSを照会。所有者の運送アカウントを要する2 USD表示は運賃本体として採用しない。','- 送料は3回加算していない。両社の重量推定方式が異なるため、最終同梱梱包・住所・Gerber審査後に変動し得る。','- 輸入消費税・関税・立替/通関料・決済為替手数料、部品代と部品送料は含まない。','','## 部品1セットの扱い','','[購入数量JSON](order-profile.json)は、旧購入表のPCB以外87行を数量・型番・手持ち・包装切上げごと維持する。','旧PCB1〜3行だけは各案の基板に読み替え、部品を5セット分や両案各1セット分へ増やさない。','既存の価格確認分6,290円は今回再調査した価格ではなく、全購入費でもない。未見積品と部品送料が残るため、基板＋部品の確定総額は示さない。','','出典：[JLCPCB公式計算器](https://cart.jlcpcb.com/quote)、[PCBWay公式計算器](https://www.pcbway.com/orderonline.aspx)。','設定をURLから復元できないため、寸法・層・枚数・銅厚・仕上げ・小径穴・配送国を再入力する。','[公開可能な観測値](observations.json)と[再計算結果](comparison.json)を保存。ブラウザーのCookie・ヘッダー・住所は含めない。','']
 (Q/'PCB-QUOTES.md').write_text('\n'.join(lines));print({v:{n:x['cheapest_inspected']['delivered_jpy'] for n,x in d['vendors'].items()} for v,d in result['variants'].items()})
if __name__=='__main__':main()
