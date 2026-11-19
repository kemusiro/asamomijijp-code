#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Reproduce the LC-A cost and envelope study; this does not generate a PCB."""
from pathlib import Path
from decimal import Decimal, ROUND_HALF_UP, ROUND_CEILING
import json,hashlib,html
P=Path(__file__).resolve().parents[1]
def read(name):return json.loads((P/name).read_text())
def dec(x):return Decimal(str(x))
def yen(x):return int(dec(x).quantize(Decimal(1),rounding=ROUND_HALF_UP))
def calculate():
    plan=read('plan.json'); inp=read('cost-inputs.json'); quote=read('pcb-price-observations.json')
    old=read('../procurement-review-d/budget.json')
    rows={r['id']:r for r in old['parts_rows']}
    cost=lambda id:dec(rows[id]['line_gross_reference'])*(160 if rows[id]['currency']=='USD' else 1)
    parts=dec(inp['baseline_goods_jpy']); deltas=[]; seen=set()
    for r in inp['delta']:
        assert not seen.intersection(r['remove']);seen.update(r['remove'])
        removed=sum((cost(x) for x in r['remove']),Decimal(0));added=dec(r['add_jpy'])
        parts+=added-removed
        deltas.append({**r,'removed_jpy':str(removed),'net_change_jpy':str(added-removed)})
    scenarios=[]
    for fallback,existing in [(False,False),(True,False),(False,True)]:
        boards=quote['boards'];prices=[dec(b['price_usd']) for b in boards]
        if fallback:prices[0]=dec(quote['fallback_base']['price_usd'])
        pcb=yen(sum(prices)*160);goods=yen(parts)
        if existing:
            goods=yen(parts-dec(4620)+cost('M01')+cost('M02')+cost('J02')+105)
        parts_freight=inp['existing_mcu_comparison_freight_jpy'] if existing else inp['parts_freight_budget_jpy']
        sub=goods+pcb+parts_freight+quote['shipping']['pcb_freight_budget_jpy']
        reserve=inp['import_and_payment_allowance_jpy']+inp['redesign_small_parts_allowance_jpy']
        total=sub+reserve;step=inp['round_budget_to_jpy']
        scenarios.append({'name':'retain_old_MCUs_and_sockets' if existing else ('direct_modules_120mm_fallback' if fallback else 'direct_modules_100mm'),
                          'parts_goods_jpy':goods,'pcb_goods_jpy':pcb,'parts_freight_allowance_jpy':parts_freight,
                          'pcb_freight_allowance_jpy':quote['shipping']['pcb_freight_budget_jpy'],'subtotal_jpy':sub,'reserve_jpy':reserve,
                          'with_reserve_jpy':total,'rounded_budget_jpy':int((dec(total)/step).to_integral_value(rounding=ROUND_CEILING))*step,
                          'saving_from_old_subtotal_jpy':inp['baseline_subtotal_jpy']-sub})
    old_area=sum(b['old_size_mm'][0]*b['old_size_mm'][1] for b in plan['boards'])
    area=sum(b['size_mm'][0]*b['size_mm'][1] for b in plan['boards'])
    return {'status':'planning_budget_not_quote_or_cad_acceptance','delta':deltas,'scenarios':scenarios,
            'area':{'old_mm2_per_set':old_area,'target_mm2_per_set':area,'reduction_percent':round(100*(1-area/old_area),1)}}

def diagram(plan):
    s=['<svg xmlns="http://www.w3.org/2000/svg" width="1180" height="600" viewBox="0 0 1180 600">',
       '<rect width="1180" height="600" fill="#f5f7fa"/>',
       '<style>text{font-family:Arial,sans-serif;fill:#17314c} .t{font-size:22px;font-weight:bold}.b{font-size:13px}.n{font-size:16px}</style>',
       '<text class="t" x="30" y="34">P2 LC-A: low-cost architecture and board envelope study</text>',
       '<text class="n" x="30" y="62">Target dimensions only - no routed PCB / no ERC, DRC or physical fit acceptance</text>']
    colors=['#e0edf9','#e4f1e7','#fff0d9']
    for j,b in enumerate(plan['boards']):
        ox=30+j*385;oy=120;scale=3.4;w,h=b['size_mm']
        s += [f'<text class="t" x="{ox}" y="100">{b["id"].upper()}: {w} x {h} mm / {b["layers"]}L</text>',
              f'<rect x="{ox}" y="{oy}" width="{w*scale}" height="{h*scale}" fill="white" stroke="#17314c" stroke-width="2"/>']
        for label,x,y,bw,bh in b['blocks']:
            xx=ox+x*scale;yy=oy+y*scale
            s += [f'<rect x="{xx}" y="{yy}" width="{bw*scale}" height="{bh*scale}" rx="3" fill="{colors[j]}" stroke="#8ca5b8"/>']
            words=label.split(' ');lines=[];line='';maxchars=max(8,int(bw*scale/7.3))
            for word in words:
                if len(line+' '+word)>maxchars:lines.append(line);line=word
                else:line=(line+' '+word).strip()
            if line:lines.append(line)
            for n,line in enumerate(lines):
                s.append(f'<text class="b" x="{xx+5}" y="{yy+14+n*14}">{html.escape(line)}</text>')
    s += ['<text class="n" x="30" y="500">Base + sound: G40 logical pinout retained, ordinary 2.54 mm socket/header under evaluation.</text>',
          '<text class="n" x="30" y="528">Editing panel: separate 152 mm IDC cable; four knobs, LCD, encoder, OP / NOTE / STOP, EEPROM retained.</text>',
          '<text class="n" x="30" y="556">100 mm base target; expand to 120 x 100 mm if standard 0.3 mm drill routing needs more room.</text>',
          '<text class="n" x="30" y="584">MCU direct-solder candidate requires RUN breakout wiring and GP24 / GP25 LED load isolation.</text>','</svg>']
    return '\n'.join(s)+'\n'

def outputs():
    d=calculate();plan=read('plan.json');panel=read('panel-connector.json')
    s=['# LC-A 費用と小型化の見通し','',
       '基板各5枚・部品1セット・YM2203C流用。1 USD=160円の比較用仮定。国内税見込を含む。外注実装なし。',
       '入力式製造見積、旧購入資料Dの差分、明示的な予算枠を混ぜた計画値。新規回路図・配線済みPCB・製造承認・確定注文BOMではない。','',
       '| 案 | 部品商品額 | 基板製造 | 部品送料枠 | 基板送料枠 | 小計 | 予備費込み | 切上げ予算 |',
       '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    labels=['Picossci直付け・ベース100mm','Picossci直付け・ベース120mm','旧MCU＋単端子ソケットを維持・100mm']
    for label,r in zip(labels,d['scenarios']):
        s.append('| '+label+' | '+' | '.join(f'{r[k]:,}円' for k in ['parts_goods_jpy','pcb_goods_jpy','parts_freight_allowance_jpy','pcb_freight_allowance_jpy','subtotal_jpy','with_reserve_jpy','rounded_budget_jpy'])+' |')
    s += ['', '旧Dは送料込み小計85,753円、予備費込み92,009円（切上げ95,000円）。新案の予備費は輸入・換算差3,000円＋再設計時小物3,000円。送料も部品7,000円（旧MCU維持比較は5,000円）・PCB3,500円の予算枠で、実カート運賃ではない。',
          'ソケット削減でDigiKey、PGA購入を外したマルツが送料無料基準を下回る可能性があるため、主案の部品送料枠を増やした。',
          '100mm主案の約4.5万円、120mm案の約5万円は、目標寸法・標準加工・部品変更が成立する場合の予算目安。価格保証や販売店確保済みを意味しない。', '',
          '## 部品差分（旧Dの国内税見込後の商品額から計算）','',
          '| 変更 | 旧購入額を除く | 新たに加える | 差額 | 条件 |','| --- | ---: | ---: | ---: | --- |']
    for r in d['delta']:
        s.append(f'| {r["name"]} | {yen(r["removed_jpy"]):,}円 | {yen(r["add_jpy"]):,}円 | {yen(r["net_change_jpy"]):+,}円 | {r["basis"]} |')
    s+=['','600円の支持材、300円のLCD支柱は未選定材料の予算枠。既存H01/H03/H04は残す。LCDを外す削減ではない。H06のキー予算も残すが、一般ソケットとの実嵌合は要確認。',
        'J03はMCU端子128・UNO端子40を除き、残り使用31接点＋切出し予備40接点。40連×2本=80接点・残り49。旧MCU維持比較は40連×5本となるため主案より105円加算。',
        '既存MCU維持比較は細かな新配置成立を保証しない。一般ソケットをMCUへ無加工置換できると仮定せず、元のMill-Max費用を残した保守的比較。','',
        '## 基板入力見積（各5枚、通常納期、鉛フリーHASL）','',
        '| 基板 | 寸法・層 | Web表示額 | 重量表示 |','| --- | --- | ---: | ---: |']
    for b in read('pcb-price-observations.json')['boards']:
        s.append(f'| {b["id"]} | {b["size_mm"][0]}×{b["size_mm"][1]}mm・{b["layers"]}層 | {b["price_usd"]} USD | {b["display_weight_kg"]}kg |')
    s += ['', 'ベース120×100mm・4層は37.70 USD。100mm主案3種は計23.90 USD=3,824円、120mm案は計48.30 USD=7,728円。旧3種227.36 USDと比べた入力条件差であり、既存Gerberをその価格で製造できる意味ではない。',
          '[JLCPCB計算機](https://cart.jlcpcb.com/quote)。クーポン・Desktop価格を使わず、Webの通常納期額を記録。4層標準内層0.5oz、0.3mm穴選択、2層Tented／4層標準Plugged。エポキシ充填・キャリア側端面加工はなし。',
          '3基板の単独重量表示は計0.80kg。画面の単独基板DHL17.67USDを3種同梱送料として転用していない。PCB送料枠3,500円は旧日本向けDHL1.3kg21.60USDを丸めた参考枠。CAM・同梱・住所別運賃は別途確認する。', '',
          f'基板1セットの面積は旧{d["area"]["old_mm2_per_set"]:,}mm²から目標{d["area"]["target_mm2_per_set"]:,}mm²へ、{d["area"]["reduction_percent"]}%減。ベースだけは約68%減、音源は20%減。パネルは向きを変えて同面積を維持。','']
    pin=['# GPIOと編集パネルの静的照合','', '現在のG/H割当のGPIO番号を維持する候補。コネクタの物理位置と端子番号は新規。実装・新基板の通信受入ではない。','',
         '| 基板 | GPIO | 機能・net | Picossci端子 |','| --- | ---: | --- | --- |']
    for board in ['base','sound']:
        for r in plan[board+'_gpio']:
            pin.append(f'| {board} | {r["gpio"]} | {r["net"]} / {r["function"]} | {r["terminal"]} |')
    pin+=['','GP24/25は両モジュールのLED抵抗R5/R6を外して負荷を切り離す候補。baseではLCD DC/CS、soundではI2S DATA/BCK。GPIOを別番号へ移す案ではない。',
          '外部RUNは端面にない。SW1 RESETの非GND端子から追加配線し、基板側コネクタを設ける。sourceは既存MOD_ENABLE→open-drain→RUNの経路を省略しない。baseも外部ハードリセットへ接続。実物導通と部品版の確認が必要。','',
          '## PANEL40（G40とは接続不可）','', '| pin | 信号 | base GPIO |','| ---: | --- | ---: |']
    for r in panel['pins']:pin.append(f'| {r["pin"]} | {r["signal"]} | {r["gpio"] if r["gpio"] is not None else "—"} |')
    pin+=['','3.3V信号のみ、AUX_3V3とIOREF_3V3は別線・別レール。2MHz以下のLCD SPIを分割DMA、100kHzのservice I2CはEEPROM書込待ちをノンブロッキングにする。152mmリボンのSPI/ADCノイズは実機で確認する。',
          'G40の論理40接点・KEY6・3.3Vバス・アナログL/R・任意I2Sは既存Hのまま。新コネクタ位置・支持高さなので、旧基板との物理嵌合は保証しない。通電中の着脱は対象外。','']
    return {'cost-report.json':json.dumps(d,ensure_ascii=False,indent=2)+'\n','COST.md':'\n'.join(s),'PIN-COMPATIBILITY.md':'\n'.join(pin),'layout-study.svg':diagram(plan)}
def main():
    for name,txt in outputs().items():(P/name).write_text(txt)
    files={str(f.relative_to(P)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(P.rglob('*')) if f.is_file() and '__pycache__' not in f.parts and f.name!='manifest.json'}
    (P/'manifest.json').write_text(json.dumps({'files':files},indent=2)+'\n')
    print(json.dumps(calculate()['scenarios'],ensure_ascii=False,indent=2))
if __name__=='__main__':main()
