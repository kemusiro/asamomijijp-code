# P2 review F：40接点・直接パラレル／SPI／I2C選択

2026-11-17 / revision3.3-interface-review-f / interface4.0-draft。
個人実験用の1スロット・電源OFF交換。**コネクタとGPIO候補の検討結果**であり、回路・PCB・firmwareへ未反映。
PGA2350ベース、アナログL/R＋ベース共通ADC、任意I2S、必要な5V変換を維持する。

40接点に8bitの直接パラレルbusを収める。既存SPI4本をD0～3と排他的に共用し、
追加8接点をD4～7とCTL0～3へ使う。以前の「追加制御4＋GND4」案とは配分を変え、GNDは既存12接点を維持。
PSGカード側のSPI→parallel latch/bridge MCUを省ける。電圧変換、decoupling、音声負荷/mixは必要な範囲で残す。

## 40接点表

2×20/2.54mm、接点列48.26mm（Eより10.16mm長い）。候補はSSW-120-02-G-D / TSW-120-07-G-D。
ベース嵌合面A列奇数/B列偶数。32は継続して抜きピン/塞ぎ穴KEYとするため、20段中16段目がKEY。
汎用40pin品は標準でこのKEY加工が無いので、加工・上下左右・裏面鏡像を回路/PCB化時に確認する。
旧32pinカードの部分挿しは運用禁止。接点増だけで旧カードのprofileを自動識別できるわけではない。

| pin | 基本信号 | parallel時の別名 | ベースGPIO候補 |
| --- | --- | --- | --- |
| 1 | V5_MODULE |  | — |
| 2 | GND |  | — |
| 3 | V5_MODULE |  | — |
| 4 | GND |  | — |
| 5 | MOD_SPI_SCK | BUS_D2 | 2 |
| 6 | GND |  | — |
| 7 | MOD_SPI_MOSI | BUS_D3 | 3 |
| 8 | MOD_SPI_MISO | BUS_D0 | 0 |
| 9 | MOD_SPI_CS_N | BUS_D1 | 1 |
| 10 | GND |  | — |
| 11 | MOD_ENABLE |  | 34 |
| 12 | MOD_ALERT_N |  | 4 |
| 13 | MOD_I2S_BCK |  | 27 |
| 14 | GND |  | — |
| 15 | MOD_I2S_LRCK |  | 28 |
| 16 | GND |  | — |
| 17 | MOD_I2S_DATA |  | 16 |
| 18 | GND |  | — |
| 19 | SOUND_CLK0 |  | — |
| 20 | GND |  | — |
| 21 | SOUND_CLK1 |  | — |
| 22 | GND |  | — |
| 23 | SOUND_CLK2 |  | — |
| 24 | GND |  | — |
| 25 | V3V3_MODULE_AUX |  | — |
| 26 | GND |  | — |
| 27 | AUDIO_L |  | — |
| 28 | AUDIO_R |  | — |
| 29 | MOD_I2C_SDA |  | 42 |
| 30 | MOD_I2C_SCL |  | 43 |
| 31 | GND |  | — |
| 32 | KEY |  | — |
| 33 | BUS_D4 |  | 30 |
| 34 | BUS_D5 |  | 31 |
| 35 | BUS_D6 |  | 32 |
| 36 | BUS_D7 |  | 33 |
| 37 | MOD_CTL0 |  | 6 |
| 38 | MOD_CTL1 |  | 7 |
| 39 | MOD_CTL2 |  | 17 |
| 40 | MOD_CTL3 |  | 18 |

全仕様は[connector.json](connector.json)、[CSV](connector.csv)、[GPIO候補](gpio-proposal.json)。
最初の32接点はSPIモードでEの信号/電圧/方向を保持する。parallelモードでは5/7/8/9がデータ線へ変わり、
特に旧MISOがベース出力にもなるので、SPIカードをparallelとして駆動しない。
共通connectorに出すdigitalはすべて3.3V。3.3V補助100mA枠/5V500mA枠はEの設計候補を継承し、容量確定は未実施。

## モードとGPIO

| モード | GP0/1/2/3 | 33～40 | 用途 |
| --- | --- | --- | --- |
| SPI | MISO/CS0/SCK/MOSI | 任意GPIO、CTL1=CS1/CTL0=CS2候補 | YM FM変換Core、DAC、電子ボリューム |
| parallel8 | D0/D1/D2/D3 | D4～7＋CTL0～3 | AY/SN等をベースから直接制御 |
| I2C | 既定Hi-Z、必要なauxだけ別途profile | 必要なauxだけ使用 | 発声・ラジオ・I2C DAC/pot |

I2Cは従来どおり内部GP42/43、HOSTはGP20/21で分離する。Si5351A/panel/共通ADCに必要な内部I2Cは
parallel選択中も動かす。SPIとparallelの同時使用はしない。MIDI/I2Cの所有権と物理busモードは別の概念。

D4～7=GP30/31/32/33、CTL0～3=GP6/7/17/18を新規候補とする。EのADC DOUT=GP5も候補のまま保持。
既承認Cの35 GPIOは動かさず、追加候補9本で最大44/47本、残りGP35/36/37の3本。
UNO・USB・HOST・Si5351A・ADC/I2S・STOP/LED用の既存信号を奪わない。
単純なI2C/SPIカードで使わない線はHi-Z。最大44本は全profileで同時駆動する本数ではない。

データ8本は非連続かつGPIO32境界をまたぐため、単一PIO OUT8での直接出力は本候補では成立しない。
初期driver候補はSIOで、write strobe非活性中に低/高bankを更新する。制御4本はすべてGPIO0～31内。
波形のdeadline/割込み制御・音声/USB負荷下の実測はfirmware段階で行う。

## 音源カードで省けるもの

| カード | 主モード | 省ける回路 | 残す回路・制約 |
| --- | --- | --- | --- |
| AY-3-8910/12 | parallel8 | SPI変換ラッチ/bridge MCU、カードADC | 5V buffer、clock/reset、声部負荷/mix。BC2露出型のprofile |
| SN76489AN | parallel8 | SPI変換ラッチ/bridge MCU、カードADC | 5V buffer、READY、analog整合。D0がMSBというIC側命名に注意 |
| ATP3012 | I2C | 追加MCU/ADC | PWM LPF・固有初期化 |
| Si4732 | I2C | 追加MCU/ADC | RF/アンテナ・reset適合 |
| SN76477 preset | SPI＋auxまたはI2C | 一部のCS選択/IO拡張回路 | R/C、VCO DAC、校正。全R/C可変化を必須にしない |
| YM2203 opn1 | 従来SPI | 今回はFM変換Coreを省かない | FM decode/SRC、必要な5V変換、SSG抵抗mix |

詳細は[音源別profile](profiles.json)、[bus動作・レベル変換](BUS-AND-LEVELS.md)、
[部品削減比較](PARTS-DELTA.md)、[停止/互換仕様](SAFETY-AND-COMPATIBILITY.md)。
write-only PSGで物理readbackを仮定しない。generic A0/CS/WR/RDは将来の配分例で、read driver実装済みという意味ではない。
A1追加や複数parallel IC同時接続まで無条件に直結できる設計ではなく、profile再配分/局所decodeが必要になる。

## 音声と互換性

Eの音声方式を保持する。アナログmonoはLを共通ADCへ、ベースで左右複製。ステレオはL/R。
48kHz/24bit-in-32slot I2Sはbase clock master固定の任意経路。
YM2203はFMのみI2S、SSGのみアナログLのhybridで、二重合成を避けて音量/遅延を校正する。
STOPはbus待ちの前に最終gateを閉じ、read-only再接続で再演奏しない。
独立watchdog、電源絶縁、自動ID EEPROM、I2C muxは追加必須にしない。

既存HOST player/WYM1互換の対象は従来のopn1・4MHz。初期opn1はSPI/Core bridgeを維持する。
直接PSGがYMのWYM1を再生できるわけではなく、PSG別driver/公開形式/MIDI mappingは未実装。
USB-MIDI6声、I2C排他、lease、USB切断I2C継続の既存契約を変更しない。

## 検査と残作業

```sh
python3 verify.py
python3 -m unittest -v test_contract.py
```

pin/GPIO・共用・音源別bit順・候補波形・禁止設定と既存C wire定数を検査する。
波形検査はPC上の仕様モデルであり、RP2350上でパルスを生成/測定した結果ではない。
結果は[verification.json](verification.json)、一次資料は[sources.json](sources.json)。MITを継承する。

GPIO候補の実装には承認が必要。[C採用GPIO](../digital-module-review-c/pins.json)は変更しない。
E一式、D回路/PCB/BOM、Rev C firmware/HOST/実機受入は保存する。
次工程はGPIO承認、40pin嵌合/UNO干渉と電源再計算、回路/ERC、PCB/DRC、driver実装、実機timing/音声確認。
