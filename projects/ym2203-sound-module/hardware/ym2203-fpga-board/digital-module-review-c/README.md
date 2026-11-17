# P2 digital module 回路図レビューC

2026-11-16。ユーザーが提示済みGPIO候補を採用し、**PGA2350(base)＋Core2350B0(source)＋PCM1863＋実YM2203C**を
接続済みKiCad回路図へ具体化した。PGA2350はbaseの1枚だけ。Coreとのpin配置は別で扱う。

**KiCad10.0.5のERCはbase/sourceとも違反0。PCB/firmware移植/新実機受入/製造リリースは未完。**
GPIO正本はこのreviewの[pins.json](pins.json)。旧Rev CとP2一体型・分離reviewA、部品選定reviewBは変更しない。
新しいnative GPIOの追加はなく、base35本・source30本を承認どおりに使う。
[base header](p2_base_pinmap.h) / [source header](p2_module_pinmap.h)は今後のport用で、動くfirmwareへ組み込んだものではない。

| 成果物 | 入口 |
| --- | --- |
| base / 147 ref、12ページ、128 nets、ERC0 | [p2-base-c.kicad_sch](base/p2-base-c.kicad_sch) / [BOM](base/bom.csv) |
| 音源 / 145 ref、14ページ、100 nets、ERC0 | [p2-ym2203-c.kicad_sch](module/p2-ym2203-c.kicad_sch) / [BOM](module/bom.csv) |
| 共通32接点 | [connector.csv](connector.csv) / [connector.json](connector.json) |
| GPIO / Core固有pin | [pins.json](pins.json) / [module-header.json](module-header.json) |
| 電源順序・ADC入力保護 | [POWER-SEQUENCE.md](POWER-SEQUENCE.md) |
| 検査結果 | [verification.json](verification.json) / [native-verification.json](native-verification.json) |

確認PDFはprojectのGit管理外 `outputs/p2/p2-digital-module-review-c.pdf`。
先頭3ページが音声分担・電源/入力保護・接点表、続いてnative26ページの計29ページ。
回路図はglobal labelで接続し、独自MIT symbolには実pin番号/電気typeを明示する。
standalone ERCのためJMOD/Core socketのpin typeは相手基板/moduleの電源・出力を表す。
物理的なconnectorが能動回路を持つ意味ではなく、接点の方向はmanifestで別照合する。
ERC rule exclusionや未接続を隠す抑制設定は使用しない。

## 回路の分担

baseはHOST I2C0 GP20/21、USB CDC/MIDI/VBUS sense、UNO R3形状・3.3V IOREF、panel/RX・6voice LED、Si5351A、
SPI0 GP0〜3、ALERT GP4、完成音I2S DATA GP16、共通clock/DAC送出GP26/27/28、mute38/39を持つ。
音源clockはSi5351AのCLK0から4MHz。CLK1/2はbase connectorまで接続するがdisable・初回source側NC。
音源側CoreはSPI1 GP8〜11、FM16〜18、ADC I2C20/21、ADC DATA24、mix DATA25、BCK26/LRCK27、ALERT28、
local YM bus0〜7/30〜37。GP39のonboard LEDと47のPSRAM候補は使わない。
Core P1〜P4の全64接点をメーカー回路図と照合し、PGAのsocket netlistを流用しない。

FMはCoreでdecode/SRC、SSG3はPCM1863の内蔵analog mix＋ADCを経由し、CoreでFMと数値合成する。
完成音を48kHz stereo/24bit有効・32bit slotのI2S DATAでbaseへ返す。BCK/LRCKはbaseが唯一のmaster。
PCM1863はBCK入力slave PLL、base PCM5102AはBCK由来PLL。FMclockとsample clockは別domainでSRCする。
4MHz時の125/108だけを基準とし、異なるclockへの固定流用はしない。
Core/ADC受信・SRC/合成・base受信の遅延合わせと性能の実装/測定はこれから。

baseではSSG/AUXのanalog合成枝を除き、完成音DAC後のbias付きL/R段、CD74HC4053、volumeを残した。
DACのground-centered出力を0〜5Vのswitchへ直結しない。feedback47k/input100kが今回の初期候補。
完成音DAC muteは全音を止め、FMのみのmuteはCore側mix前のFM gainで実現する要件。
FM100%/SSG比、6声の加算余裕、左右とクリックは再校正・実機確認する。

## 停止・電源・入力保護

[電源レビュー](POWER-SEQUENCE.md)で、RUNとのANDによる最終gate・独立ENABLE、Core RUNのopen-drain、
5V biasのYM reset clamp、ADC LDO EN、Ioff buffer、TMUX1511/BAT54S/4.7kを具体化した。
ADCのGPIO3を入力ARMに使い、native MCU GPIOは増やさない。
ADC OFFは680Ωと最低250msを案とし、80µF/流入50µAの条件で約0.072Vまで下がる算術を確認した。
ADC poweroffのデジタル遮断、clampのpin極性・電流上限、256通りの論理条件も検査した。
mid-railの挙動・漏れ・実際の放電と電圧過渡は測定前で、ERCが保証するものではない。
ADC I2Cは内部pullup禁止/open-drain限定というfirmware条件がある。

設計割当はbase PGA3V3 275mA/300mA、AUX150/500、source MCU205/800、ADC60/500。
source入力415mA、全体955mA、source500mA枠なら1040mA。PTC候補1.5Aは40°Cで1.25Aへderateする。
外部5.1V級2Aを候補にし、YM端子の4.75〜5.25Vと温度を実測する。
電流定格だけで小型module/SOT-23 LDOの放熱が合格したと扱わない。

合計292 electrical ref。旧分離Aの195 refに対して+97で、今回の合成/電源隔離/保護を含めた構成が少部品になったとはしない。
PGA/Coreのmodule本体、64個のPGA socket端子等は[assembly-extras.csv](assembly-extras.csv)も参照する。
PCB上のbody配置、4個のCore socketの角干渉、接点/基板高さとUNO shield干渉は次の配置検討に残る。
メーカー図面と照合したのは現段階ではpin番号・電源で、フットプリントの穴番号一致と実物嵌合は別の確認。

## 互換性と検証の範囲

既存HOST無変更互換の対象はYM2203×1・4MHz/WYM1。I2C0x42/100kHz、YM22S002/status64/PUSH32/FIFO1024/lease1000ms、
公開opcode・CRC/sequence・executed=実YM書込み完了を保持する。[内部SPI/停止契約](../digital-module-review-b/LINK-AND-SAFETY.md)を継続し、
ADC OFF待ちは本reviewの250msへ更新する。STOP ACKは即時消音/破棄後に返し、BEGIN準備待ちを既存HOST timeout内に納める実装が必要。
MIDI/I2Cの相互排他、MIDI USB切断panic・I2C所有時USB切断継続、readback/再接続で再発音しない要件も維持する。
UNO各信号・HOST/USB/panelの端子は旧回路と自動比較した。shieldは3.3V専用であり5V全シールド互換とはしない。
既存Rev C firmware/HOSTと受入結果は変更していない。新基板でのソフトウェア互換合格を意味しない。

検査は28件、電源Boolean256条件、292部品のfootprint pad番号、native全netlist、両ERC0。
analog値は区間/理想受動RCの算術で、silicon SPICEやADC入力保護の実測ではない。
各railの立上り/放電・ADC VIN・LDO温度・clock・音質、長時間再生と停止再開はfirmware移植後に確認する。
PCB配線・DRCや製造リリースは今回の成果へ含めない。

## 再生成

repo rootから次を実行する（KiCad10.0.5、Python3.15.2で確認）。

```sh
python3 -B projects/ym2203-sound-module/hardware/ym2203-fpga-board/digital-module-review-c/generate.py --check
python3 -B projects/ym2203-sound-module/hardware/ym2203-fpga-board/digital-module-review-c/verify.py --output projects/ym2203-sound-module/hardware/ym2203-fpga-board/digital-module-review-c/verification.json
python3 -B projects/ym2203-sound-module/hardware/ym2203-fpga-board/digital-module-review-c/export_review.py --pdf projects/ym2203-sound-module/outputs/p2/p2-digital-module-review-c.pdf
```

KiCad CLI、標準footprint library、librsvg、Poppler、Ghostscriptが必要。PDFはexport後に全ページを描画・確認する。
旧回路JSON/footprintはread-only入力。生成物はこのreviewのschema、KiCad/BOM/検証JSONを管理し、PDFとPNGはGit管理外。

既存C/HOSTの回帰は111件合格・楽曲依存4件skip、旧P2検査12件・分離A検査18件も合格。
[regression-results.json](regression-results.json)へ新回路の検査と分けて記録した。
