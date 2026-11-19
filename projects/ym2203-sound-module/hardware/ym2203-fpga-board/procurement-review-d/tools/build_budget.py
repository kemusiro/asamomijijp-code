#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the explicitly conditional procurement review D budget."""
from pathlib import Path
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
import hashlib
import json

P=Path(__file__).resolve().parents[1]
D=lambda x: Decimal(str(x))
def read(name): return json.loads((P/name).read_text())
def yen(x): return int(D(x).quantize(D(1),rounding=ROUND_HALF_UP))
def units(need,pack,minimum,multiple):
    if need <= 0: return 0
    count=max(minimum,int((D(need)/D(pack)).to_integral_value(rounding=ROUND_CEILING)))
    return ((count+multiple-1)//multiple)*multiple

def calculate():
    plan=read('purchase-plan.json'); freight=read('freight-observations.json')
    fx=D(plan['assumptions']['jpy_per_usd']); rows=[]; vendors={}
    for raw in plan['rows']:
        r=raw.copy()
        need=max(0,r['required']+r['spare_target']-r['stock'])
        qty=units(need,r['pack'],r['minimum'],r['multiple'])
        if r['order_override'] is not None: qty=r['order_override']
        money=D(r['price'])*qty
        # Overseas cart line totals are displayed to two decimals, not fractions of a cent.
        if r['currency']=='USD': money=money.quantize(D('.01'),rounding=ROUND_HALF_UP)
        gross=money*(D('1.1') if r['tax']=='excluded' else D(1))
        r.update(order_units=qty,purchased_units=qty*r['pack'],
                 remaining_units=r['stock']+qty*r['pack']-r['used'],
                 line_goods=str(money),line_gross_reference=str(gross))
        rows.append(r)
        key='共立エレショップ' if r['supplier'].startswith('共立') else r['supplier']
        v=vendors.setdefault(key,{'currency':r['currency'],'goods':D(0),'gross':D(0),'freight':D(0),'handling':D(0)})
        assert v['currency']==r['currency']
        v['goods']+=money; v['gross']+=gross
    for f in freight['retailers']:
        vendors[f['supplier']]['freight']=D(f['fee_jpy'])
    for f in freight['international']:
        v=vendors[f['supplier']]; v['freight']=D(f['fee_usd']); v['handling']=D(f['handling_usd'])
        assert v['goods']==D(f['goods_usd'])
    vendor_out=[]; parts=D(0); domestic=D(0); imported=D(0); goods_jpy=D(0)
    for name,v in vendors.items():
        rate=fx if v['currency']=='USD' else D(1)
        all_in=D(yen((v['gross']+v['freight']+v['handling'])*rate))
        parts+=all_in;goods_jpy+=D(yen(v['gross']*rate))
        if v['currency']=='USD': imported+=all_in
        else: domestic+=all_in
        vendor_out.append({'supplier':name,**{k:str(val) for k,val in v.items()},'delivered_jpy':yen(all_in)})
    choices=[]
    for name in ['primary','comparison']:
        q=freight['pcb'][name]; pcb=D(yen(D(q['total_usd'])*fx))
        total=parts+pcb
        reserve=D(yen((imported+pcb)*D(freight['reserve']['imported_value_fraction'])+D(freight['reserve']['clearance_and_fx_jpy'])))
        with_reserve=total+reserve
        choices.append({**q,'pcb_delivered_jpy':yen(pcb),'parts_delivered_jpy':yen(parts),
                        'subtotal_jpy':yen(total),'reserve_jpy':yen(reserve),'with_reserve_jpy':yen(with_reserve),
                        'rounded_budget_jpy':int((with_reserve/D(5000)).to_integral_value(rounding=ROUND_CEILING))*5000})
    sensitivities=[]
    for rate in [150,160,170]:
        q=freight['pcb']['primary']
        imp=sum(D(yen((v['gross']+v['freight']+v['handling'])*rate)) for v in vendors.values() if v['currency']=='USD')+D(yen(D(q['total_usd'])*rate))
        sub=domestic+imp
        reserve=D(yen(imp*D('.1')+D(2000)))
        sensitivities.append({'jpy_per_usd_assumption':rate,'subtotal_jpy':yen(sub),'with_reserve_jpy':yen(sub+reserve)})
    return {'checked':plan['checked'],'not_a_final_quote':True,'parts_rows':rows,'vendors':vendor_out,
            'parts_goods_jpy':yen(goods_jpy),'parts_freight_handling_jpy':yen(parts-goods_jpy),
            'parts_delivered_jpy':yen(parts),'pcb_comparison':choices,'fx_sensitivity':sensitivities}

def outputs():
    data=calculate()
    out={'budget.json':json.dumps(data,ensure_ascii=False,indent=2)+'\n'}
    s=['# 購入候補96行・部品1セット分','',
       '2026-11-19のカタログ／画面観測に基づく条件付き予算。注文書ではない。円の税別価格は別途10%を予算加算し、USD商品は輸入税等を含まない。',
       '「数量」は販売単位数。「購入数」「余り」はその行の単位であり、m・セット・SKU販売個を物理接点の個数と混同しない。H06の余栓数は受取時確認。',
       '秋月を基本にし、指定IC・基板に合うソケット等を他店で補完。索引由来の在庫は当日の確保を意味しない。全行の注記・根拠はpurchase-plan.json。','',
       '| ID / B対応 | 購入候補・販売店 | 必要＋指定予備 | 袋入数／MOQ／倍数 | 注文単位 | 購入数／余り | 商品小計（元通貨） | 入手条件 |',
       '| --- | --- | ---: | --- | ---: | --- | ---: | --- |']
    for r in data['parts_rows']:
        s.append(f'| {r["id"]} / {",".join(r["covers"])} | [{r["offered_mpn"]}]({r["url"]}) / {r["supplier"]} {r["sku"]} | {r["required"]}+{r["spare_target"]} | {r["pack"]}/{r["minimum"]}/{r["multiple"]} | {r["order_units"]} | {r["purchased_units"]}/{r["remaining_units"]} | {r["line_goods"]} {r["currency"]}・{r["tax"]} | {r["availability"]} |')
    s+=['','M03は流用1個、新規注文0。H05A/B/Cは7位置分の厚さ合わせ用材料3種で、3種すべてを各位置へ重ねる指示ではない。',
         'J02は128本の単端子ソケットを購入。J03は使用199接点＋切出し予備40接点で40連×6本、残り41接点。',
         'R07は6個×16円より10個×6.3円が安いため10個を選択。H02は小売店MOQ50個のため4個使用・46個余る。','']
    out['PURCHASES.md']='\n'.join(s)
    s=['# 送料込み比較','', '1 USD＝160円の比較用仮定。相場照会ではない。国内税込額・国外USD表示を区別し、販売店ごとの円換算額を1円へ四捨五入して合算。実際の請求書との丸め差は残る。','',
       '| 購入先 | 商品額（税別／税込は入力表参照） | 国内税見込後の商品額 | 送料＋取扱料 | 配送込み円換算 |','| --- | ---: | ---: | ---: | ---: |']
    for v in data['vendors']:
        s.append(f'| {v["supplier"]} | {v["goods"]} {v["currency"]} | {v["gross"]} {v["currency"]} | {D(v["freight"])+D(v["handling"])} {v["currency"]} | {v["delivered_jpy"]:,}円 |')
    s+=['',f'部品商品額（国内税見込を含む）{data["parts_goods_jpy"]:,}円＋部品送料・取扱料{data["parts_freight_handling_jpy"]:,}円＝部品配送込み{data["parts_delivered_jpy"]:,}円。', '',
       '| PCB業者・送料方式 | PCB3種各5枚＋送料 | 部品配送込みを合算 | 自主予備費 | 予備費込み | 切上げ予算 |',
       '| --- | ---: | ---: | ---: | ---: | ---: |']
    for c in data['pcb_comparison']:
        s.append(f'| {c["vendor"]} / {c["method"]} | {c["total_usd"]} USD / {c["pcb_delivered_jpy"]:,}円 | {c["subtotal_jpy"]:,}円 | {c["reserve_jpy"]:,}円 | {c["with_reserve_jpy"]:,}円 | {c["rounded_budget_jpy"]:,}円 |')
    s+=['','予備費はPCB・Waveshare・LCSCの円換算配送込み額の10%＋2,000円。税関の課税価格・税額を計算した値ではなく、輸入時費用・決済換算差等を見込む任意の予算枠。国内税込・DigiKeyに二重加算しない。',
        '国外商品・配送表示に輸入消費税・通関立替料・カード換算手数料を全て含む保証はない。住所別追加送料、実際のCAM査定、分納も未確定。LCSCの期間割引0.07 USDは予算から除外。','',
        '| 為替仮定（円/USD） | JLCPCB案・送料込み小計 | 自主予備費込み |', '| ---: | ---: | ---: |']
    for x in data['fx_sensitivity']:
        s.append(f'| {x["jpy_per_usd_assumption"]} | {x["subtotal_jpy"]:,}円 | {x["with_reserve_jpy"]:,}円 |')
    s+=['','PCB仕様と6つの送料比較は保存した[review C](../procurement-review-c/PCB-QUOTES.md)。今回の送料の観測条件・URLはfreight-observations.json。新たなGerberアップロード・注文・規約同意はしていない。','']
    out['TOTAL.md']='\n'.join(s)
    return out

def main():
    for name,content in outputs().items(): (P/name).write_text(content)
    files={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest()
           for f in sorted(P.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.name!='manifest.json'}
    (P/'manifest.json').write_text(json.dumps({'files':files},indent=2)+'\n')
    data=calculate(); print(json.dumps({k:v for k,v in data.items() if k not in ['parts_rows','vendors']},ensure_ascii=False,indent=2))
if __name__=='__main__': main()
