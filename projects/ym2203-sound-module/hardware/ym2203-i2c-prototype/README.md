# YM2203C＋YM3014B-F I2C音源モジュール — 回路案 Rev A

2026-10-14。ユーザー指定の実チップでFM 3ch＋SSG 3chを鳴らすための、未組み立ての試作回路案。
ヤマハの公式製品ではない。基板データ・製造用Gerber・実装済みファームウェアは含まない。
電源・端子・信号接続を具体化した設計レビュー用で、実機での発音・音質・安定動作は未確認。

## 前提と成果物

- 電源：安定化されたUSB 5 V / 2 A電源から、VBUS/GNDをJ1へ供給する。
  USB給電用ブレークアウトまたは給電ケーブルを使用。USB通信・USB PD交渉回路は含まない。
  PCの任意のUSBポートから大電流を取る設計ではない。
- 音源：YM2203C一台、4.000 MHz。外部DACはYM3014B-Fの**16ピンSOP版**。
- J3：3.5 mm・3極TRS、32 Ω程度のステレオイヤホン。左右に同じモノラル音を出す。
- J4：8 Ω・定格1 W以上のスピーカー一個。S1でスピーカーだけを無効にできる。
  イヤホン挿入による自動切り替えは含まない。
- 制御用M1：ESP32-S3-DevKitC-1-N8R8（8 MiB PSRAM）。音源のエミュレーションには使わず、
  I2C受付、予約データ保持、時刻管理、音源レジスタの書き込み、音量制御を担当する。

| ファイル | 内容 |
| --- | --- |
| `ym2203-i2c-prototype.kicad_pro` / `.kicad_sch` | KiCadプロジェクト／端子番号付き接続回路図 |
| `YM2203_HW.kicad_sym` / `sym-lib-table` | この設計用に新規作成したシンボル。外部ライブラリ不要 |
| `rendered/ym2203-i2c-prototype.svg` | KiCadから出力した拡大表示用の回路図 |
| `connections.csv` | ネット名、部品、端子番号、端子機能の全接続表 |
| `bom.csv` | 各部品の数量・値・補足。発注用MPN確定表ではない |
| `netlist.xml` | KiCadが読み取った接続情報 |
| `calculations.json` / `verification.json` / `erc.json` | 計算・接続照合・ERC結果 |
| `index.html` | 構成図と接続表の閲覧ページ |
| `host_driver_adapter.py` | 曖昧な実I2Cパケットを避けるホスト用MicroPythonアダプター。音源MCUのファームウェアではない |
| `generate.py` / `verify.py` | 図面生成／接続検証用のデスクトップPythonスクリプト |

回路図は同名ネットラベルで接続する方式。多ピンICも一つのボックスで描き、
端子番号を明示している。抵抗・コンデンサ等も接続表と対応する2端子ボックスで表現する。
配置配線済みのPCBではない。製造前にはフットプリント・コネクターの実端子番号の確定が必要。

## 信号の流れ

```text
I2Cホスト（Pico等、3.3 V）
  → M1 ESP32-S3 → 電圧変換・双方向バス → U1 YM2203C
                                      ├ FMデジタル → U5 YM3014B-F → U6Bバッファ ┐
                                      └ SSG A/B/C ────────────────────────────┤
                                                         U6C混合 → U7音量 → U6Dバッファ
                                                                            ├ U8 → イヤホンL/R
                                                                            └ U9 → スピーカー
```

## デジタル回路とI2C端子

J2は1=GND、2=SDA、3=SCL。プルアップR1/R2は各2.2 kΩで**モジュールの3.3 V**に接続。
ホストとのGNDを共通にする。J2に5 Vプルアップを接続しない。
100 pF負荷と仮定した立ち上がりは約186 ns。400 kHzでの実波形・配線容量は実測する。

U2/U4はSN74**AHCT**541を5 Vで使用し、3.3 V出力を5 Vへ変換する。
MCP41010の5 V時入力H条件は0.7 VDDなので、SPI信号もU4を通す。HC541への単純置換はしない。
U3はSN74**LVC**245Aを3.3 Vで使用し、5 VのYM2203データバスを読み取る。
DIRはHに固定してA→B。5 V耐性のないHC245等には置き換えない。

| MCU GPIO | 機能 |
| --- | --- |
| 8 / 9 | I2C SDA / SCL |
| 4,5,6,7,15,16,17,18 | データD0〜D7（順番に対応） |
| 10 / 11 / 12 / 13 | A0 / WR_N / CS_N / RD_N |
| 47 | RESET_N |
| 14 / 21 | 書き込み／読み取りバッファのOE_N |
| 39 / 40 / 41 | デジタル音量用SPI SCK / MOSI / CS_N |
| 42 | イヤホン有効（Q1経由でU8のSHUTDOWNを反転） |
| 2 | スピーカー有効（S1がONのとき） |

GPIO35〜37、起動設定用GPIO0/3/45/46、USB用GPIO19/20、基板LED用GPIO48は使わない。
M1の端子番号はメーカーv1.0ガイドのJ1/J3に対応。互換開発ボードでは端子番号を再確認する。
未記載のM1ピンは接続しない。

**電源投入時：** U2/U3は両方無効、CS_N/WR_N/RD_NはH、RESET_NはL。
イヤホンアンプはQ1のゲートプルダウンにより停止、スピーカーもプルダウンで停止する。
MCP41010は電源投入時に中点になるので、必ず音量0を設定してからアンプを有効にする。

## YM2203とDACの接続

| YM2203C | YM3014B-F（SOP16） |
| --- | --- |
| 23 OP-O | 7 SD |
| 22 SH | 4 LOAD |
| 39 φS | 10 CLOCK |

U5の1=+5VA、12=GND、14=RB、16=MP、2=TO_BUFF。
3/5/6/8/9/11/13/15はNCで開放。**DIP8版の電源端子などをSOP版へ流用しない。**

DACのRBはC13=10 µFでGNDへバイパスし、U6Aのフォロワで受けてMPへ戻す。
U6A出力を約2.5 VのVREFとして混合回路と音量回路にも使う。
TO_BUFFはU6Bのフォロワで受ける。RBを負荷へ直接つながない。
U1のSSG A/B/Cはそれぞれ20/19/18番のアナログ出力で、DACへは通さない。

X1は5 V・4.000 MHzのCMOS/TTL発振器。33 Ωを介してU1の38 φMへ供給する。
図面はECS-2100系列の8ピン相当4端子品（1=NC、4=GND、5=OUT、8=5 V）の資料に基づく。
発注する現物の端子・enable有無・起動時間を最終データシートで照合する。
Yamaha二品種間の3本のデジタル信号は短く配線し、φSとSHの波形・DAC入力H電圧を実測する。

## FM＋SSG混合と音量

U6は5 V動作可能なRRIOのOPA4192。汎用4558等へ無条件に交換しない。
4系統は各1 µFでDCを切り、U6Cの反転加算器でVREF中心に混合する。

- FM入力R22=22 kΩ、SSG入力R23〜R25=各100 kΩ、帰還R26=22 kΩ。
- FMの利得−1、SSG一系統の利得−0.22。初期の調整値であり、WebLabとの聴感一致は未検証。
- 帰還C18=330 pFの極は約21.9 kHz。SSG入力の低域遮断は約1.59 Hz、FMは約7.23 Hz。
- U7=MCP41010（10 kΩ）のPA=MIX_OUT、PB=VREF、PW=U6D入力。
  音色レジスタを変えずに、FMとSSGを一緒に減衰する。
- MCUはSPI mode 0で`0x11, code`を送る。percent=0ならcode=0、100なら255。
  電圧利得は概ねcode/256。0%時は併せて両アンプを停止し、端点抵抗による漏れを抑える。
- 部品値はミックス音の余裕を取った初期値。全ch最大音量や極端なSSGノイズではクリップ確認が必要。

## イヤホンとスピーカー

U8=TPA6110A2は左右独立の反転アンプで、各Ri=Rf=22 kΩ、利得−1。
各出力を**470 µF（＋をアンプ側）→22 Ω→ジャック**へ接続する。
バイアス電圧をイヤホンへ流さないため、出力コンデンサは省略しない。
32 Ω負荷で出力側の低域遮断は約6.27 Hz、抵抗分圧は約0.593。
U8の露出パッドはGNDへはんだ付けする。J3は機能端子番号で表しており、
採用ジャックのメーカー端子番号へ製造前に割り当てる。4極TRRS・マイク機能は含まない。

U9=PAM8302AAS（SO8）を5 Vで使用。両入力に各1 µF＋82 kΩを入れ、
内蔵10 kΩと合わせて公称利得を約1.63へ下げる。入力−側の結合コンデンサの外側はGND。
8 ΩスピーカーはOUT+とOUT−の間へ接続する。
**BTL出力なので、OUT−をGNDへ接続したり、ここへイヤホンを接続したりしない。**
測定も差動で行う。S1をOFFにするとSD_NがLとなり、イヤホンだけで使用できる。
この利得設定では出力は入力レベル次第で、ICの広告値「2.5 W」をそのまま得る構成ではない。

## 電源・実装

- J1→F1→+5V。M1の5V端子、YM2203、ロジック、発振器、スピーカーアンプへ供給。
- +5V→FB1→+5VA。DAC、OPA4192、MCP41010、イヤホンアンプへ供給。
- GNDは同一ネット。スピーカー大電流経路をDAC/RB/混合器の帰路と共用しない配置にする。
  電源・GNDを細い長いジャンパで数珠つなぎにしない。
- 100 nFは各ICの電源ピン直近へ。C1/C32の大容量コンデンサも所定の電源入口近くへ置く。
- **負荷時にもU1の端子で4.75〜5.25 V**であることを確認する。ケーブル・ヒューズの電圧降下を含める。
- M1へ外部5 Vを与える間は、開発ボードのUSBポートへ別の電源を同時接続しない。
  最初の書き込みはM1を回路から外してUSBで行い、USBを抜いてから回路へ戻す。
- 音源/DAC/ロジックを載せる基板＋M1のソケット構成を想定する。細ピッチ部品とPowerPADがあるため、
  変換基板や小型の試作基板を使う。高出力Class-D段を長いブレッドボード配線にしない。

## ファームウェアの実装条件（この成果物には未同梱）

回路だけでI2Cコマンドを理解することはできない。M1へのC/C++ファームウェアが別途必要。
制御ホスト側には既存のMicroPythonドライバーを使う方針だが、実機互換性の検証はこれから行う。

**仮想I2Cと実配線の違い：** 現在の`write_register()`は`writeto_mem()`を使う。
実配線ではレジスタ4への値20の書き込みも、音量20%指定も、どちらも`04 14`になり、
受信側では区別できない。実機で2バイトの直接レジスタ指定を許可せず、
`host_driver_adapter.py`の`YM2203I2CHardware`を利用して必ず`00 reg value`を送る。
メソッド名や音色・譜面APIは継承し、既存WebLabドライバーは変更しない。
BINプレイヤーの予約転送は元から明示opcodeを使用している。

```python
from machine import I2C, Pin
from host_driver_adapter import YM2203I2CHardware
sound = YM2203I2CHardware(I2C(0, scl=Pin(9), sda=Pin(8), freq=400_000))
sound.reset()
sound.volume(20)
sound.fm_tone("soft")
sound.fm_note(60)
```

上のコードが動くのは、モジュールMCUへ対応ファームウェアを実装した後。
ホストの`lib/`には既存`web_lab_ym2203_v1.py`とアダプターの両方を置く。

1. 起動直後は両アンプを無効にし、両データバッファを無効にする。
   発振器と電源の安定を待ち、RESET_Nを100 µs以上Lに保持してから解除する。
   音量code=0、SSGミキサー・音量、FMキーオフを設定し、必要な初期化後に音量20%から有効にする。
2. チップのパラレルバスは一つのタスクだけが操作する。I2C ISRから直接操作しない。
   無効パケットはキューへ反映せず、通信受付と適用完了を区別する。
3. 書き込み：RD_N=H、CS_N=HにしてU3を無効化。1 µs待ち、MCUデータ端子を出力にし、U2を有効化。
   A0/データを安定させてからCS_N/WR_Nを駆動する。
4. 読み取り：CS_N/WR_N/RD_NをH、U2を無効、MCUデータ端子を入力にする。
   1 µs待ってU3を有効にし、A0=0でCS_N/RD_NをLにして状態を読む。終了後はRD_N/CS_NをH、U3を無効にする。
   **U2/U3の同時有効化や、読み取り中のMCUデータ出力を禁止する。**
5. 最初のバス実装はデータ設定・保持およびWR/RDパルス幅を各1 µsとする。
   アドレス／データの各アクセス前にBUSY(bit7)を確認し、タイムアウト時は消音して診断する。
   信号波形を実測し、メーカーのセットアップ／ホールド条件を満たすことを確認する。
   OPL用の「12/84クロック」など別チップの待ち値を流用しない。
6. I2C 7bitアドレス0x44、操作00〜04と長時間操作05/06、4/6バイト状態応答を実装する。
   レジスタ書き込みは00付きだけを受け付け、曖昧な2バイト直接レジスタ形式は実装しない。
   アドレス0x44はYM2203自体の仕様ではなく、WebLab側で定義したモジュール仕様。
7. 予約時刻はuint32 ms、実行時の単調時計・演算は64bitを使う。最大131071件。
   6バイト packedなら786426 B、8バイト構造体なら1048568 B。PSRAMへ保存し、時刻を誤差累積させない。
   24時間ループも保存パターンを再利用する。実チップのBUSYによる遅れ・同一msの命令密度を計測する。
8. percent=0・停止・通信処理の致命的エラーではアンプを無効にし、キーオフ／初期化とキュー破棄を行う。
   音量・リセット時にポップ音が出ないよう、アンプ停止→ボリューム設定→安定待ち→有効化の順にする。

既存の[WebLab I2C仕様](https://github.com/kemusiro/micropython-web-lab/blob/main/docs/devices/ym2203-prototype.md)と
[WYM1仕様](https://github.com/kemusiro/micropython-web-lab/blob/main/docs/devices/ym2203-bin-format.md)を対応先とする。
ただし実バスでは、約739 kBの曲を400 kHz I2Cで送るだけで理論上約17秒以上かかる。
ブラウザの機能シミュレーションと同じ転送時間・開始遅延になるとは扱わない。

## 組み立て後の検証順序

1. 音源を挿す前に+5V/+5VA/+3V3、電源投入時のRESETとミュート状態を測定。
2. 4 MHzクロックとレベル変換、読み取り／書き込み時のバス衝突がないことを確認。
3. DACのRB/MP/TO_BUFF、U6各出力のDC電圧を確認。
4. SSGだけでドレミ、次にFMだけでドレミ。まずダミー負荷と低音量で確認する。
5. FM＋SSG混合、左右同音、スピーカーON/OFF、音量0〜100%、停止、再起動を確認。
6. 実I2Cの400 kHz波形、全曲BINの転送、密なレジスタ列、24時間動作と温度・電圧降下を確認。

## 一次資料・設計根拠

資料の図面をそのまま複製せず、接続と部品値をこの試作のために新規作成した。

- [Yamaha YM2203 datasheet](https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf)：端子図、電源、バス、リセット。
- [Yamaha YM3014B datasheet](https://www.quarter-dev.info/archives/yamaha/YM3014B.pdf)：SOP16端子、RB/MP、二つのフォロワ。
- [TI SN74AHCT541](https://www.ti.com/lit/ds/symlink/sn74ahct541.pdf)：5 V側へのTTL入力バッファ。
- [TI SN74LVC245A](https://www.ti.com/lit/ds/symlink/sn74lvc245a.pdf)：3.3 V電源・5.5 V入力耐性。
- [TI OPA4192](https://www.ti.com/lit/ds/symlink/opa4192.pdf)：4.5 V以上の単電源・RRIO。
- [Microchip MCP41010](https://ww1.microchip.com/downloads/aemDocuments/documents/OTH/ProductDocuments/DataSheets/11195c.pdf)：5 V SPI、抵抗端子、電源投入時中点。
- [TI TPA6110A2](https://www.ti.com/lit/ds/symlink/tpa6110a2.pdf)：単電源イヤホンアンプ、入力抵抗／帰還抵抗、出力コンデンサ。
- [Diodes PAM8302A](https://www.diodes.com/datasheet/download/PAM8302A.pdf)：SO8端子、BTL出力、入力抵抗による利得変更。
- [Espressif DevKitC-1 v1.0](https://documentation.espressif.com/esp-dev-kits/en/latest/esp32s3/esp32-s3-devkitc-1/user_guide_v1.0.html)：端子・PSRAM・排他的な給電方法。
- [ECS-2100系列](https://ecsxtal.com/store/pdf/ecs_2100.pdf)：発振器の4端子構成。

## 再生成と確認

以下はWebLabリポジトリのルートで実行する開発者向けコマンド。
KiCad CLIと`rsvg-convert`が必要。アダプターの検査にはリポジトリの既存ドライバーを読み込む。
ZIPを展開して図面・接続表を見るだけなら、これらのコマンド実行は不要。

```sh
python3 hardware/ym2203-i2c-prototype/generate.py
kicad-cli sch export svg -o hardware/ym2203-i2c-prototype/rendered/ hardware/ym2203-i2c-prototype/ym2203-i2c-prototype.kicad_sch
kicad-cli sch export netlist --format kicadxml -o hardware/ym2203-i2c-prototype/netlist.xml hardware/ym2203-i2c-prototype/ym2203-i2c-prototype.kicad_sch
kicad-cli sch erc --format json -o hardware/ym2203-i2c-prototype/erc.json hardware/ym2203-i2c-prototype/ym2203-i2c-prototype.kicad_sch
python3 hardware/ym2203-i2c-prototype/verify.py
```

検証スクリプトはKiCad出力の環境固有パスのみを正規化し、接続情報は変更しない。

デジタル接続の一致やERC合格は、アナログ特性・ノイズ・発振・音質・実チップ動作の保証ではない。
SPICE・基板配線・実機測定は未実施。本変更はWebLabの公開APIやブラウザ実装を変更しない。
