# P2交換式音源基板：候補の機能差

2026-11-18。現主案は[review H](clean-sheet-schematic-review-h/README.md)のアナログL/R＋ベース共通ADC、I2S任意。YM2203×1は[review Iの配線済みPCB](clean-sheet-pcb-review-i/README.md)を作成しERC/DRC0。firmware/実機受入は未実施。
クロックは再生プロファイルの出発点であり、各ICの許容周波数上下限ではない。

| 音源基板 | FM / SSG | 追加音源 | clock候補 | 音源基板に必要な検討 |
| --- | --- | --- | --- | --- |
| YM2203×1 | FM3 / SSG3 | — | 4MHz（Rev C互換） | FM decode/SRC、SSG ADC/mix、5V bus変換 |
| YM2203×2 | FM6 / SSG6 | — | 各4MHzを出発点 | 2個のCS、2経路のFMとSSG合成、個別clock対応要否 |
| YM2608 | FM6 / SSG3 | 内蔵リズム6＋外部ADPCM1 | 7.9872 / 8MHz | A1追加、stereo DAC＋SSG合成、ADPCM用メモリ制御 |
| YM2610 | **FM4** / SSG3 | ADPCM-A6＋ADPCM-B1 | 8MHz | A1、stereo DAC＋SSG合成、A/Bサンプルメモリ |
| YM2610B | **FM6** / SSG3 | ADPCM-A6＋ADPCM-B1 | 8MHz | YM2610と別device識別・対応曲判定 |
| YMF288 | FM6 / SSG3 | 内蔵リズム6、**外部ADPCMなし** | 7.9872MHz | 3.3Vモード、FM/SSG/リズムを含むデジタル出力、対応DAC |
| YM2151＋SegaPCM系 | FM8 / SSGなし | 外部サンプルPCM | FM 4MHz（対象3作品のうち2作品） | OPMドライバー、stereo DAC、PCM系・メモリ・音量合成 |
| YM2203＋初期SegaPCM系 | FM3 / SSG3 | 初期PCM系 | FM 4MHz | OPN＋初期PCMのレジスタ配置・同時実行 |

YM2203/2608/2610系の機能差はMAMEに含まれる[ymfm開発者の比較表](https://github.com/mamedev/mame/blob/master/3rdparty/ymfm/GeneralInfo.md#chip-specifics)
でも確認できる。表のSSG数は波形発生ch数で、アナログ端子数ではない。
YM2610のFM4とYM2610BのFM6を同じものとして扱わない。

YM2608の原資料は[Yamaha YM2608 Data Sheet](https://www.quarter-dev.info/archives/yamaha/YM2608_Data_Sheet.pdf)。
資料上の7.9872MHz、FM追加3音、ADPCMとリズムの追加を確認した。
詳細なDAC・SSG出力・外部メモリの説明は
[Yamaha Application Manualの翻訳版](https://wiki.agiri.ninja/_media/datasheets:ym2608_en_t.pdf)も照合する。
翻訳の数値・表現だけで部品定格を確定せず、回路化時には原文と照合する。
YM2610は[Application Manualの転記・翻訳](https://www.ajworld.net/neogeodev/ym2610am_en.html)に
YM3016、SSGアナログ出力、A/B外部メモリ、8MHzの説明がある。
これらの音源は、単なるレジスタ列のほかにサンプル配置・容量・アクセス方法も設計対象になる。

YMF288は[Yamahaデータシート（保存版）](https://quarter-dev.info/archives/yamaha/YMF288.pdf)の
概要・端子説明・DAC I/Fを確認した。FM/SSG/リズムのレジスタ互換を持ち、ADPCM・I/O port・
SSGアナログDACを削除している。5V/3.3Vモードがあり、3.3Vモードなら当該モジュールの変換削減を検討できる。
SSGもデジタル音声に含まれるため、旧YM2203のアナログSSG回路へそのまま差し替えることはできない。
通常は専用外付けDACを使う。本案では対応するMCU decoderで代替するため、一般のI2S DACへ生信号を直結する意味ではない。

## DACと音量合成の方針

現在の主案は[review H](clean-sheet-schematic-review-h/README.md)。
PCM1863をベースへ1個移し、アナログL/Rを標準返送経路にする。I2Sは同期slaveの任意経路。
YM2203ではCore2350B0のFM decode/SRCを残し、FMのみI2S、抵抗mixしたSSGをアナログLで返すhybrid回路候補。Hのsource impedance目標は4.7kΩ以下。
表中のADC/mixは音源内に必須という意味ではなく、この共通ADC/ベースmixへ移せる。
複数音源のアナログ出力はカード内でL/Rにまとめる。同時ADCは2chであり、全声個別DSPは保証しない。
異なるserial音源のdecoderは各カードで実装が必要。対応できない非同期I2Sを自動変換する仕様ではない。

共通DACのhardware muteと最終LINE muteは全音。FM枝だけ消す操作はhybridのベースmix前digital gainで扱う。
旧Rev Cの「DAC muteでSSGだけ残る」物理経路のままではなく、公開操作の意味をadapterで保持する。
ADC/SRC遅延・音量の校正は実装後。Dの完成音I2S方式と混同せず、profileで指定する。

## 実装難度と優先度

YM2203×1で分離による電気・音声・互換性を先に確認する。
YM2203×2は通信対象の拡張、YMF288は電源/音声形式の違い、YM2608/2610は
追加portとメモリ系の検証になる。Sega系はさらにPCM実装方式の選定が必要。
候補の列挙は、すべてを既存HOSTで直ちに再生できるという意味ではない。

## 独立した実験用音源基板候補

2026-11-17追加：[SN76477の音色プリセット付き単音シンセ](P2-SN76477-CANDIDATE.md)。
リファレンス回路のR/C設定をデジタル保存・呼出しし、外部VCO制御電圧で音程を指定する案。
既存YM系の曲再生とは別の候補で、現review Eの候補profileに含める。IC固有回路・MIDI mappingは未実装。
共通アナログ入力案なら音源側ADCを省略できるが、その経路は現Dに未実装。
校正、R/C切替、停止回路、単音演奏の実測を先に行い、全パラメーターの可変化は初期要件にしない。

## 簡素なアナログカード候補

[profiles.json](analog-module-interface-review-e/profiles.json)でAY/YM系PSG、SN76489系、
ATP3012音声合成、Si4732 DSPラジオ、SN76477 presetを整理した。
native I2C/SPI音源は追加MCU/ADCなし、パラレル音源は局所bus bridge、PWM出力はLPFを基本とする。
共通ADCでL/Rを受け、全カードに汎用Core2350B0・EEPROM・電源絶縁を必須化しない。
opn1以外の候補は既存YM22S002/WYM1の再生対象ではなく、新command/driverの実装が必要。

## 40接点・直接parallelによる簡素化（review F）

[F profile](parallel-module-interface-review-f/profiles.json)でAY-3-8910/12とSN76489ANの直接8bit制御を具体化。
SPI変換latch/bridge MCUを省略でき、必要な5V bufferとanalog負荷/mixだけを残す。
AYのBC2/BDIR手順、SNのD0=MSB配線/READYは[bus仕様](parallel-module-interface-review-f/BUS-AND-LEVELS.md)で区別する。
opn1は既存SPI/Coreを維持。PSG別driver・ファイル/API・MIDI mappingは未実装。

## 旧基板互換を撤廃したreview G

[新規40接点/GPIO](clean-sheet-interface-review-g/README.md)へbus/clock/analogを再配列。
AY/SNの電気的profile/bit順/timing条件はFから引継ぐが、Fのconnector番号とGPIOは流用しない。
native PSG cardはlevel buffer＋IC固有passiveを基本とし、必要のないMCU/ADCは追加しない。
YM opn1のFM変換Coreは残し、sourceローカルGPIOは新カードで別途割当てる。
