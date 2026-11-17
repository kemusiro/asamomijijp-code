# 購入一覧 — P2 分離基板 review D

1セット＝ベース1枚＋YM2203C×1音源基板1枚。予備・手持ち控除前。2026-11-16確認。

包装数未確認品の発注単位1は仮置き。検索リンクは型番検索で、在庫・小口販売の保証ではない。
詳細な注意事項は[README](README.md)、実装箇所は[implementation-map.csv](implementation-map.csv)。

## MCU・音源・コネクタ

|ID|品名・型番|1セット|5セット|販売単位|購入先|確認事項|
|---|---|---:|---:|---|---|---|
|M01|ベースMCUモジュール<br>**PGA2350 / PIM722**<br>25.4mm角・64接点|1|5|1個（仮）|[Pimoroni / PIM722](https://shop.pimoroni.com/products/pga2350)|指定型番／在庫・販売単位再確認<br>オスピン別売。ベースのみ1枚。Coreとは互換なし。|
|M02|音源MCUモジュール＋USB書込みアダプター<br>**Core2350B0-Kit**<br>25.4mm角・PSRAMなし|1|5|1個（仮）|[Waveshare / Core2350B0-Kit](https://www.waveshare.com/Core2350B.htm)|指定型番／在庫・販売単位再確認<br>0MB PSRAM / USB adapter Includedを選択。アダプター＋FFC含む。既所有なら基板単体可。|
|M03|実音源IC<br>**YM2203C**<br>DIP40 / 列間15.24mm|1|5|1個（仮）|[手持ち優先・調達先未確定](https://www.digikey.jp/)|手持ち確認／新品販売先未確定<br>既存Rev Cからの転用なら買わない。中古・真贋・動作は個別確認。|
|J01|YM用ICソケット<br>**2227-40-06**<br>DIP40 / 15.24mm|1|5|10個|[秋月 / 100015](https://akizukidenshi.com/catalog/g/g100015/)|販売中を確認<br>1パック10個。MCU用ソケットには使わない。|
|J02|MCU用独立レセプタクル<br>**0300-2-15-15-47-27-10-0**<br>Mill-Max / 0.64mm角ピン対応|128|640|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=0300-2-15-15-47-27-10-0)|指定型番／少数で実装高さ確認<br>ベース64＋音源64。PCB穴1.20mm。最初に少数で挿入深さ・高さを現物確認。|
|J03|1列オス端子（切り出し材料）<br>**PH-1x40SG**<br>1×40 / 2.54mm / 0.64mm角|150|750|40接点（発注は40接点/本）|[秋月 / 100167](https://akizukidenshi.com/catalog/g/g100167/)|販売中を確認<br>数量単位は接点。128接点をMCU、22接点をPCB用に使用。最低4本、作業予備を含め5本推奨。MCU四隅は樹脂干渉回避が必要。|
|J04|基板間ソケット（ベース）<br>**SSW-116-02-G-D**<br>2×16 / 2.54mm / 高8.51mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SSW-116-02-G-D)|指定型番／在庫・販売単位再確認<br>32番を塞ぐ。汎用2×16の高さ違いは不可。|
|J05|基板間オス（音源基板裏面）<br>**TSW-116-07-G-D**<br>2×16 / 2.54mm / 嵌合長5.84mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=TSW-116-07-G-D)|指定型番／在庫・販売単位再確認<br>32番抜去。音源基板の裏面に実装。|
|J06|UNO R3用1列メスヘッダー<br>**SSW-108-02-G-S**<br>1×8 / 2.54mm / 高8.51mm|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SSW-108-02-G-S)|指定型番／在庫・販売単位再確認<br>3.3V I/O専用。シールドの裏面突出5mm以下。|
|J07|UNO R3用1列メスヘッダー<br>**SSW-110-02-G-S**<br>1×10 / 2.54mm / 高8.51mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SSW-110-02-G-S)|指定型番／在庫・販売単位再確認<br>3.3V I/O専用。シールドの裏面突出5mm以下。|
|J08|UNO R3用1列メスヘッダー<br>**SSW-106-02-G-S**<br>1×6 / 2.54mm / 高8.51mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SSW-106-02-G-S)|指定型番／在庫・販売単位再確認<br>3.3V I/O専用。シールドの裏面突出5mm以下。|
|J09|UNO ICSP用オスヘッダー<br>**TSW-103-07-G-D**<br>2×3 / 2.54mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=TSW-103-07-G-D)|指定型番／在庫・販売単位再確認<br>ICSPはメスではなくオス。UNO形状の3.3V SPI用。|
|J10|USB-Cレセプタクル<br>**TYPE-C-31-M-12**<br>HRO / 16接点 / 指定フットプリント|1|5|1個（仮）|[LCSC / 型番検索](https://www.lcsc.com/search?q=TYPE-C-31-M-12)|候補型番／シェル・穴寸法確認<br>同じUSB-Cでも取付穴とシェル寸法が異なる。HRO指定品の寸法図を照合。|

## IC・半導体・水晶・保護部品

|ID|品名・型番|1セット|5セット|販売単位|購入先|確認事項|
|---|---|---:|---:|---|---|---|
|U01|可変クロック生成<br>**Si5351A-B-GT**<br>MSOP10 / 0.5mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products/detail/skyworks-solutions-inc/SI5351A-B-GT/3679847)|指定型番／在庫・販売単位再確認<br>秋月のSi5351Aモジュールは不可。IC単体。|
|U02|ステレオDAC<br>**PCM5102APWR**<br>TSSOP20 / 0.65mm|1|5|1個（仮）|[共立エレショップ](https://eleshop.jp/shop/g/gEAO411/)|指定型番／在庫・販売単位再確認<br>秋月DACキットではなくIC単体。|
|U03|SSG用ADC<br>**PCM1863DBT**<br>TSSOP30 / 0.5mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products/detail/texas-instruments/PCM1863DBT/4895616)|指定型番／在庫・販売単位再確認<br>TSSOP30指定。基板モジュール不可。|
|U04|音声オペアンプ<br>**MCP6022-I/SN**<br>SOIC8 / 1.27mm|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=MCP6022-I%2FSN)|指定型番／在庫・販売単位再確認<br>|
|U05|アナログ出力ゲート<br>**CD74HC4053M**<br>SOIC16 / 1.27mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=CD74HC4053M)|指定型番／在庫・販売単位再確認<br>CD4053Bではない。HC版を指定。|
|U06|LED・スイッチI/O<br>**MCP23017-E/SO**<br>SOIC28W / 1.27mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=MCP23017-E%2FSO)|指定型番／在庫・販売単位再確認<br>-E/SOのワイドSOIC指定。DIP/SSOP不可。|
|U07|3.3V LDO<br>**TLV75533PDBVR**<br>SOT23-5|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=TLV75533PDBVR)|指定型番／在庫・販売単位再確認<br>入力・出力MLCCのDCバイアス後容量を確認。|
|U08|シュミットバッファ<br>**SN74LVC1G17DBVR**<br>SOT23-5|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SN74LVC1G17DBVR)|指定型番／在庫・販売単位再確認<br>|
|U09|ANDゲート<br>**SN74LVC1G08DBVR**<br>SOT23-5|6|30|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SN74LVC1G08DBVR)|指定型番／在庫・販売単位再確認<br>|
|U10|4回路レベル変換バッファ<br>**SN74LV4T125PWR**<br>TSSOP14 / 0.65mm|7|35|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products/detail/texas-instruments/SN74LV4T125PWR/4806529)|指定型番／在庫・販売単位再確認<br>LV4T125指定。LVC125/HC125へ置換不可。|
|U11|8bit双方向レベル変換<br>**SN74LVC8T245PWR**<br>TSSOP24 / 0.65mm|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SN74LVC8T245PWR)|指定型番／在庫・販売単位再確認<br>二電源型指定。|
|U12|YMクロックレベル変換<br>**SN74LVC1T45DBVR**<br>SOT23-6|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SN74LVC1T45DBVR)|指定型番／在庫・販売単位再確認<br>|
|U13|オープンドレインバッファ<br>**SN74LVC1G07DBVR**<br>SOT23-5|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SN74LVC1G07DBVR)|指定型番／在庫・販売単位再確認<br>|
|U14|ADCデータバッファ<br>**SN74LVC1G125DBVR**<br>SOT23-5|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=SN74LVC1G125DBVR)|指定型番／在庫・販売単位再確認<br>|
|U15|ADC入力保護スイッチ<br>**TMUX1511PWR**<br>TSSOP14 / 0.65mm|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=TMUX1511PWR)|指定型番／在庫・販売単位再確認<br>powered-off protectionを維持。|
|U16|USB ESD保護<br>**USBLC6-2SC6**<br>SOT23-6|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=USBLC6-2SC6)|指定型番／在庫・販売単位再確認<br>|
|Q01|NPNトランジスター<br>**MMBT3904LT1G**<br>SOT23|3|15|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=MMBT3904LT1G)|指定型番／在庫・販売単位再確認<br>|
|D01|ADC入力クランプ<br>**BAT54S,215**<br>SOT23 / 直列2ダイオード|3|15|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=BAT54S%2C215)|指定型番／在庫・販売単位再確認<br>BAT54A/C不可。直列S品、pin3が中点。|
|X01|Si5351A用水晶<br>**ABM8-25.000MHZ-10-B1U-T**<br>3225 / 4pad / 25MHz / CL10pF|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=ABM8-25.000MHZ-10-B1U-T)|候補型番／端子図・流通単位確認<br>10ppm品候補。1/3が水晶、2/4がケースGNDの図面照合を行う。発振器完成品は不可。|
|F01|リセッタブルヒューズ<br>**MF-MSMF150/16X-2**<br>1812 / Ihold1.5A@23℃|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=MF-MSMF150%2F16X-2)|指定型番／在庫・販売単位再確認<br>旧案の1.1A品へ戻さない。|
|L01|フェライトビーズ<br>**BLM21PG601SN1D**<br>0805 / 600Ω@100MHz|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=BLM21PG601SN1D)|指定型番／在庫・販売単位再確認<br>回路BOM末尾省略を流通型番Dに具体化。|

## 操作・表示

|ID|品名・型番|1セット|5セット|販売単位|購入先|確認事項|
|---|---|---:|---:|---|---|---|
|S01|タクトスイッチ6個共通<br>**SKHHALA010**<br>6×6mm / H4.3mm / 4本足|6|30|1個|[DigiKey / 4809-SKHHALA010-ND](https://www.digikey.jp/ja/products/detail/alps-alpine/SKHHALA010/19529104)|販売中を確認<br>4本足・6mm角・高さ4.3mm。秋月108215（2本足）/107193（高型）は不可。|
|S02|クロック選択4bit DIP<br>**209-4LPST**<br>DIP8 / 2.54mm / 列間7.62mm / low-profile|1|5|10個|[共立エレショップ（Farnell取寄） / 3778093](https://eleshop.jp/shop/g/g3778093/)|販売ページ確認／外形最終照合<br>KiCad footprint参照CTS209シリーズ。秋月EDS104SZは外形が異なるため未採用。注文単位10個。|
|LED01|RX・6声表示LED<br>**OSG8HA3Z74A**<br>3mm THT / 緑 / 無抵抗|7|35|1個|[秋月 / 111637](https://akizukidenshi.com/catalog/g/g111637/)|販売中を確認<br>7個を同色で統一。抵抗内蔵5V品・自己点滅品を選ばない。|

## 抵抗

|ID|品名・型番|1セット|5セット|販売単位|購入先|確認事項|
|---|---|---:|---:|---|---|---|
|R01|10kΩ チップ抵抗<br>**RG2012-N-103-B-T5**<br>0805 / 2012M / 0.1%|34|170|5個|[秋月 / 111797](https://akizukidenshi.com/catalog/g/g111797/)|販売中を確認<br>汎用/1%指定箇所も0.1%品に統一。|
|R02|100kΩ チップ抵抗<br>**RG2012N-104-B-T5**<br>0805 / 2012M / 0.1%|40|200|5個|[秋月 / 111798](https://akizukidenshi.com/catalog/g/g111798/)|販売中を確認<br>汎用/1%指定箇所も0.1%品に統一。|
|R03|1kΩ チップ抵抗<br>**RG2012N-102-B-T5**<br>0805 / 2012M / 0.1%|10|50|5個|[秋月 / 111796](https://akizukidenshi.com/catalog/g/g111796/)|販売中を確認<br>汎用/1%指定箇所も0.1%品に統一。|
|R04|5.1kΩ チップ抵抗<br>**RC0805FR-075K1L**<br>0805 / 2012M|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-075K1L)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R05|47k 0.1%Ω チップ抵抗<br>**RT0805BRD0747KL**<br>0805 / 2012M|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RT0805BRD0747KL)|指定型番／在庫・販売単位再確認<br>VBUS検出用、0.1%指定を厳守。|
|R06|68k 0.1%Ω チップ抵抗<br>**RT0805BRD0768KL**<br>0805 / 2012M|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RT0805BRD0768KL)|指定型番／在庫・販売単位再確認<br>VBUS検出用、0.1%指定を厳守。|
|R07|2.2kΩ チップ抵抗<br>**RC0805FR-072K2L**<br>0805 / 2012M|4|20|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-072K2L)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R08|33Ω チップ抵抗<br>**RC0805FR-0733RL**<br>0805 / 2012M|18|90|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-0733RL)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R09|470Ω チップ抵抗<br>**RC0805FR-07470RL**<br>0805 / 2012M|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-07470RL)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R10|47kΩ チップ抵抗<br>**RC0805FR-0747KL**<br>0805 / 2012M|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-0747KL)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R11|100Ω チップ抵抗<br>**RG2012N-101-B-T5**<br>0805 / 2012M / 0.1%|2|10|5個|[秋月 / 111795](https://akizukidenshi.com/catalog/g/g111795/)|販売中を確認<br>汎用/1%指定箇所も0.1%品に統一。|
|R12|0Ω チップ抵抗<br>**RK73Z2ATTD**<br>0805 / 2012M|1|5|10個|[マルツ / M1559-080](https://www.marutsu.co.jp/pc/i/1559080/)|販売中を確認<br>最小10個・10個単位。秋月111622は販売終了。|
|R13|4.7kΩ チップ抵抗<br>**RC0805FR-074K7L**<br>0805 / 2012M|6|30|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-074K7L)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R14|1.33kΩ チップ抵抗<br>**RC0805FR-071K33L**<br>0805 / 2012M|3|15|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-071K33L)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R15|680Ω チップ抵抗<br>**RC0805FR-07680RL**<br>0805 / 2012M|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-07680RL)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|
|R16|3.01kΩ チップ抵抗<br>**RC0805FR-073K01L**<br>0805 / 2012M|3|15|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=RC0805FR-073K01L)|指定型番／在庫・販売単位再確認<br>許容差±1%以下を指定。|

## コンデンサー

|ID|品名・型番|1セット|5セット|販売単位|購入先|確認事項|
|---|---|---:|---:|---|---|---|
|C01|積層セラミック 100nF / X7R / 50V<br>**GRM21BR71H104KA01L**<br>0805 / 2012M|43|215|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=GRM21BR71H104KA01L)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C02|積層セラミック 10µF / X7R / 10V<br>**GRM21BR71A106KE51**<br>0805 / 2012M|9|45|10個|[秋月 / 117593](https://akizukidenshi.com/catalog/g/g117593/)|販売中を確認<br>0805/2012M。X7Rを維持。|
|C03|積層セラミック 2.2µF / X7R / 25V<br>**GRM21BR71E225KE11**<br>0805 / 2012M|5|25|10個|[秋月 / 114788](https://akizukidenshi.com/catalog/g/g114788/)|在庫僅少／再確認<br>0805/2012M。X7Rを維持。|
|C04|積層セラミック 1µF / X7R / 10V<br>**CL21B105KPFNNNE**<br>0805 / 2012M|2|10|40個|[秋月 / 107549](https://akizukidenshi.com/catalog/g/g107549/)|販売中を確認<br>0805/2012M。X7Rを維持。|
|C05|積層セラミック 4.7µF / X7R / 16V<br>**GRM21BR71C475KE51**<br>0805 / 2012M|5|25|20個|[秋月 / 131147](https://akizukidenshi.com/catalog/g/g131147/)|販売中を確認<br>仕様・サイズ適合。LDO用4.7µFは3.3V/5Vバイアス後の実効容量1µF以上を確認。|
|C06|積層セラミック 22µF / X7R / 10V<br>**GRM21BZ71A226ME15L**<br>0805 / 2012M|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=GRM21BZ71A226ME15L)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C07|積層セラミック 1nF / C0G / 50V<br>**CC0805JRNPO9BN102**<br>0805 / 2012M|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN102)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C08|積層セラミック 100pF / C0G / 50V<br>**CC0805JRNPO9BN101**<br>0805 / 2012M|1|5|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN101)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C09|積層セラミック 2.2nF / C0G / 50V<br>**CC0805JRNPO9BN222**<br>0805 / 2012M|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN222)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C10|積層セラミック 47pF / C0G / 50V<br>**CC0805JRNPO9BN470**<br>0805 / 2012M|2|10|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN470)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C11|積層セラミック 470pF / C0G / 50V<br>**CC0805JRNPO9BN471**<br>0805 / 2012M|3|15|1個（仮）|[DigiKey](https://www.digikey.jp/ja/products?keywords=CC0805JRNPO9BN471)|候補型番／現行仕様・カットテープ確認<br>値・誘電体・耐圧・DCバイアス容量を照合。1608M(0603)品は不可。|
|C12|電源電解100µF<br>**16MH5100MEFC6.3X5**<br>100µF16V / D6.3 / P2.5mm|1|5|1個|[秋月 / 105002](https://akizukidenshi.com/catalog/g/g105002/)|販売中を確認<br>指定10V以上を満たす16V品。|
|C13|音声用無極性電解4.7µF<br>**50NXA4R7MEFC5X11**<br>4.7µF50V / D5 / H11 / P2mm|4|20|1個|[秋月 / 130140](https://akizukidenshi.com/catalog/g/g130140/)|販売中を確認<br>必ず無極性。極性付き電解は不可。|

## 基板外部材・基板

|ID|品名・型番|1セット|5セット|販売単位|購入先|確認事項|
|---|---|---:|---:|---|---|---|
|E01|音量ボリューム<br>**JH16T2A103L20KC**<br>A10kΩ / 2連 / ラグ / 軸6mm|1|5|1個|[秋月 / 116478](https://akizukidenshi.com/catalog/g/g116478/)|販売中を確認<br>|
|E02|ステレオLINE出力ジャック<br>**MJ-073H**<br>3.5mm TRS / パネル穴8.2mm|1|5|1個|[秋月 / 106257](https://akizukidenshi.com/catalog/g/g106257/)|販売中を確認<br>JPOT/JLINEは配線式。JLINE 1=L 2=GND 3=R。ヘッドホン直駆動用ではない。|
|E03|ボリューム用ノブ<br>**6mmローレット軸適合**<br>外径はケースに合わせる|1|5|1個（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>軸・ケース設計後に選定。|
|E04|基板間スペーサー<br>**M3絶縁・高さ調整式**<br>嵌合後11.05mm公称に合わせる|4|20|1個（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|現物合わせ<br>ワッシャー併用。固定11mmで基板を引き寄せない。|
|E05|ベース足スペーサー<br>**M3絶縁・高さ8mm以上**<br>外周4箇所|4|20|1個（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>下面ソケットはんだ・端子との干渉を避ける。|
|E06|UNOシールド支柱<br>**M3絶縁・シールドに合わせる**<br>H9/H10/H12の3箇所|3|15|1個（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|現物合わせ<br>H11は裸パッド。固定ねじ不可。シールドを使う場合。|
|E07|絶縁ねじ・ナット・ワッシャー<br>**M3 / 2枚厚と支柱に合わせる**<br>長さ要採寸|1|5|1式（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>ベース4、基板間4、UNO3の各取付箇所用一式。金属頭は配線に接触させない。|
|E08|外部安定化電源<br>**5.1V級・2A以上**<br>JPOWER入力・極性厳守|1|5|1個（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>YM端子の負荷時4.75..5.25Vを確認。USB VBUSは電源でなく検出専用。|
|E09|電源配線・変換アダプター<br>**2.54mm 2極メス＋太い短い配線**<br>実電源と整合・2A対応|1|5|1式（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>細い杜邦ジャンパーで電源を給電しない。電源側コネクタ未確定。|
|E10|音量・LINE配線<br>**JPOT6極＋JLINE3極メス・シールド線**<br>2.54mm / 短い配線|1|5|1式（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>コネクタハウジング＋圧着端子または組立済みコード。|
|E11|HOST接続ケーブル<br>**JHOST 4極 2.54mm**<br>SDA/SCL/GND・3.3V|1|5|1式（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|要選定<br>既存操作Picoを流用。JHOSTに電源供給用ピンはない。|
|E12|USBデータケーブル<br>**PC側適合⇔USB-C**<br>充電専用不可|1|5|1個（仮）|[手持ち優先／仕様で選定](https://akizukidenshi.com/)|手持ち優先<br>Core書込みアダプターにも使用可能。|
|PCB1|ベースPCB<br>**p2-base-d**<br>194×142mm / 4層 / 1.6mm|1|5|1個（仮）|[PCB製造業者](https://jlcpcb.com/)|基板発注前確認<br>銅箔GND面、穴公差、コネクタ嵌合を図面で確認。|
|PCB2|音源PCB<br>**p2-ym2203-d**<br>100×100mm / 4層 / 1.6mm|1|5|1個（仮）|[PCB製造業者](https://jlcpcb.com/)|基板発注前確認<br>5箇所のpad内viaは手実装時の予備はんだ・平坦化、または充填を指定。|
