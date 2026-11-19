# 購入資料 review D：部品1セット・基板各5枚の総購入予算

2026-11-19確認。ベースL（220×142 mm・4層）、音源K（100×100 mm・2層）、開口なしシールドB（76×100 mm・2層）を各5枚、実装部品は1セット。YM2203Cはユーザー回答に従いRev Cから1個流用する。

残っていた18行すべてに販売先・販売単位・価格の根拠または流用条件を与えた。生産終了コンデンサ2種類、キー栓、厚さ合わせ材料、ハーネスは**購入予算用の候補**であり、正式なBOM置換・現物の適合確認まで完了した意味ではない。既存87部品行を、ハーネス材料の共同使用を含む96購入行で網羅する。

- [送料込み総額・業者別内訳・為替感度](TOTAL.md)
- [96行の購入数量と販売先](PURCHASES.md)／[根拠・注記付き入力JSON](purchase-plan.json)
- [生産終了品の代替候補・配線と機構の確認事項](SUBSTITUTIONS.md)
- [送料観測・適用条件](freight-observations.json)／[計算結果JSON](budget.json)

送料込み小計はカタログ額と送料表示の条件付き合算。予備費込み予算はTOTAL.mdを参照。すべて即納・在庫確保済みの一括発注見積ではない。国外分の税・通関・換算手数料、住所別追加送料、CAM査定、分納は未確定であり、未確定費用を0円と断定しない。

## 前回未確定18行の扱い

| B ID | 今回の購入条件 | 結果 |
| --- | --- | --- |
| M03 | Rev CからYM2203Cを1個流用 | 新規購入0円。実際の移設は未実施 |
| X01 | ABM8-25.000MHZ-10-B1U-T、DigiKey CT1個、90円税別 | 25 MHz、CL10 pF、3.2×2.5 mmを維持 |
| F01 | MF-MSMF200/16X-2、DigiKey CT1個、139円税別 | 2 A hold/16 V/1812。旧包装説明の1.5 Aと混同しない |
| L01 | BLM21PG601SN1D、DigiKey CT1個、31円税別 | 同一型番 |
| R05 | RT0805BRD0747KL、DigiKey CT1個、20円税別 | 47 kΩ・0.1%、表示在庫7434個 |
| R06 | RT0805BRD0768KL、DigiKey CT1個、20円税別 | 68 kΩ・0.1%、表示在庫4567個 |
| R07 | RC0805FR-072K2L、DigiKey CT10個、6.3円/個税別 | 必要6個。10個63円が6個96円より安い |
| R14 | RC0805FR-071K33L、DigiKey CT3個、17円/個税別 | 必要3個、MOQ1 |
| R17 | RC0805FR-076K81L、DigiKey CT2個、18円/個税別 | DigiReelの別価格・加工料を使わない |
| C01 | C0805C104K5RACTU、DigiKey CT28個、16.5円/個税別 | 旧Murata品の代替候補。10個以上価格、MOQ1 |
| C08 | CC0805JRNPO9BN101、DigiKey CT1個、38円税別 | 100 pF・C0G・50 V・5%を維持 |
| C09 | C0805C222J5GACTU、DigiKey CT2個、120円/個税別 | 旧YAGEO品の代替候補、MOQ1 |
| C11 | CC0805JRNPO9BN471、DigiKey CT2個、28円/個税別 | 470 pF・C0G・50 V・5%を維持 |
| H05 | BRB003007100/005/010、モノタロウ各7枚 | 1 mm本体と0.05/0.1 mm調整リングを別計上 |
| H06 | Samtec PK-01-06、DigiKey SKU販売個1、109円税別 | 6栓wheel表記。販売商品数とキー本数を区別 |
| E09 | AWG22、QI2P、接点、DCジャック端子台 | 15 cm程度の電源ハーネス材料 |
| E10 | 1芯シールド線3 m、QI6P/3P、共有接点等 | 音量・L/Rハーネス材料、端末を自作 |
| E11 | QI4P/1P、共有AWG22と接点 | HOST GP0/GP1/GND、電源線を追加しない |

単価の確認方法（live_product / indexed_catalog / 保存B/C）と確認日は各JSON行に記載。検索索引の在庫は当日の即納保証ではない。

## 今すぐ全品揃うと断定しない部品

- U01 Si5351A-B-GT：DigiKey表示在庫0、12/11入荷予定95個。予定は確約ではない。同一GT品の361円税別を予算に残した。
- U07 TLV1117LV33DCYR：指定TI品はDigiKey在庫0、LCSC直接在庫も0。54円税別のカタログ値で予算化し、納期は未確定。端子互換だけで別LDOへ変更しない。
- U16 USBLC6-2SC6（ST）：DigiKey表示在庫0、11/23入荷予定。別メーカーの同名品を採用していない。
- R04 5.1 kΩ指定品、C03 2.2 µF指定品は保存した確認で入荷待ち。M01 PGA2350は取り寄せ先在庫の古い表示、U02 DACも販売店の即納数は非公開。購入直前に価格と納期を確認する。
- U14は同一TI SN74LVC1G125DBVR、D01は同一Nexperia BAT54S,215をLCSC在庫品へ集約。U14は必要1に対し10個、D01は必要2に対し20個購入。長いバックオーダーのDigiKey注文を避ける候補。

これらは「価格未確認18行」を閉じた後に残る**在庫・納期の発注条件**であり、無償・手持ちとして扱っていない。

## 送料と数量の注意

国内は秋月550円、共立550円、モノタロウ550円、DigiKey/マルツは金額条件を満たす1配送として0円。Waveshareはキット1個5.99 USD＋E-packet 9 USD。LCSCは5 SKU 5.09 USD＋送料5.86 USD＋少額取扱料3 USD＝13.95 USDを予算化（画面の期間割引0.07 USDを使わない）。

Waveshare・LCSCは日本を選択した匿名画面、郵便番号や住所は未入力。PCB送料も保存Cの国別入力条件であり、個別住所の確定運賃ではない。住所・氏名等を資料へ含めない。見積確認に使った一時カートは発注ではなく、注文・決済・規約同意をしていない。

H02 ASB-2012EはマルツMOQ50個（4個使用・46個余り）。メーカー直販には20個袋1320円税別の掲載もあるが送料未確定なので主計算へ混ぜない。[廣杉直販](https://www.hirosugi-net.co.jp/shop/c/c10101013/)。

## 保存範囲と検証

B/C、CAD、回路図、ファームウェア、HOSTプレーヤーは変更しない。ソケット・シールド・ADC入力容量等の現物確認も引き続き必要。Rev Cの受入結果をP2へ流用しない。PCB各5枚のうち各1枚を実装し、各4枚（合計12枚）は予備。

```sh
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/procurement-review-d/tools/build_budget.py
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/procurement-review-d/tools/verify.py
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/procurement-review-c/tools/verify.py
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/primary-order-review-b/tools/verify.py
git diff --check
```

Python標準ライブラリのみ。build_budget.pyの再計算、MOQ・袋入数・共有材料の網羅、税・通貨・送料の整合、保存B/C/CADのSHA-256を検査する。CAD変更がないためERC/DRCの再実行は行わず、過去の検査記録を維持する。購入・実組立・P2実機受入は未実施。commit・pushは今回行わない。
