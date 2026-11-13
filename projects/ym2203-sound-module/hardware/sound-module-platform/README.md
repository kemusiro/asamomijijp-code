# 交換式実音源モジュール — 共通接続案 Rev A

2026-10-15。音源ICを載せた基板を電源OFFで交換する、設計レビュー用の接続案。
**GPIOの本数・機能・信号の収容を確認した段階。回路図、PCB、動作するファームウェアは未作成。**
非公式の試作であり、各メーカーとの提携・承認を示すものではない。
既存の `hardware/ym2203-i2c-prototype/` のESP32-S3＋YM3014B-F回路とは別案で、
旧コネクタへの電気的互換性はない。WebLabの既存API・WYM1形式は変更していない。

## 対象と境界

- 対象：YM2203C、YM2608、YM2610、SN76489AN、YMZ285、YMZ294。
- 交換単位：音源IC、発振器、レベル変換、アナログ調整、必要なメモリと接続回路を載せた基板。
- 操作側：別のPico 2でMicroPython。3.3 VのI2Cホスト。
- 共通ベース：無線なしPico 2一台、C/C++、I2C受信、演奏時刻管理、チップ制御、FM取り込み、I2S出力。
- 共通出力部：AE-DAC5102、混合後の音量・ミュート、イヤホン／スピーカー用アンプ。
  音源MCUはI2Cスレーブとデジタル音声変換を兼任する。
- 当面は音源別ファームウェア。実装されていない自動ドライバー切り替えは前提にしない。
- 音源部をエミュレーションせず、実ICの出力を使う。YM3014／YM3016は汎用DACへの変換で代替。

## GPIOを先に割り当てた結果

**外部に出ている26 GPIOを26本使用。重複なし。予備GPIOはない。**
リセット・アンプ制御・基板IDをすべて直結する案では不足するため、
低速制御にMCP23017-E/SPを一個追加する。高速バスと音声信号には使用しない。
広いGPIOを持つ別ボードへ変更する案より部品は増えるが、Pico 2一台を維持できる。

| Pico 2 GPIO | 信号 | 方法 |
| --- | --- | --- |
| GP0〜GP7 | D0〜D7。D0をバイトのLSBとする | 双方向SIO、8本連続 |
| GP8 / GP9 | A0 / A1 | SIO出力 |
| GP10 | I2S DATA | PIO出力 |
| GP11 / GP12 | I2S BCLK / LRCK | PIO出力。クロック2本を連続配置 |
| GP13 / GP14 / GP15 | CS_N / WR_N / RD_N | SIO出力 |
| GP16 / GP17 | FM SD / CLK | PIO入力 |
| GP18 / GP19 | FM SH1 / SH2 | PIO入力 |
| GP20 / GP21 | 外部ホスト SDA / SCL | I2C0、スレーブ |
| GP22 | ARM | 外付け10 kΩプルダウン。リセット時にバスと音声を停止 |
| GP26 / GP27 | 内部補助 SDA / SCL | I2C1、マスター |
| GP28 | STATUS | IRQ／READY／PLAY用の直接入力 |

GPIO番号とPicoの物理端子番号は別物。[gpio.csv](gpio.csv) に双方を記載。
GP23/24/25/29は基板内の電源制御・VBUS検出・LED・VSYS測定用なので使わない。
USBとSWDはそれぞれの専用端子を使用し、追加GPIOを消費しない。
PIO入力／出力はすべてGP0〜31の範囲内である。

I2C0のGP20/21とI2C1のGP26/27は、RP2350の端子機能表と照合した。
二つのI2Cは**電気的に別バス**。両方3.3 Vへプルアップし、ホストと補助バスを接続しない。
初期のホスト通信は400 kHz、補助バスは100 kHzから評価する。
MCP23017は補助バスの7ビットアドレス0x20。交換基板の補助デバイスは0x30〜0x37を予約し、
0x20を使用しない。実際のメモリローダーは未実装。

### 補助GPIOとリセット

[expander.csv](expander.csv) に16本の配分を記載。

| MCP23017 | 用途 |
| --- | --- |
| GPA0 | RESET_RELEASE。ARMとのANDで交換基板のRESET_Nを生成 |
| GPA1 / GPA2 | HP_ALLOW / SPK_ALLOW。ARMと組み合わせて各出力のミュートを制御 |
| GPA3 | DAC_ALLOW。AE-DAC5102のRST用制御回路へ |
| GPA4 / GPA5 | 交換基板の低速AUX0 / AUX1 |
| GPA6 / GPA7 | 予備出力 |
| GPB0〜GPB2 | ID0〜ID2。ベース側10 kΩプルアップ、交換基板側ストラップ |
| GPB3 | PRESENT_N。交換基板側でGNDへ接続 |
| GPB4〜GPB6 | 予備入力 |
| GPB7 | 予備出力 |

GPA7/GPB7は入力に使わず、現行MCP23017の端子制約を避ける。
拡張ICのPOR直後はGPIOが入力になるため、RESET_RELEASE、HP_ALLOW、SPK_ALLOW、
DAC_ALLOW、AUX0/1には外付けプルダウンを設ける。
ファームウェアでは出力ラッチを安全値へ書いてから方向を出力へ変更する。

MCP23017がPicoのウォッチドッグリセットを検知するとは仮定しない。
**GP22の外付けプルダウンとハードウェアゲート**で、Picoのリセット中は必ずARM=0とする。
RESET_N = ARM AND RESET_RELEASE、HP_RUN = ARM AND HP_ALLOW、
SPK_RUN = ARM AND SPK_ALLOWを基本とする。未初期化、基板未挿入、ID不一致ではARMを上げない。
アンプキットにEN端子がない場合は共通ベースへアナログミュート回路を追加する。
AE-DAC5102のRSTだけでは、SSGを含むアナログ混合音全体のミュートにならない。

## 共通コネクタ JMOD：2列50ピン

2.54 mm、25列×2、極性を合わせたシュラウド付きの嵌合ペアを候補とする。
全接点の正本は [connector.csv](connector.csv)。番号は嵌合する電気接点番号であり、
部品面・はんだ面の見え方を意味しない。MPN、背丈、フットプリント、固定穴はPCB設計時に確定する。
KEY_NCの50番は無配線とし、接点抜き／ブロックキーを使える嵌合ペアを選ぶ。
シュラウドの極性キーと基板固定具も併用し、番号だけで逆挿し防止済みとは扱わない。

| 接点 | 信号 |
| --- | --- |
| 1,3 / 2,4,6 | +5 V / GND |
| 5 | +3V3_AUX |
| 7〜14 | D0〜D7 |
| 15,17 / 16,18 | A0,A1 / GND |
| 19,20,21 / 22 | CS_N,WR_N,RD_N / GND |
| 23,24,25 / 26 | RESET_N,ARM,STATUS / GND |
| 27〜30 / 31 | FM_SD,FM_CLK,FM_SH1,FM_SH2 / GND |
| 32,33 / 34 | AUX_SDA,AUX_SCL / GND |
| 35〜38 | ID0,ID1,ID2,PRESENT_N |
| 39,40 | AUX0,AUX1 |
| 41,43,45 / 42,44 | AGND / ANALOG_L,ANALOG_R |
| 46,47 / 48,49 / 50 | 予備NC / GND / KEY_NC |

コネクタのデジタル信号は**すべて3.3 V**。5 Vネイティブ信号を直接接続しない。
交換基板側でAHCT系の上り変換、5 V入力耐性を持つLVC系の下り変換等を行う。
5 V出力の最小H保証がTTLレベルのICもあるため、5 V側VIHが0.7VCCの双方向変換器へ
無条件に置き換えない。電源OFF時の逆給電条件も使用部品のデータシートで確認する。

RESET_Nや制御信号はネイティブIC側でも必要なHレベルへ変換する。
特にYMZ294のリセット／クロック／TEST入力には3.5 V以上のH条件があり、
Picoの3.3 Vをそのまま接続する設計にはしない。

音源クロックは**各交換基板に置く**。そのため共通Picoのクロック出力GPIOは不要。
初期値はYM2203C=4 MHz、YM2608/YM2610=8 MHz、SN76489AN=3.579545 MHz、
YMZ285=4.096 MHz、YMZ294=4 MHz。曲の想定クロックが違う場合は基板側で合わせる。
YMZ294の4/6選択端子は4 MHz用にH固定。YMZ285のXIとCLKOを混同しない。

+5 Vは交換基板一枚500 mA、+3V3_AUXは100 mAを初期の設計予算とする。
これは接点や電源の実測定格ではない。電源回路と採用コネクタの定格を別途確認する。
補助3.3 Vは必要に応じてベース側専用レギュレーターで供給する。
3.5 V／±5 VのDAC用電源、パワーアンプの大電流は交換コネクタへ通さない。
AGNDとGNDは共通基準とし、クロック／スピーカー電流の帰路をアナログ経路と共用しない配線にする。
短い基板間接続を想定しており、長いリボンケーブルへの対応は未検証。

### 双方向データバス

読み書き切り替えは低速GPIOエキスパンダーを経由させない。
交換基板の書き込み用・読み取り用バッファをRD_NとARMから選択する。
安定状態での条件は、書き込み有効=ARM AND RD_N、読み取り有効=ARM AND NOT RD_N。
書き込み中はデータバッファをWR_Nの上昇で直ちに切らず、データ保持時間を確保する。

読み取りへの移行は、CS_N/WR_N=H → Picoデータ端子を入力 → RD_N=L →
バッファ切り替え待ち → CS_N=L → アクセス待ち → 読み取り。
終了時はCS_N=H → チップの出力解放待ち → RD_N=H → バッファ切り替え待ち →
Picoデータ端子を出力へ戻す。アドレス書き込み時はRD_N=H。
ゲート遅延、バッファOE遅延、ネイティブICのデータ保持時間の照合は回路設計で行う。
SN76489AN/YMZ285/YMZ294ではRD_NをHに保ち、未対応の読み取りサイクルを発生させない。

## 六種類の交換基板

| ID（ID2..0） | IC | バスの追加信号 | デジタル音声 | アナログ音声 |
| --- | --- | --- | --- | --- |
| 001 | YM2203C | A0,RD_N,RESET_N、IRQ→STATUS | OP-O/φS/SH→SD/CLK/SH1 | SSG A/B/Cを合成してL/R同音 |
| 010 | YM2608 | A0,A1,RD_N,RESET_N、IRQ→STATUS | OP-O/φS/SH1/SH2 | SSGをL/R同音 |
| 011 | YM2610 | A0,A1,RD_N,RESET_N、IRQ→STATUS | OP-O/φS/SH1/SH2 | SSGをL/R同音 |
| 100 | SN76489AN | /CE機能→CS_N、/WE→WR_N、READY→STATUS | 使用しない | AUDIO OUTをL/R同音 |
| 101 | YMZ285 | /CS,/WR,/RESET、/PLAY→STATUS | 使用しない | SOとPOを合成してL/R同音 |
| 110 | YMZ294 | /CS,/WR,A0,/IC | 使用しない | SOをL/R同音 |

全基板でD0〜D7/CS_N/WR_Nを収容する。表の信号名は機能対応であり、
各ネイティブパッケージへの全端子番号の接続表は未作成。
SN76489ANの資料は選択端子を図で/OE、本文で/CEと記載している。
16ピン版の選択端子は6番、書き込みは5番。音声読み取りのOE信号とは扱わない。
またTIのD0/BIT0は最上位側である。**共通D0（LSB）→TI D7、共通D7（MSB）→TI D0**と
交換基板側で配線を逆順にし、ファームウェアの一般的な0x9F等のバイト表現を維持する。

STATUSはYM系ではIRQ=L、SNではREADY=H、YMZ285ではPLAY=Lという別の意味になる。
極性は音源別ファームウェアで扱う。READYの初期Hを早まって転送完了と判断しないよう、
SNのCS/WE、約32クロックの転送周期とREADYの遷移を資料どおりに評価する。
YMZ294ではSTATUSを駆動しない。未使用のFM音声端子も交換基板側ではNC。
ベース側で未使用入力を弱くプルダウンし、偽のフレームを処理しない。

ID000/111は予約／無効。PRESENT_N=H、ID無効、ファームウェアの想定ID不一致はARM=0。
基板識別は受動ストラップなので、音源ICの読み取り機能や内蔵ROMに依存しない。

### YMZ285だけは演奏機能の前提が異なる

物理接続に必要なD0〜D7、CS、WR、RESET、PLAY、SO/POは収容できる。
ただし資料の通常CPUインターフェイスは、内蔵ROMの曲選択・開始停止・テンポ・PCM選択用。
ROM内のシーケンスで使うSSGレジスタ表を、外部CPUから自由に書けるとは解釈しない。
内部は512 KbitのワンタイムROMであり、手持ちICの書き込み済み内容／ブランク状態は不明。
**YMZ285の任意曲・任意PCM再生は、ROM内容またはプログラミング仕様が確認できるまで保証しない。**
VPPは通常動作の+5 V、TEST1/TEST2は通常動作のHとして設計する。
共通コネクタからOTP書き込み電圧を供給する機能は含めない。

## デジタル音声と共通アナログ部

- YM2203C：仮数／指数のYM3014形式を復号し、左右同じPCMへ変換。
- YM2608/YM2610：YM3016向けの左右データを取り込む。FMだけでなくチップが混合した
  リズム／ADPCMもこのデジタル経路に含まれる。
- SN76489AN/YMZ285/YMZ294：I2S側は無音PCMとし、交換基板のアナログ入力を使う。
- 交換基板のアナログは直流成分を除去し、バッファ・合成・減衰を通す。
  L/R各0.5 Vrms以下、駆動インピーダンス1 kΩ以下を初期設計目標とする。
  ICの出力保証値ではなく、全チャンネル同時発音時に測定して調整する値。
  モノラル出力からL/Rへは独立抵抗／バッファを用い、IC出力同士を直結しない。
- AE-DAC5102のLINE_L/LINE_Rへアナログ入力、HPAL/HPARから混合後の音声を出力する。
  ヘッドホン／スピーカーはここへ直接つながず、専用アンプを使用する。
- マスター音量・ミュートは**混合後**に置く。PCMだけのソフトウェア音量ではSSG/PSGを制御できない。
  音量回路の部品選定は別途。内部I2Cまたは拡張GPIOで制御し、Picoの追加GPIOを使わない。
- AE-DAC5102はDAC部3.5 V、アナログ部±5 Vが必要。USB 5 Vからの電源変換を別途設計する。

I2Sは初期48 kHz、左右32ビットスロット、BCLK=64fs=3.072 MHzの3線式を想定する。
PCM5102AはBCLKから内部PLLを使える。AE-DAC5102のMCLK端子をDGNDへ固定してSCKを浮かせず、
DIN/BICK/LRCKを接続する。基板回路図でMCLKがICのSCKへ接続されていることは確認した。
外部クロック出力との競合がないことと、基板の現物リビジョンを実装前に照合する。
この3線方式によりPicoのMCLK用GPIOを省く。4線MCLK必須のDACへは無条件に交換できない。

入力の音声更新周期は音源クロックに依存し、48 kHzとは限らない。
分数比の再サンプリングと必要なら小さなクロック誤差への追従を行い、単なる固定FIFOだけで接続しない。
FM経路の遅延がSSGとのバランスへ影響しないよう低遅延の小ブロックで評価する。
これは実装方針であり、再サンプリング品質や24時間連続動作は未検証。

PIOの初期予算はFM取り込み最大2 SM＋I2S出力1 SM、二つのPIOブロックへ分ける。
DMAはダブルバッファ／チェイン等を含め6チャネルを見込む。RP2350の資源内だが、
PIO命令メモリへの収容、同期エッジ、DMAサービス遅延、I2Cとの同時負荷はコード作成後に確認する。
大きな曲の全イベントをPico 2のRAMへ無条件に保持せず、予約キューと音声バッファを分ける。
既存WebLabの最大予約件数と同じ一括保持能力があるとは扱わない。

## ADPCM用メモリ

購入候補、用途ごとの数量、容量制限、変換回路は [memory.md](memory.md) を参照。
音源のメモリ端子は共通コネクタへ出さず、交換基板内に閉じ込める。
内部I2Cは将来のローダー用であり、I2C線をSRAMへ直結するという意味ではない。
ローダー／アクセス調停回路とローダー用プロトコルは未実装。

## 検証と次の設計工程

```sh
python3 hardware/sound-module-platform/generate.py
python3 hardware/sound-module-platform/verify.py
```

生成元はgenerate.py。design.json、CSVは直接編集せず再生成する。
verify.pyは露出GPIO、物理端子の重複、二つのI2Cの機能、I2S連続配置、6プロファイルの信号収容、
コネクタの電圧区分、MCP23017のポート7方向、CSV/JSON一致、資源予算を確認する。
結果は [verification.json](verification.json)。**回路のERCや実機動作を確認するものではない。**

次は、共通ベースと6交換基板のネイティブ端子接続表、電源とミュート、バス切り替え回路、
YM2608のDRAM→SRAM変換、YM2610のA/Bメモリ回路、ローダーを具体化する。
回路・部品定数とデジタル波形を確認してから、製造用のコネクタ仕様を固定する。

## 参照した資料

メーカー資料は参照のみとし、PDFや図のコピーを成果物へ同梱しない。

- [Raspberry Pi Pico 2 datasheet](https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf)：外部GPIO、基板内GPIO、物理端子。
- [RP2350 datasheet](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)：GPIO機能とPIO/DMA。
  GPIO機能表のローカル照合には[メーカー資料のWaveshareミラー](https://files.waveshare.com/wiki/common/Rp2350-datasheet.pdf)を使用。
- [Pico SDK](https://www.raspberrypi.com/documentation/pico-sdk/hardware.html)、[I2Cスレーブ例](https://github.com/raspberrypi/pico-examples/tree/master/i2c/slave_mem_i2c)。
- [YM2203](https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf)、[YM3014B](https://www.quarter-dev.info/archives/yamaha/YM3014B.pdf)。
- [YM2608メーカー資料の英訳](https://csclub.uwaterloo.ca/~pbarfuss/YM2608J_Translated.PDF)。
- [YM2610メーカー資料の転記・部分翻訳](https://ajworld.net/neogeodev/ym2610am_en.html)。
- [SN76489ANメーカー資料](https://map.grauw.nl/resources/sound/texas_instruments_sn76489an.pdf)：端子とデータのビット順を画像でも確認。
- [YMZ285メーカー資料](https://www.quarter-dev.info/archives/yamaha/YMZ285.pdf)：通常CPUコマンド、OTP、SO/PO、4.096 MHz。
- [YMZ294資料（秋月配布）](https://akizukidenshi.com/goodsaffix/ymz294.pdf)：18ピン、4/6 MHz、バスとリセットの入力条件を画像で確認。
- [MCP23017製品情報](https://www.microchip.com/en-us/product/MCP23017)、[秋月109486](https://akizukidenshi.com/catalog/g/g109486/)：I2C補助GPIO。
- [PCM5102Aメーカー資料](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)、[AE-DAC5102説明書](https://akizukidenshi.com/goodsaffix/ae-dac5102.pdf)：3線I2S、MCLK、混合、電源。
