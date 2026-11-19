# LC-B具体化：接続済み回路図 review C

2026-11-19。ユーザー承認のLC-B推奨構成と提示GPIOを採用し、**ベース・音源・3.3V I2C音色編集パネルの接続済みKiCad回路図**を別版として作成した。旧L/K/シールドB、LC-A/LC-Bの検討結果、active-plan、既存HOST/C firmware・過去受入は保存する。旧版が更新済みに見えるような書換えはしない。

| 基板 | 回路図入口 | 部品参照 | シート（表紙込み） | ネット | native ERC |
| --- | --- | ---: | ---: | ---: | ---: |
| ベース | [p2-base-lc-c.kicad_sch](base/p2-base-lc-c.kicad_sch) | 143 | 15 | 114 | 0 |
| 音源 | [p2-ym2203-lc-c.kicad_sch](module/p2-ym2203-lc-c.kicad_sch) | 73 | 10 | 73 | 0 |
| パネル | [p2-panel-lc-c.kicad_sch](panel/p2-panel-lc-c.kicad_sch) | 51 | 9 | 38 | 0 |

KiCad10.0.5で全警告を含めてERC違反0、各ピンとexport netlistを一致照合。部品表の267実装参照を79購入行へ対応付けた。**新PCB・配線・DRC・Gerber・新firmware・実機受入ではない。**

- [電源・停止・機構と実装条件](POWER-STOP.md)
- [外部互換と受入条件](COMPATIBILITY.md)
- [費用比較・3万円目標](COST.md)／[購入用CSV](purchase-plan.csv)／[計算正本](purchase-plan.json)
- [承認・具体化範囲](adoption.json)／[独立検証](verification.json)／[KiCad検証](native-verification.json)
- [旧設計保存ハッシュ](preservation.json)／[一次資料の識別](sources.json)

## 採用構成とGPIO

ベースはPicossci2 RP2350A、音源はPicossci2B RP2350B＋実YM2203C、パネルはPico RP2040＋CD74HC4051E。パネルとの接続はGrove I2C 3.3V・150mm。YMはRev Cから1個流用する。

ベースは27GPIO（予備GP24/29、GP25は基板LED）、パネルは21GPIO（予備5本）、音源はHの28GPIOを維持。ベースSTOPをGP23へ直接接続した。HOST GP20/21、G40データ0..7・制御8..11・ENABLE12・ALERT13、音声14..18を維持し、service I2C1は26/27。割当の根拠は保存したLC-B gpio-proposal.json。新回路のUBASE/UPICO/USOURCEを検証スクリプトが全件照合する。

パネルのLCD・4ノブ・encoder・OP1～4・NOTE・STOP・EEPROM64音色・JSON機能を維持する要件。LCDはパネル内SPI、EEPROMはパネル内I2C1、uplinkはパネルI2C0 slave0x30。音声・HOSTバスから分離する。

## 安価で入手しやすい部品への変更

USB-Cの特定コネクタ輸入を避け、**汎用USB-B THT（秋月100161、50円）**を選んだ。必要なUSB-A↔Bデータケーブルも購入表へ含める。PCがUSB-Cのみの場合は別途変換アダプター等が必要。USB2 Full SpeedのCDC/MIDI、外部5V給電、VBUS検出と切断処理はそのまま維持する。電源専用USBコネクタは採用しない。

ADC入力の特定高容量MLCCは、**無極性10µF/50V NXA（秋月130142、20円/個）**へ置換。容量の定格公差下限8µFは従来の有効4.7µF条件を上回る。温度・漏れ・ノイズ・歪みを含めた実機同等性の証明ではない。外径5mm・高さ11mmのため、音源の下ではなくベース露出部へ置く。大型化を許容して汎用品を使う方針を反映した。

汎用pull-up/LED/series抵抗は0805厚膜1%を標準とし、0.1%薄膜品をやめた。一般のX7R/C0Gコンデンサ、DIPスイッチ、DIP40ソケットを使用。1G125とBAT54Sは通常流通の同機能品へ変更し、Ioff・電圧・ピン順を確認した。単端子MCUソケット、精密シム、特殊キー部品、UNO専用ヘッダーは新案へ持ち込まない。基板モジュール自体は承認されたPicossciを使うため、供給元はSwitch Scienceに依存する。

## 総額と基板外形

基板各5枚・部品1セット、手実装、YM流用で**送料・予備費込み29,751円の概算**。購入表には品番ごとの確定見積が未了の価格枠が含まれる。新Gerberの送料込みカートではないので、3万円以内の発注保証とはしない。

目標はbase100×100mm4層、source100×80mm2層、panel100×76mm2層、0.3mm穴/0.6mmビア、鉛フリーHASL。サイズ縮小のための極小部品・特殊ビア・ENIGを要求しない。120×100mm4層baseへ広げる比較は約33,655円となるため、次の配置配線で面積と総額を一緒に判断する。

## 次工程へ残す内容

Picossci2枚の直接実装ランド、USB-B、Grove2箇所は合計5参照でfootprint未割当。端子ネットは接続済みだが、現物/図面からランド形状を確定してからPCBへ進む。空欄を他社の類似footprintで埋め、ERC0を機構検証と見せることはしない。既存encoderとノブ/LCDの寸法確認事項も継承する。

音源Picossci2BのR5/R6 LED負荷切離しとRESET追加線を省略しない。base2AのRESETはJ1.18端面を使う。フラッシュ実容量・温度・電流・新HAL/内部SPI・音声合成・USB/HOST回帰は未完。過去Rev Cの実機合格をこの新回路の合格へ読み替えない。

## 再生成・検証

リポジトリrootから以下を実行する。

```sh
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-schematic-review-c/generate.py --check
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-schematic-review-c/purchasing.py
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-schematic-review-c/verify.py
git diff --check
```

Python3.15.2、KiCad CLI10.0.5。generate.pyが回路JSON・KiCad原本・symbol library・BOM・netlist・ERCを生成する。生成物を直接編集しない。verify.pyはGPIO/G40・電源/停止経路・全数量/価格算術・旧404ファイルSHAを独立照合。新しい実装/PCB実測の検査ではない。commit/push/注文は実施していない。
