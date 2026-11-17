# P2 revision 2.1 / carrier review A

PGA2350 + 実YM2203C + Si5351Aの**実端子・接続済み回路図**を具体化したレビュー案。
FPGAは使用しない。UNO R3形状・3.3V信号というユーザー指定に従う。
既存Rev CファームウェアのGPIO、I2C v2、HOSTプレーヤーは変更していない。
P2用ファームウェア移植・可変SRC・USB WYM1転送は未実装であり、実機互換を認定したものではない。

## 正本と生成物

|ファイル|用途|
|---|---|
|`pins.json` / `pins.csv`|GP0..47、PGA2350のA1..J10実端子、機能割当の正本|
|`header-geometry.json`|公式UNO Rev3e CADから確認した38接点の位置・向きの数値事実|
|`design.py`|158部品の全物理ピン・ネット・電源・定数・フットプリント|
|`generate.py` / `geometry.py`|接続済みKiCad回路図、シンボル、ソケット形状、BOMの再生成|
|`schematic/p2-carrier.kicad_pro` / `.kicad_sch`|13ページのKiCad 10回路図。グローバルラベルでページ間接続|
|`schematic/circuit.json` / `netlist.xml` / `erc.json`|回路正本の展開、KiCad出力の全接続、ERC結果|
|`schematic/bom.csv` / `assembly-extras.csv`|回路部品とソケット等の別部品。購入確定BOMではない|
|`schematic/p2-header-placement.kicad_pcb`|**未配線の配置確認用**。UNO、PGA2350、YMソケット、取付穴だけを配置|
|`schematic/footprint-pin-check.json`|全158部品について回路図ピン番号とフットプリントパッド番号を照合|
|`sources.json`|取得元とSHA-256。第三者PDF・CADアーカイブ自体は再配布しない|

`schematic/`は再現可能なテキストCADとして管理する。PDF/PNGはプロジェクトの
`outputs/p2/`へ出力しGit管理しない。回路正本を変更してから再生成する。
既存F1/P1と過去の検証記録は維持する。

## 実際のGPIO割当

|役割|RP2350B GPIO|周辺回路・補足|
|---|---|---|
|YM D0..7|GP0..7|8bit連続、双方向SN74LVC8T245|
|FM SD / CLK / SH|GP16 / 17 / 18|SN74LVC125、PIO0 SM0、GPIO_BASE=0|
|HOST SDA / SCL|GP20 / 21|I2C0 target 0x42、100kHz、既存配線維持|
|I2S DIN / BCK / LRCK|GP26 / 27 / 28|PIO1 SM0、GPIO_BASE=0、side-set=27から2本|
|YM A0 / CS / WR / RD|GP30 / 31 / 32 / 33|固定A→Bの制御用SN74LVC8T245|
|YM RESET_RELEASE|GP34|既定でリセットを保持する5V側2段NPNクランプ|
|DATA DIR / DATA OE / CTRL OE|GP35 / 36 / 37|OEはactive-low、10kで既定無効|
|DAC_ALLOW / LINE_ALLOW|GP38 / 39|10k pulldown、PCM5102Aとアナログミュート|
|基板・UNO SDA / SCL|GP42 / 43|I2C1 controller。Si5351A 0x60 / MCP23017 0x20|
|USB VBUS sense|GP46|分圧＋Ioff付きSchmitt。USB専用DP/DMは別端子|
|予約|GP47|PGA2350内蔵PSRAM CS、キャリアでは未接続|

PGA2350公式図の**部品面から見たA1を左上、A行を上辺、1列を左辺**とする。
25.4mm角、2.54mmグリッド、10×10の外周2列・64接点。
VBUS=A3、3V3=B4、RUN=A5、DP=A6、DM=A7、BOOTSEL=A8、
SWCLK=B6、SWDIO=B7。GNDはA1/A10/B2/B9/J1/J10。
ADC_VREF=B5と3V3_EN=A4は未接続。底面図に読み替えてミラー反転しない。

ネイティブGPIOは**47/47本を使用**。PIOは2インスタンス各1 SM、DMAはRX/TXの
ping-pong各2chを確保する方針。PIO2は未使用。PWM・UART・SPIはPIOを消費しない。
高位GPIO32..46は64bit／high-bank対応SIO APIを使う必要があり、旧コードの
`1u << gpio`や32bitマスクの流用は禁止。既存Pico 2バイナリはこの基板へ書き込めない。
SDKの`pimoroni_pga2350`を移植の基礎とし、`PICO_RP2350A=0`（48GPIO版）を必須にする。
同SDKヘッダーの既定UART0/1、I2C4/5、SPI16..19、LED25は本回路と競合するため、
自動初期化せず、P2専用割当で明示初期化する。UART stdioを音源バスへ出さない。
`schematic/p2_pinmap.h`は割当定数だけで、移植済みファームウェアではない。

### UNO R3機能との両立

|UNO端子|GPIO|機能|
|---|---|---|
|D0 / D1|13 / 12|UART0 RX / TX|
|D2 / D4 / D7 / D8|19 / 24 / 25 / 29|独立汎用GPIO|
|D3 / D5|14 / 15|PWM7 A / B|
|D6 / D9|22 / 23|PWM3 A / B|
|D10 / D11|9 / 11|SPI1 CSn / TX、またはPWM4B / PWM5B|
|D12 / D13|8 / 10|SPI1 RX / SCK|
|A0 / A1 / A2 / A3|40 / 41 / 44 / 45|ADC0 / 1 / 4 / 5。音源と専用ピンを共有しない|
|A4 / A5、重複SDA / SCL|42 / 43|I2C1 SDA / SCL。切離し時のみADC2 / 3|

SPI・UART・6PWM・ADCの機能はPico SDK 2.2.0のRP2350レジスタ定義と照合済み。
同じD10/D11のSPIとPWMは排他的なモード。PWMのA/Bは同スライスの周波数を共有する。
UNO信号・IOREF・ICSP VCCは3.3V、AREFとVINはNC。Arduinoスケッチ互換は含めない。
5V信号や5Vプルアップを持つシールドは直結できない。

A4/A5は基板内のSi5351A・パネルと共用するため、通常の演奏中はI2Cとして使用する。
`JP_SDA`と`JP_SCL`を開くと、基板内I2C枝と2.2kプルアップを物理的に分離できる。
ADC利用は**出力停止・パネル／クロック制御停止の保守モードだけ**。
ジャンパーを開いたままの演奏は許可しない。起動時にパネル不在なら無音で失敗させる。
シールドがSDAを保持するとソフトSTOPも使えなくなるため、直接RUNに接続する
ハードリセットをシールド領域外に設ける。パネルのタイムアウトは2ms目標、無限待ちを禁止。

IOREFは電圧通知でありシールド用電源ではない。`JP5V`は既定OPEN。
3V3電源はPGA2350の最大300mAレギュレータをMCU・DAC・Si5351A等と共用するため、
シールドへ供給できる電流は実測後に確定する。外部電源をヘッダーから逆給電しない。

## UNOソケットの配置

公式UNO-TH Rev3eの座標を数値照合し、KiCadの上面表示に合わせてY軸だけ変換した。
銅箔・シルク・回路・元の基板輪郭は複製していない。

- D7とD8の中心間は**4.064mm**。通常の2.54mm間隔へ揃えない。
- デジタル列とアナログ／電源列の中心間は**48.26mm**。
- ICSPはATmega328P側の位置を使用。USBブリッジ側ICSP1は使用しない。
- POWERはNC、IOREF、RESET、3V3、5V、GND、GND、VINの順。
- SPI 2×3はCIPO/VCC、SCK/COPI、RESET/GND。CIPOが上面左上となる向き。
- 4つのM3用3.2mm穴の位置も照合。各シールドの突起・ケーブル・高さは別途確認する。

配置確認用ではUNOを(10,10)mm基準、PGA2350 A1を(95,20)mm、YMピン1を(95,65)mmとし、
UNOの68.58×53.34mm領域からPGAのソケット領域まで横に**13.42mm**空けた。
PGAとYMはシールドの下へ置かず、パネルもシールド領域の外に確保する。
現時点の**160×120mm外形は余裕を持つ配置確認枠**であり、最終面積や配線成立の保証ではない。
PGAは4個の2×8ソケットを外周で組み合わせる候補。ソケット筐体の干渉、モジュール底面の
PSRAMとの高さ、実物A1方向を購入品で確認してからフットプリントを製造用に確定する。

## 周辺回路と既定停止

- 外部5VのみでキャリアとPGA2350を駆動。USB VBUSはESD保護と検出専用で、
  キャリア5V・PGAのVBUS端子には接続しない。USB切断中もI2C演奏を続ける経路を維持。
- USB-CのCC1/CC2はそれぞれ5.1kでGND。USBLC6-2SC6はコネクタ近傍。
  PGA2350にDP/DM各27.4Ωが既設のため直列抵抗を追加しない。差動配線とソケット経由の
  USB信号品質は未実測で、最終PCB配線時に検証する。
- YMデータ・制御・クロックは3.3V/5V変換を残す。FMの5V入力もLVC125を介して受信。
  初期状態ではYM RESET asserted、両OE disabled、DAC/LINE muted。
- Si5351Aは25MHz水晶、CLK0だけをYMへ接続。CLK1/2は未接続かつ初期設定で無効化。
  DIPはリセット時だけラッチする。4MHz以外のSRC検証は未了で、既存I2C v2 BEGINは
  4MHz時だけ許可する設計条件を維持する。
- MCP23017の実ピン：GPB0..7=1..8、VDD9、VSS10、SCL12、SDA13、A0..2=15..17、
  RESET18、INTB19/INTA20、GPA0..7=21..28。NC11/14、INT未使用。
  GPA0..3=DIP、GPA4=STOP、GPA5=TEST、GPA7=RX、GPB0..5=6声LED。
  **GPA7/GPB7は入力に使用しない**。LEDは1k経由の低電流sink、出力前にOLATをHIGH。
- RUNボタンは直接GNDへ。MCP RESETもRUNへ接続するが、内部watchdogは外部RUNを
  駆動しないため、起動時にMCPを明示初期化する。BOOTSELを押してRESETでUSBブートへ。
- STOPはソフト処理の全owner共通停止。TESTはownerなし・新たな押下だけで発音。
  USB WYM1・USB-MIDI・I2C間の排他、切断時停止、USB切断中I2C継続は移植時の回帰項目。
- Rev CのSSG負荷1k、各入力100k、混合帰還22kとFMフィルタを維持。
  モノラル混合を左右へ複製する。独立ステレオ音源やヘッドホンドライバではない。

電源監視・独立watchdog・停止許可ラッチはユーザー指定に従い省略している。
通常STOP・リース・内部watchdogは必要だが、MCU停止中の独立した安全停止は保証しない。
回路図ERCは部品定格・電源立上り・アナログ音質・USB適合・手ハンダ品質を保証しない。

## HOST互換の固定条件

HOSTはこれまで通りGP0=SDA、GP1=SCL、GND共通。キャリア側JHOSTはGND/SDA/SCL/GND。
100kHz、アドレス0x42、`YM22S002`、64byte STATUS、32event/PUSH、1024event FIFO、
CRC32・sequence・WYM1形式・1000ms lease・STOP全消去・再接続時自動再開なしを維持する。
共有パネルI2Cは別のI2C1で、HOSTバスを拡張シールドと共用しない。
今回HOST/Rev Cファームウェアはハッシュ比較で未変更を確認する。P2実機受入は未実施。

## 再生成と検証

Python標準ライブラリとKiCad CLI 10.0.5を使用する。以下はこのディレクトリで実行する。

```sh
python3 generate.py --check
# KiCad同梱PythonまたはpcbnewがimportできるPythonで実行する。
python3 placement.py --footprints /path/to/kicad/footprints
python3 check.py
python3 export_review.py --pdf ../../../outputs/p2/p2-revision-2.1-review-a.pdf
cc -std=c11 -Wall -Wextra -Werror -fsyntax-only -Ischematic -I/path/to/pico-sdk/src/rp2350/hardware_regs/include check_mux.c
# SDK定義の取得版まで照合する場合
python3 check.py --sdk-registers /path/to/pico-sdk/src/rp2350/hardware_regs/include/hardware/regs/io_bank0.h
```

`--output`で生成先を分離できる。`check.py`はピン重複、GP47使用、SPI/ADC/PWM/PIO不整合、
USB逆給電、OE既定値、MCP出力専用端子の誤用、UNOの向き・間隔を含む12テストを実行する。
KiCad netlistの全端子集合も正本と比較する。配置確認用PCBには未配線が残るため、
製造用DRC合格や全158部品の配置完了を主張しない。

## 次の配線候補

[PCBレビューB](pcb-review-b/README.md)で電源容量・ソケット構成を見直し、配線済み基板とDRC検査へ進めた。
このディレクトリのレビューA回路図・未配線配置枠・過去検査結果は、その時点の資料として変更しない。
