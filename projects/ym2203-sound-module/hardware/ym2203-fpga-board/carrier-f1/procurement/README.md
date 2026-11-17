# ULX3S 85Fキャリア：購入用部品表

2026-11-15確認。現回路図レビューAを基準に、**1台分**の必要数と発注単位を分けた。
5台分はCSVの別列に記載する。予備は袋の余り以外に加算していない。
秋月を優先し、現行footprintで揃わない部品はDigiKey／Mouser等へ回す。
価格・在庫は閲覧時点で、予約・発注は実行していない。

- [全165refと追加部材の調達CSV](purchasing-bom.csv)：回路図側の必要数、候補、package、確認状態。
- [秋月注文単位CSV](akizuki-order.csv)：共通部品の重複をまとめた購入数。サイトの自動取込形式とは限らない。
- [集計・対象BOMのSHA記録](verification.json)。
- 元の[回路図・設計BOM](../README.md)は変更していない。

**回路図レビュー段階の調達候補表で、製造確定BOMではない。**
ULX3S現物のPCB revision／header向き・高さ、clock電気条件、PTCの抵抗と電源余裕、
未確認の他店在庫・価格を確定してから一括発注する。

## 秋月で購入候補を確認したもの

抵抗は2012（0805）で統一。10kΩと100kΩは通常のpull抵抗・アナログ用と精密用をまとめ、
秋月で確認できた±0.1%品へ統一する案。一般品を他店へまとめる方が安くなる場合がある。
10µFは25V品、bipolarは50V品で、回路図の最低定格を満たす。

| 商品・販売コード | 必要数／1台 | 注文数／1台 | 注文単位の税込価格 | 小計 |
| --- | ---: | ---: | ---: | ---: |
| [118147 2x20 pin socket 2.54mm vertical](https://akizukidenshi.com/catalog/g/g118147/) | 2個 | 2単位 | ¥60 | ¥120 |
| [100167 1x40 pin header PH-1x40SG (cut into seven headers)](https://akizukidenshi.com/catalog/g/g100167/) | 26pin | 1単位 | ¥35 | ¥35 |
| [105002 100μF16V 16MH5100MEFC6.3X5](https://akizukidenshi.com/catalog/g/g105002/) | 1個 | 1単位 | ¥20 | ¥20 |
| [113388 10μF25V B 2012 GRM21BB31E106KA73](https://akizukidenshi.com/catalog/g/g113388/) | 5個 | 1単位 | ¥100 | ¥100 |
| [111798 100kΩ ±0.1% 2012 RG2012N-104-B-T5](https://akizukidenshi.com/catalog/g/g111798/) | 34個 | 7単位 | ¥100 | ¥700 |
| [111797 10kΩ ±0.1% 2012 RG2012-N-103-B-T5](https://akizukidenshi.com/catalog/g/g111797/) | 27個 | 6単位 | ¥100 | ¥600 |
| [114788 2.2μF25V X7R 2012 GRM21BR71E225KE11](https://akizukidenshi.com/catalog/g/g114788/) | 2個 | 1単位 | ¥100 | ¥100 |
| [107549 1μF10V X7R 2012 CL21B105KPFNNNE](https://akizukidenshi.com/catalog/g/g107549/) | 1個 | 1単位 | ¥150 | ¥150 |
| [130140 4.7μF50V bipolar 50NXA4R7MEFC5X11](https://akizukidenshi.com/catalog/g/g130140/) | 5個 | 5単位 | ¥20 | ¥100 |
| [111796 1kΩ ±0.1% 2012 RG2012N-102-B-T5](https://akizukidenshi.com/catalog/g/g111796/) | 3個 | 1単位 | ¥100 | ¥100 |
| [111795 100Ω ±0.1% 2012 RG2012N-101-B-T5](https://akizukidenshi.com/catalog/g/g111795/) | 2個 | 1単位 | ¥100 | ¥100 |
| [100034 DIP40 socket 600mil 2227MC-40-06](https://akizukidenshi.com/catalog/g/g100034/) | 1個 | 1単位 | ¥90 | ¥90 |
| [116478 Dual A10k volume JH16T2A103L20KC](https://akizukidenshi.com/catalog/g/g116478/) | 1個 | 1単位 | ¥130 | ¥130 |
| [100080 2x20 male header PH-2x20SG/RH; conditional module part](https://akizukidenshi.com/catalog/g/g100080/)（module未実装時のみ） | 2個 | 2単位 | ¥50 | ¥100 |

秋月分の小計は**2,345円**。module側オスheaderが未実装なら2個・100円を追加し**2,445円**。
他店品、FPGA module、YM本体、基板、外部電源、配線類、送料を含まない。
headerの26pinは7個へ切り分ける。5台分は切断作業用の余裕として1本／台を計上した。
ピンソケットは縦型オスheaderでの実装前提で、L字header実装済みmoduleとはそのまま接続しない。

## 他店で同一型番を手配するIC類

以下は**DigiKey／Mouser等で探す型番の指定**。全品の現在在庫・見積金額は未確定。
末尾まで型番とpackageを確認する。秋月で同一型番の裸ICを今回の調査では確認できなかった。

| ref | 型番 | 必要数／1台 | package |
| --- | --- | ---: | --- |
| U1 | SN74LVC1G17DBVR | 1 | SOT-23-5 |
| U2 | TPS3808G01DBVR | 1 | SOT-23-6 |
| U3 | TPS3808G01DBVR | 1 | SOT-23-6 |
| U4 | MAX6369KA+T | 1 | SOT-23-8 |
| U5 | SN74LVC74APWR | 1 | TSSOP-14_4.4x5mm_P0.65mm |
| U6 | SN74LVC08APWR | 1 | TSSOP-14_4.4x5mm_P0.65mm |
| U7 | SN74LVC1G08DBVR | 1 | SOT-23-5 |
| U8 | SN74LVC8T245PWR | 1 | TSSOP-24_4.4x7.8mm_P0.65mm |
| U9 | SN74LVC8T245PWR | 1 | TSSOP-24_4.4x7.8mm_P0.65mm |
| U10 | SN74LVC1G04DBVR | 1 | SOT-23-5 |
| U11 | SN74LVC1G08DBVR | 1 | SOT-23-5 |
| U13 | Si5351A-B-GT | 1 | MSOP-10_3x3mm_P0.5mm |
| U14 | SN74LVC1T45DBVR | 1 | SOT-23-6 |
| U15 | CDCLVC1102PWR | 1 | TSSOP-8_3x3mm_P0.65mm |
| U16 | SN74LVC125APWR | 1 | TSSOP-14_4.4x5mm_P0.65mm |
| U17 | PCM5102APWR | 1 | TSSOP-20_4.4x6.5mm_P0.65mm |
| U18 | MCP6022-I/SN | 1 | SOIC-8_3.9x4.9mm_P1.27mm |
| U19 | CD74HC4053M | 1 | SOIC-16_3.9x9.9mm_P1.27mm |

Q1〜Q5は**MMBT3904LT1G / SOT-23を5個**。秋月[105969](https://akizukidenshi.com/catalog/g/g105969/)は商品詳細で販売終了を確認したため、秋月注文表へ入れていない。
U15 CDCLVC1102PWRはclock測定条件の確認が残る候補で、下記の保留項目にも含める。

確認できた他店商品ページの例：
[SN74LVC8T245PWR / DigiKey](https://www.digikey.com/en/products/detail/texas-instruments/SN74LVC8T245PWR/857773)、
[Si5351A-B-GT / DigiKey](https://www.digikey.jp/ja/products/detail/skyworks-solutions-inc/SI5351A-B-GT/3679847)、
[MAX6369KA+T / DigiKey](https://www.digikey.jp/en/products/detail/analog-devices-inc-maxim-integrated/MAX6369KA-T/948135)。
通販SKUのTRはリール、CTはカットテープ。少数手配はCT／単品を選ぶ。

秋月の[Si5351Aモジュール](https://akizukidenshi.com/catalog/g/g110679/)は実装済み基板で、裸MSOP10の代わりにはならない。
[MCP6022-I/P](https://akizukidenshi.com/catalog/g/g116187/)もDIP8で、現行SOIC8のU18へ直接実装できない。
採用する場合は別の基板／footprint変更になるため、この注文表には含めない。

## 残りの抵抗・コンデンサー等

以下はDigiKey／Mouser等で、指定サイズ・精度・誘電体を満たすものを選ぶ。
現行SMD抵抗・MLCCは**0805=2012M**。1608M、0603Mと混同しない。

| 種類 | 必要数／1台 | 要求 |
| --- | ---: | --- |
| 22Ω | 1 | 2012、±1%以下 |
| 33Ω | 5 | 2012、±1%以下 |
| 470Ω | 1 | 2012、±1%以下 |
| 2.2kΩ | 4 | 2012、±1%以下 |
| 4.7kΩ | 1 | 2012、±1%以下 |
| 22kΩ | 1 | 2012、±1%以下 |
| 47kΩ／68kΩ／110kΩ／66.5kΩ | 各1 | **2012、±0.1%**。監視／VBUS分圧用、1%品へ置換しない |
| 0.1µF | 28 | 2012、X7R、10V以上。発注は50個程度に丸めてもよい |
| 100pF | 1 | 2012、C0G/NP0 |
| 2.2nF | 1 | 2012、C0G/NP0 |
| 47pF | 1 | 2012、C0G/NP0 |
| フェライトビーズ | 1 | BLM21PG601SN1、2012、600Ω@100MHz |
| D51改造用Schottky | 1 | STPS2L30AF候補。ULX3Sの既設padと向き確認後 |

秋月[0.1µF X7R 2012 / 117576](https://akizukidenshi.com/catalog/g/g117576/)も販売終了表示のため、現行サイズを維持して他店へ回す。
4.7µF bipolarを極性付き電解へ変更したり、pF／nFの音声filterを容量同値だけで別誘電体へ変えたりしない。
各refの全一覧はCSVに含めた。

## module・clock・保留項目

| 品目 | 必要数／1台 | 調達先・状態 |
| --- | ---: | --- |
| ULX3S 85F | 1 | [Crowd Supply](https://www.crowdsupply.com/radiona/ulx3s)。85Fの掲載$275、海外送料掲載$18、2026-12-01出荷予定表示。実PCB v3.0.8との一致と現行納期を販売側へ確認 |
| YM2203C本体 | 1 | 手持ち予備品／別途調達。秋月の現行新品取扱は確認できず。socketは別計上 |
| 12MHz XO | 1 | ASV-12.000MHZ-EJ-T候補。精度・負荷・buffer込みでP3エッジ条件を確認後に確定 |
| 25MHz水晶 | 1 | CL10pF、3225-4pin。候補ABM8-25.000MHZ-10-1-U-TのESR／drive等が未確定 |
| PTC | 1 | 1812、Ihold 1.1A候補。実型番と抵抗の確定前は購入保留 |
| 電源 | 1 | 5V系1.5A以上。PTC後4.95〜5.05V・ripple・監視閾値の成立を確認して選定 |
| NC停止switch／loop | 1 | JESTOP向け。接点開放で停止。機構の選定はPCB／筐体と合わせる |
| 配線・USB・spacer・line出力 | 一式 | 手持ち優先。コネクター形状、moduleの高さ、外付けjackの構成を確認 |
| キャリアPCB | 1 | 未レイアウト・未発注 |

clock bufferの0.8ns最大値は20–80%であり、P3の10–90% rise/fall 1ns以内の確認を代替しない。
PTCは定格電流だけで選ばず、負荷時の電圧降下と5V監視閾値の余裕を確認する。
D8は既存Schottkyを現物確認、D9/D52は開放とし、購入するdiodeを追加する位置ではない。

この表の更新は回路図を変更するものではなく、既存HOST／RTLにも変更を加えない。
