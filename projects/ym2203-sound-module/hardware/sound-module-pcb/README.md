# 交換式サウンドモジュール PCB Rev A

共通ベース基板と、最初のYM2203C交換基板の試作設計。
音源側Pico 2のGPIO共通化案は2026-10-18に承認済み。
電源は外部安定化DC 5Vを主電源とする構成。旧版の電源選択JPWRは廃止した。
従来のブレッドボード結線図や `hardware/sound-module-platform/` のRev A案とは
電源・出力段・制御回路が異なる。旧版と部品番号を混用しない。

**実機未検証。専用ファームウェアは未実装。**
回路図・基板の検査結果は `rev-a/verification.json` を正本とする。
ERC/DRCの合格は、実チップでの音声取り込み、音質、タイミングの保証ではない。
将来の交換基板5種類は信号を収容する段階で、製造用回路図・PCBは含まない。

## 成果物

- `output/pdf/sound-module-platform-rev-a.pdf`：10ページ。構成、GPIO、コネクタ、基板配線図、
  組立・通電手順、検証結果、2枚のA0回路図。
- `output/sound-module-platform-rev-a.zip`：KiCad 10の編集データ、プロジェクト内ライブラリ、
  部品表CSV、接続表、ネイティブ検査結果、再生成スクリプト、PDF、SHA-256一覧。
- `rev-a/base/` / `rev-a/ym2203/`：各基板の `.kicad_pro` を開いて編集する。
- 各 `gerbers/`：試作版の両面銅箔・レジスト・シルク・外形・PTH/NPTHドリル。
  部品の現物寸法とコネクタ嵌合を確認してから試作発注に使う。
- 検証済み範囲：両基板ともERC/DRCのエラー・警告0、未配線0、回路図との不一致0。
  電気的タイミングや実機動作まで合格した意味ではない。

## 構成と設計範囲

```text
操作用Pico 2（外部、MicroPython）
  GP0 SDA / GP1 SCL / GND
          │ 3.3V I2C
共通ベース基板
  音源用Pico 2（C/C++）
  ├─ 内部I2C1 → MCP23017：リセット、ミュート、基板ID、補助信号
  ├─ 3.3V並列バス → 50ピン交換コネクタ → 音源交換基板
  └─ FMシリアル受信 → PIO/DMA → サンプル変換 → I2S
                                         ↓
                              AE-PCM5102A（左右のFM）
  交換基板のアナログL/R ────────────┐
                             MCP6022 左右ミキサー
                                         ↓
                             アナログミュート → 音量
                                         ↓
                         3.5mm TRS → AMS-22 LINE IN → PC
```

- ベース：180 × 160 mm、2層、FR-4、厚さ1.6 mm、外層銅35 µmを想定。
- YM2203C交換基板：130 × 120 mm、2層。同じ向きでベース右上へ重ねる。
- 配線の公称幅0.25 mm、狭いパッド付近の最小幅0.18 mm、最小クリアランス0.20 mm。
  5V電源0.8 mm、3.3V電源0.4 mmを公称値とする。ビア径0.7 mm、穴0.3 mm。
  両面GNDベタへ直接接続するため、GND端子の手はんだには十分な熱容量のこてを使う。
- USBとスイッチ操作のため、操作用Pico 2は基板外に置く。
- DACは既定のAE-PCM5102A DIP化キット。±電源の必要なAE-DAC5102とは別製品。
- ベースのMCP6022は2個、交換基板のSSG合成用は1個。
  将来のYM2608/YM2610のFMステレオを保持するため、ベースの混合経路も左右独立。
- イヤホン／スピーカーの電力アンプは載せない。出力先はAMS-22のLINE IN。
  モニター用イヤホンはAMS-22へつなぐ。
- デジタル信号の電圧変換、音源クロック、SSG等の出力調整、ADPCMメモリは交換基板側。
- ファームウェアは音源別。基板IDが違う場合に自動で別ファームウェアへ切り替わる機能はない。

## GPIOと内部I2C

全26 GPIOを使用。物理端子番号を含む正本は `rev-a/gpio.csv`。

| GP | 用途 | GP | 用途 |
| --- | --- | --- | --- |
| 0～7 | D0～D7、D0がLSB | 8 / 9 | A0 / A1 |
| 10 / 11 / 12 | I2S DATA / BCLK / LRCK | 13 / 14 / 15 | CS_N / WR_N / RD_N |
| 16 / 17 / 18 / 19 | FM SD / CLK / SH1 / SH2 | 20 / 21 | ホストI2C0 SDA / SCL |
| 22 | ARM、制御有効 | 26 / 27 | 内部I2C1 SDA / SCL |
| 28 | STATUS、IRQ/READY等 | | |

MCP23017は3.3 V、アドレス0x20。内部バスはホストバスから独立する。
ホスト400 kHz、内部100 kHzを初期評価値とする。内部I2Cは交換基板の将来用ローダーにも予約。
高速のデータ転送やFM受信はエキスパンダーを通さない。

| MCP23017 | 用途 | 初期値／接続 |
| --- | --- | --- |
| GPA0 | RESET_RELEASE | 外付け10kΩプルダウン |
| GPA1 | LINE_ALLOW | 外付け10kΩプルダウン |
| GPA3 | DAC_ALLOW | 外付け10kΩプルダウン |
| GPA4 / GPA5 | AUX0 / AUX1 | 外付け10kΩプルダウン |
| GPA2 / GPA6 / GPA7 | 未使用 | 未接続。GPA7は出力設定 |
| GPB0 / GPB1 / GPB2 | ID0 / ID1 / ID2 | ベース10kΩプルアップ |
| GPB3 | PRESENT_N | ベース10kΩプルアップ |
| GPB4 / GPB5 / GPB6 | 未使用入力 | GND固定、出力に設定しない |
| GPB7 | 未使用 | 未接続、出力設定 |

MCP23017のRESETはPicoのRUNへ接続する。ウォッチドッグリセットでRUNがLになるとは
仮定せず、PicoのGP22が入力へ戻ると外付け抵抗でARM=Lになるハードウェアゲートを設ける。

## 交換コネクタ

50ピン、2列25位置、ピッチ2.54 mm。全接点は `rev-a/connector.csv`。
デジタル信号はすべて3.3 V。音源ICの5 V信号は交換基板のレベル変換の後で接続する。
旧資料のAGND端子41/43/45も、今回のPCBでは連続したGND面へ接続する。
GND面にスリットを入れてデジタル信号の帰路を切らない。

| 番号 | 内容 |
| --- | --- |
| 1,3 / 2,4,6 | +5V / GND |
| 5 | Pico由来+3.3V |
| 7～14 | D0～D7 |
| 15,17 / 16,18 | A0,A1 / GND |
| 19,20,21 / 22 | CS_N,WR_N,RD_N / GND |
| 23,24,25 / 26 | RESET_N,ARM,STATUS / GND |
| 27～30 / 31 | FM_SD,FM_CLK,FM_SH1,FM_SH2 / GND |
| 32,33 / 34 | AUX_SDA,AUX_SCL / GND |
| 35～38 | ID0,ID1,ID2,PRESENT_N |
| 39,40 | AUX0,AUX1 |
| 41,43,45 / 42,44 | GND / ANALOG_L,ANALOG_R |
| 46,47,50 / 48,49 | 未接続 / GND |

コネクタ候補は次を設計値とする。シリーズ指定だけでなく末尾まで一致させる。

- ベース上面：Samtec **ESQ-125-58-L-D**、低挿入力、嵩上げソケット、ボディ高さ16.13 mm。
- 交換基板下面：Samtec **TSW-125-07-L-D**、ポスト5.84 mm、絶縁体2.54 mm。
- 基板対向面間19 mmでは、挿入長 `16.13 + 2.54 + 5.84 - 19 = 5.51 mm`。
  ソケットの挿入範囲3.68～6.35 mm内。M3絶縁スペーサーでこの間隔を保持する。
- 上記寸法はカタログ値。発注するMPNの最終図面・現物でもピッチ、番号方向、嵌合高さを照合する。
- 接点50は両基板とも電気的NC。**オスの50番接点を抜き、メスの50番位置を絶縁キーで塞ぐ**。
  未加工のコネクタには機械的な極性がない。非対称穴だけを逆挿し防止とは扱わない。
- ホットスワップ非対応。両PicoのUSBと外部電源を外してから交換する。
- 番号は電気接点番号。交換基板の下面から見た位置は上面視と左右反転する。
  KiCadデータは嵌合時に同じ番号が同じXYへ来るよう検証する。

交換基板原点はベースの `(50,0) mm`。固定穴は交換基板上で
`(5,5),(125,5),(5,115),(125,108) mm`、ベース上ではXに50 mm加える。
穴径3.2 mm。部品の高さは、基板間のコネクタ以外は13 mm以下を目標とする。
電解コンデンサー、ソケット、Picoのピンヘッダーを含めた現物寸法を確認する。

## 電源と出力

**外部の安定化DC 5V電源を必須とする。** JPOWERは2.54mmピッチの2ピン入力で、
`1=+5V入力、2=GND`。ACアダプタを使う場合も、そのDC出力を極性を照合して接続する。
9V/12V出力や非安定化電源は接続しない。DCジャックは基板に含まず、必要なら基板外へ設置する。

```text
JPOWER 1（外部+5V） → F1（PTC） → +5V → 音源IC・5V回路
                                      └→ D1（SS14） → Pico VSYS
                                                           └→ Pico 3V3 OUT → 3.3V回路
JPOWER 2（GND） ──────────────────────── 共通GND
```

電源選択JPWRとUSB VBUSから主電源への配線は廃止。Picoの40番VBUSは基板上で未接続。
Pico内蔵のUSB→VSYSダイオードと、外付けD1（A=+5V、K=VSYS）で給電経路を分離する。
D1はUSBからVSYS経由で音源基板やアダプタへ逆流することを防ぐため残す。
PicoのVSYSをYM2203の5V電源に使わない。F1は過電流保護で、逆極性・過電圧保護や降圧器ではない。

ケーブル、PTC、配線の電圧降下を含め、**YM2203Cの端子で4.75～5.25 V**を確認する。
安定化5V・定格1A以上の電源を候補とするが、基板側は従来どおりPTC 0.5A hold、
初期消費電流予算は全体400mA以下。1Aを基板へ流せるという意味ではない。
各素子の最大値を積算した実測保証ではなく、起動時・大音量時の電流を測って合否判断する。
将来の交換基板で負荷を増やす場合は、PTC・コネクタ・配線・電源容量を再評価する。

音源用PicoのUSBは書き込み・通信に利用できるが、USBのみでは5V音源回路を動作させられない。
USBだけでもPicoと3.3V側は起動するので、基板全体が無給電とは扱わない。
通常は外部5Vを先に投入してからUSBとホストI2Cを接続し、終了時は演奏停止・ARM=L、
ホストI2CとUSBを外した後に外部5Vを切る。外部5Vの活線抜き差しは行わない。
5V喪失を自動検出する回路は含まない。将来の専用ファームウェアもUSBのみで演奏を開始しない運用とする。

3.3VはPicoの36番から供給。外付け合計は初期設計予算200 mA以下とし、
Pico資料の推奨外部負荷上限300 mAより余裕を取る。
交換基板だけで200 mA使えるという意味ではない。YM2608/YM2610のメモリ・ローダーを
追加する際は、電流を積算し、必要ならベースの3.3V電源を別設計へ更新する。
別の3.3V出力をPico出力に並列接続しない。

操作用Picoは別USB給電。接続するのはGND/SDA/SCLだけで、両PicoのVBUSや3.3Vはつながない。
I2Cのプルアップは4.7kΩ。操作側にも存在する場合は重複分を実装しない。
この版にはI2Cの無給電時バス分離はない。片側だけを給電したまま接続しない。

FMはPCM5102Aの左右独立出力を470Ω/2.2nFでフィルターし、4.7µF無極性コンデンサーと
100kΩを通してMCP6022で合成する。交換基板のアナログL/Rも100kΩ入力。
帰還22kΩ、47pF。各ベース入力の小信号利得は約-0.22。
YM2203カードはSSG A/B/Cそれぞれに1kΩの対GND負荷を設け、AC結合後に
各100kΩ、帰還100kΩで先に合成し、L/Rへ複製する。
1kΩは同系統のYM2149資料の測定負荷を参考にした初期評価値で、
YM2203C現物の出力振幅と歪を測って調整する。コンデンサーだけでDC負荷を省略しない。
SSGは合成段が2段なので各チャネルの最終利得は約+0.22、FM経路は-0.22。
FM/SSGの相対極性も録音時に確認し、必要ならFMのPCM符号をファームウェアで反転する。
SSG3音の最大振幅を同時に加えたときのクリッピングは実機で確認する。

音量は基板外の二連10kΩ Aカーブ可変抵抗。JVOLの番号は
`1=L HIGH,2=L WIPER,3=L LOW(GND),4=R HIGH,5=R WIPER,6=R LOW(GND)`。
JLINEは `1=L(TIP),2=R(RING),3=GND(SLEEVE)`。
AMS-22のLINE INへステレオTRSで接続し、XLRや平衡モノ入力用の配線と混用しない。
音量位置とミュート状態は独立する。

## 起動とバス制御

```text
RESET_N = ARM AND RESET_RELEASE
DAC_XSMT = ARM AND DAC_ALLOW
LINE_RUN = ARM AND LINE_ALLOW

OE_WRITE_N = NOT(ARM AND RD_N)
OE_READ_N  = NOT(ARM AND NOT RD_N)
SAFE_CS_N = CS_N OR NOT ARM
SAFE_WR_N = WR_N OR NOT ARM
SAFE_RD_N = RD_N OR NOT ARM
```

ARM=Lでは両データバッファを無効にし、ネイティブCS/WR/RDをHに固定。
制御用AE-LLCNVの出力は有効のままなので、リセットと非選択レベルを5V側へ伝える。
書き込みは3.3→5V専用のAE-LLCNV、読み取りは5V入力耐性の74LCX245FTを別に使用。
5V側VIHが3.5V必要な双方向変換器へ、YMのTTL最小VOHをそのまま入力しない。

書き込み中はRD_N=H。データとアドレスを安定させてからCS/WRを操作する。
読み取りへ移る場合は、CS/WR=H → Pico D0～7を入力 → RD=L → バッファ待ち →
CS=L → 音源アクセス待ち → サンプル → CS=H → 音源バス解放待ち → RD=H →
バッファ待ち → Picoを出力へ戻す。この順序で論理ゲートの過渡的な重なりを避ける。
初期ファームウェアでは切替待ち各1µs以上から測定を始めるが、これは最適値・検証済みの仕様ではない。
YMのアドレス／データ書き込み後はBUSYを確認し、単なる固定短パルスの連打にしない。

起動時はARM=L、MCPの出力ラッチを0にしてから方向を設定し、IDとPRESENTを確認。
CS/WR/RD=H、データ入力、無音I2S、受信/DMAを初期化する。
該当音源のプロファイルが一致するときだけARMを上げてリセット解除する。
最後にDAC_ALLOW、LINE_ALLOWを上げる。停止・エラー時はLINE_ALLOWとARMを下げる。
アナログミュートはCD74HC4053で混合後の左右出力をVREFへ切り替える。
DACだけのミュートに依存しない。電源投入・切替時のポップ音の大小は未検証。

## 集合抵抗と実装

- ベース：RN1/RN2は8素子10kΩ、RN3/RN4/RN5は4素子10kΩ。
- YM2203カード：RN1は8素子10kΩ、RN2は4素子10kΩ（1素子未使用）。
- YM2203カードのRN3は8素子1kΩ、SSG A/B/Cの負荷に3素子使用、残り5素子は未接続。
- すべてKOA RKCのB回路、1番共通の2.54mm SIP。共通先がGNDか3.3Vか5Vかを回路図で確認する。
- 上記8パッケージを使う。1206の個別抵抗とはフットプリントも内部回路も異なる。
- 個別抵抗は1206、音声・基準電圧の指定箇所は1%、その他は5%でも可。
- セラミックコンデンサーは1206。4.7µF BP・10µF等は径5mm、ピッチ2mmのラジアル品を想定。
  47µFはこの版のフットプリントに収まる耐圧10V以上の小径品を選ぶ。
  径やリード間隔が異なる購入品は、フットプリントを合わせてから製造する。
- 74LCX245FTはTSSOP20、0.65mmのはんだ付け2個が必要。従来のDIP変換基板は不要。
- AE-LLCNVの2個は既製の24ピン・列間15.24mmモジュールを使用。
  内蔵デカップリングとDIR/OE抵抗を重複実装しない。
- AE-PCM5102Aにも列間15.24mmを使用。外部チャージポンプ／電源コンデンサーは必要。
- DIPのYM2203C、MCP6022、MCP23017、HCロジックにはソケットを推奨。
- IC本体や変換モジュールの実装面、切り欠き、1番ピンを組立図と照合する。

個別部品番号・値・販売元リンクは各基板の `bom.csv`。
基板外の操作用Pico、音量用二連ボリューム、ジャックモジュール、ソケット、
スペーサー、ケーブル、AMS-22は `rev-a/external-bom.csv` にまとめた。

## 他の交換基板

| 基板ID | 音源 | 共通側で収容した信号 | 交換基板側の追加設計 |
| --- | --- | --- | --- |
| 001 | YM2203C | FMモノ、SSGモノ、A0、IRQ | 今回の回路図とPCBに含む。4MHz |
| 010 | YM2608 | A0/A1、FMステレオ、SSG、IRQ | 8MHz、ADPCM用DRAMアクセス変換等 |
| 011 | YM2610 | A0/A1、FMステレオ、SSG、IRQ | 8MHz、独立したADPCM-A/Bメモリとローダー |
| 100 | SN76489AN | D0～7、CS/WR、READY、アナログ | 3.579545MHz、TIのビット番号逆順を基板で配線 |
| 101 | YMZ285 | D0～7、CS/WR、RESET、PLAY、アナログ | 4.096MHz、SO/POの調整。内蔵OTP内容に依存 |
| 110 | YMZ294 | D0～7、A0、CS/WR、RESET、アナログ | 4MHz、TEST/4-6選択等の5Vレベル処理 |

IDはID2..ID0。入力3本はプルアップされ、0にするビットを交換基板でGNDへ接続する。
YM2203カードはID1/2とPRESENT_NをGND、ID0を開放する。
STATUSの意味と極性、音声シリアル形式、クロックは音源別ファームウェアで扱う。
未使用のデジタル音声はベース側プルダウンと受信無効で扱う。

ADPCMメモリ候補は `reference/adpcm-memory-notes.md` を参照。
YM2608のDRAM端子にSRAMを直結できない。YM2610はA/B別メモリが必要で、
SRAMのロード用バス調停とアドレス復元回路も交換基板内に必要。
これらの回路と部品確定は今回のYM2203基板には含まない。
将来大きい基板にする場合、JMODと固定穴を維持して、ベース外側へ延ばす。

## 段階的な実機検証

1. 全電源OFF。ICを挿す前に電源間の短絡とJMODの全接点を導通確認する。
2. ベースのみ外部5Vで通電。JPOWERの極性、5V、3.3V、VREFを測る。3.3Vへ5Vが来ていないことを確認する。
3. ロジックのみ実装。ARM=LでRESET_N=L、LINE_RUN=L、DAC_XSMT=Lを確認する。
4. 無音I2Sを出してDAC、ミュート、左右音量、ライン出力のDC電圧を測る。
5. 全電源OFFでYM2203カードを接続。カード上の5V/3.3V、4MHz、ID=001を確認する。
6. YMリセット解除後、BUSY/ステータス読み出し、SSG単音を検証する。
7. FM SD/CLK/SHの波形を観測して、PIO受信とI2S出力を検証する。
8. FM/SSG同時再生、ミュート、リセット、停止、ホスト停止の挙動を確認する。
9. AMS-22で左右、クリッピング、ハム、USB由来ノイズを録音評価する。
10. リングバッファのアンダーラン／オーバーランを計測し、長時間再生へ進む。

YM2203の浮動小数点シリアル出力はI2Sそのものではない。PIO受信・整数PCM変換と
入力更新周期から48kHzへのレート変換を専用ファームウェアで実装する。
FM受信最大2 SM、I2S出力1 SMを別PIOブロックへ配置する予算を保つが、
PIO命令メモリ、DMA、I2Cとの同時動作はコード作成後に検証する。

## 再生成と検証

Python 3.11以降とKiCad 10 CLIで回路図を生成する。
`build_pcb.py` はKiCad同梱Pythonとpcbnewを使う。開発者向けパスは各環境で設定する。

```sh
python3 hardware/sound-module-pcb/generate.py
"$KICAD_PYTHON" hardware/sound-module-pcb/build_pcb.py
```

生成されたDSNをローカルで配線した後、`finish_pcb.py` でSESを取り込む。
配線に使用したFreeroutingは2.5.0 JAR版（GPL-3.0）、KiCadは10.0.5。
再配線用DSNはクリアランス0.23mmを指定し、短い細線を最小幅0.18mmへ戻す際にも
PCBの最小クリアランス0.20mmを満たす余裕を取る。最終合否はKiCad DRCで判断する。
外部サービスへ設計をアップロードせず、配線ツールやメーカーPDFを配布物に同梱しない。
ツールの設定・一時実行環境はリポジトリ外に置く。

```sh
"$KICAD_PYTHON" hardware/sound-module-pcb/finish_pcb.py base path/to/base.ses
"$KICAD_PYTHON" hardware/sound-module-pcb/finish_pcb.py ym2203 path/to/ym2203.ses
kicad-cli sch erc --format json -o rev-a/base/erc.json rev-a/base/base.kicad_sch
kicad-cli pcb drc --schematic-parity --format json -o rev-a/base/drc.json rev-a/base/base.kicad_pcb
python3 hardware/sound-module-pcb/verify.py
```

上の検査例の `rev-a` は本ディレクトリからの相対パス。
生成ファイルを手で編集して再生成で失わないよう、変更は生成元に反映する。
配線後のPCBは設計成果物として保存し、`build_pcb.py` は未配線状態へ戻すことに注意する。

## 一次資料

- [Pico 2](https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf) / [RP2350](https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf)
- [YM2203](https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf)
- [YM2149のSSGアナログ負荷条件](https://www.bitsavers.org/components/yamaha/YM2149_199209.pdf)
- [AE-LLCNV 回路図](https://akizukidenshi.com/goodsaffix/AE-LLCNV-LVC8T245_sch_20210113.pdf)
- [74LCX245FT](https://akizukidenshi.com/goodsaffix/74LCX245FT_datasheet_ja_20150130.pdf)
- [MCP23017 DS20001952D](https://akizukidenshi.com/goodsaffix/MCP23017-Data-Sheet-DS20001952.pdf)
- [PCM5102A](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)
- [MCP6022](https://akizukidenshi.com/goodsaffix/MCP6022.pdf)
- [CD74HC4053](https://www.ti.com/lit/ds/symlink/cd74hc4053.pdf)
- [MMBT3904](https://www.onsemi.com/pdf/datasheet/mmbt3904lt1-d.pdf)
- [TC74HC08](https://akizukidenshi.com/goodsaffix/TC74HC08AP.pdf)
- [TC74HC00](https://akizukidenshi.com/goodsaffix/TC74HC00A.pdf)
- [TC74HC74](https://akizukidenshi.com/goodsaffix/TC74HC74AP_datasheet_ja_20140301.pdf)
- [KOA RKC](https://akizukidenshi.com/goodsaffix/rkc.pdf)
- [Samtec ESQ](https://suddendocs.samtec.com/catalog_english/esq_th.pdf) / [TSW](https://suddendocs.samtec.com/catalog_english/tsw_th.pdf)
- [AMS-22](https://zoomcorp.com/manuals/ams-22-ja/)

回路記号・フットプリントは本設計用に新規作成。WebLabソフトウェア、公開API、WYM1形式の変更はない。
