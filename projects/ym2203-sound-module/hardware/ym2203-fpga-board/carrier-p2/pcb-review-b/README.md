# P2 revision 2.1 / PCB review B

レビューAを保存したまま、電源とソケットの見直しを反映した**配線済みPCB候補**を別ディレクトリに置く。
GPIO割当、UNO R3接点座標、HOST配線とI2C v2の仕様は維持する。
回路図・PCBの静的検査であり、P2実機受入・ファームウェア移植・発注承認ではない。

## 電源容量の確認

レビューAではDACとシールド電源までPGA2350内蔵レギュレーターへ載るため、
拡張電流100mAを含む計算で300mA上限を超える。Bでは次の2系統に分ける。
**両レギュレーターの出力は接続しない。**

|電源|担当|予算|定格・余裕|
|---|---|---:|---:|
|PGA2350 3V3|MCU、Si5351A、MCP23017、7 LED、変換IC、I2C pullup|259.4mA|メーカー上限300mA、余裕40.6mA|
|V3_AUX|PCM5102A、UNO 3V3端子|150mA|TLV75533PDBVR 500mA、余裕350mA|
|外部5V入力|上記2レギュレーター＋YM・アナログ・任意5Vシールド|約674.4mA|安定化5V/1.5A以上を基準|

計算正本は`power_mechanics.py`と`schematic/power-budget.json`。
PGAモジュール180mAは**設計上の割当**で、メーカー保証最大値でも実測値でもない。
Si5351Aはcore35mA＋1出力5.6mAを切上げ42mAとし、CLK1/2は無効化する。
PCM5102Aは48kHzのDVDD13mA＋AVDD/CPVDD32mAを使用する。
LEDは7個同時点灯を含める。全DIPとSTOP/TESTが同時ONのpullupも含める。

UNOの3V3供給は**100mAまで**、5V供給もJP5Vを閉じた場合だけ**100mAまで**を設計条件にする。
IOREFは引き続きPGA側3V3を示す。シールドの信号を5Vへ変更するものではない。
5V信号のシールド、電源の逆給電、汎用シールドの無条件対応は含めない。
A4/A5の切離しジャンパー、VIN/AREF未接続はAのまま。

追加UAUXはSOT-23-5のTLV75533PDBVR、入力・出力に各4.7uFを配置する。
DC biasと公差後の有効容量1uF以上を部品選定条件とする。
DACの3つのI2S入力には100k pulldownを追加し、XSMTの既定LOWと合わせて起動時を無音にする。
DAC出力のアナログ合成、SSG負荷、FM100%の基準定数は変更しない。

### 熱・電圧の限界

入力5.25V、出力3.2V、周囲30°Cの感度計算では、AUX LDOは約0.308W、
データシートのDBV熱抵抗231.1°C/Wで接合温度約101°Cとなる。
PGA2350公式回路図の内蔵LDOはAP7366EA-33SN-7（U-DFN2020-6）。
そのメーカー基準基板値46.2°C/Wと、厳しめの感度値139°C/Wを両方記録する。
**25.4mm角モジュールと本PCBはJEDEC試験基板と異なり、これらは実温度の保証ではない。**

初回は室内・周囲30°C以下で、シールドを外して起動する。
各レールの電流、LDOとPGAの温度、YM電源端子の電圧・リップルを測定する。
YMの推奨範囲4.75..5.25Vを負荷中に満たすことを確認する。
PTC、配線、電源ケーブルの電圧降下を無視して「5Vアダプターだから合格」としない。
USB VBUSは検出専用のままで、USBから基板へ給電しない。

## ソケット高さと部品干渉

### PGA2350

一般的なHarwin M20-7830842は20.72×5.04mm、高さ8.5mm。
4個の2×8ソケットを外周へ置くと、グリッドの20.32mm区間に対して端部が出て角で干渉する。
この組合せを無加工のまま使用する案は採用しない。

Bは**Mill-Max 0300-2-15-15-47-27-10-0の単端子ソケット64個**を候補にし、
角ピン0.64mmを受けられる種類に限定する。丸ピン専用ICソケットへ角ピンを押し込まない。
外径最大2.032mmに対し2.54mmピッチで、位置誤差を見込んだ隙間も計算する。
PCBはパッド径2.05mm、仕上り穴径1.20mm。穴径公差と端子径の適合を製造条件で確認する。

単端子は部品代と64か所の組立負荷が増える。回路BOMの164 refに端子64個の数量を隠さず、
`assembly-extras.csv`側へ記載する。通常の4ソケットを使う場合は端部切削を伴う別の実物確認が必要。

高さモデルはソケット上面約5.33mm、PGA基板下面を9.5mmに揃える治具を前提にする。
モジュール下面部品を3.6mmの保守的な枠とし、キャリアとの隙間5.9mmを確保する計画。
上面高さは約13.1mmの枠で扱う。**雄ピン長・実挿入量・接触保持力は未実測**なので、
1組を先に組み、3.5..4.5mm程度の有効挿入と底付きがないことを確認してから64本へ展開する。
PGA下へ別の部品は置かない。通電中にモジュールを抜き差ししない。

### UNO R3と外周部品

UNOヘッダーはレビューAの公式CAD由来座標を維持する。特殊間隔4.064mmとSPI位置も同じ。
Samtec SSW系の1列8/10/6/8接点・高さ8.51mmを比較基準とする。
ICSPは2×3の**雄ヘッダー**とし、2.54mm樹脂＋約6mmの自由ピン長を比較基準にする。
外周の雌ソケットとは種類を分け、シールド側のSPIソケットに無理なく嵌る高さを実物確認する。
シールド下面の突出を5mm以内とする場合、空のキャリア面まで3.51mmの余裕がある。
PGA、YM、電解コンデンサ、ボタン、LEDはシールド本体領域の外に置く。
個々のシールドの基板張出し、コネクタ、下面部品は別途そのシールドで確認する。

H1/H2/H4でシールドを支える。**H3はヘッダー端に近いため穴だけを残し、スペーサーとネジを付けない。**
大きなM3ネジ頭の取付けをDRC合格に見せない。外周4か所のキャリア固定穴は別に用意する。
裏面は端子・はんだを適切に切り揃え、台座との間に8mm以上の高さを取る。

## 基板・配線の検証

- 外形164×124mm、4層。In1.Cuは信号配線を禁止したGND面。
- 164電気部品＋8取付穴。UNOとPGA/YMの配置は専用データへ固定。
- 一般信号0.18mm、電源幹線0.50mmの配線クラスを基準。最小クリアランス0.15mm。
  細ピッチICのVDDは0.18mmの短いfanoutから0.6/0.3mmビアへ接続する。
  F.Cuに5V、In2.CuとB.Cuに3V3の電源面を補助配置し、In1.CuのGND面を維持する。
  通常のTHTはサーマル接続。PGAのA3/B4供給端子だけは密集部でスポークが孤立するため面へ直結する。
- すべての接続は回路正本とKiCad XML netlistから比較する。
- DRCは未接続、短絡、間隔、穴、定義済みcourtyardの衝突、silk、回路図との整合を含む。
  KiCad10標準で無効な5検査（missing_courtyard、track_not_centered_on_via、tuning_profile_track_geometries、
  footprint_filters_mismatch、footprint_type_mismatch）は検査記録へ列挙する。違反の個別除外は追加しない。
  独自ソケットとUNOの実体は別途body-clearances.jsonの外形比較で検査する。
- 接地面とUSB・水晶・クロック・音声の実経路はPDFとネイティブPCBで確認する。
- DRC合格はUSBインピーダンス・EMC・音質・電流・発熱・組立の実機合格ではない。

最終検査記録は`schematic/drc.json`、`schematic/verification.json`を参照する。
USBはFull Speed用の短い経路を基準にする。製造業者のスタックアップ未確定なので、
90Ω差動インピーダンスを保証した配線として扱わない。
USBデータはGND面を基準にしたプロトタイプ配線で、差動ペアの等長・製造公差を保証するものではない。

## 互換性と履歴

HOSTはこれまで通りGP0=SDA、GP1=SCL、GND共有。基板側GP20/21、0x42、100kHz、
YM22S002、64byte STATUS、32event/PUSH、1000ms leaseを維持する。
GPIO正本`../pins.json`と既存HOST/Cファームウェアは変更しない。
P2専用C版の移植と実機受入は別工程。レビューAとその検査記録も保存する。

## 再生成

KiCad CLI / pcbnew 10.0.5、Pico SDK2.2.0の割当表、Freerouting2.1.0を使用する。
FreeroutingのJARは同梱せず、`toolchain.json`のSHA-256と版を照合して使う。
ルーターはローカルだけで動かし、GUI・解析送信・APIサーバーを無効化する。
ルーターにはF.Cu/In2.Cu/B.Cuだけの3信号層モデルを渡し、実際の4層PCBのIn1.CuはKiCadでGND面を補充する。
これは物理的な3層基板の提案ではない。DSN/SESは再現用の中間CADテキスト。ソースの絶対パスは公開版から除く。

```sh
python3 generate.py --check
# pcbnewがimportできるKiCad Pythonで実行
python3 pcb.py --footprints /path/to/kicad/footprints
# toolchain.jsonに記録したオプションでDSNを配線してSESを作る
python3 router_input.py
# BoundedRouter.javaをtoolchain.jsonのJARでcompileしてローカル配線
# 入力schematic/p2-three-signals.dsn / 出力schematic/p2-b.ses
python3 finish.py
python3 power_mechanics.py
python3 verify.py
kicad-cli pcb drc --schematic-parity --format json -o schematic/drc.json schematic/p2-carrier-b.kicad_pcb
```

### 一次資料

- [Pimoroni PGA2350](https://shop.pimoroni.com/products/pga2350)
- [AP7366EA](https://www.diodes.com/datasheet/download/AP7366EA.pdf)
- [TLV755P](https://www.ti.com/lit/ds/symlink/tlv755p.pdf)
- [Si5351A/B/C-B](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/data-sheets/Si5351-B.pdf)
- [PCM5102A](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)
- [Harwin M20-7830842](https://www.harwin.com/products/M20-7830842)
- [Mill-Max pin receptacles](https://www.mill-max.com/catalog/download/2017-11%3A148.pdf)
- [Samtec SSW](https://www.samtec.com/products/ssw)

第三者PDF、モデル、ツールJARはGitへ追加しない。参照部品の製造図と実物の一致を確認する。

### ローカル配線ツールの呼出し

JARのSHA-256を`toolchain.json`と照合したうえで、作業用ディレクトリにclassを出す。

```sh
javac -d /tmp/p2-router -cp /path/to/freerouting-2.1.0.jar BoundedRouter.java
java -Xmx4g -XX:ActiveProcessorCount=2 -Djava.awt.headless=true \
  -cp /path/to/freerouting-2.1.0.jar:/tmp/p2-router BoundedRouter \
  schematic/p2-b.ses 300 --gui.enabled=false --api_server.enabled=false -da \
  -de schematic/p2-three-signals.dsn -do schematic/p2-b.ses -mp 30 -mt 0
```

Freerouting2.1.0のCLI指定だけでは最大passが反映されない場合があったため、
ラッパーで既定25pass上限と時間制限を適用する。継続配線には`-Dp2.router.passes=120`を使用した。部分的なSESも出力できるが、
**`verify.py`は未接続が1件でもあれば失敗する**。配線の完成判定はルーターのscoreではなくKiCad DRCによる。
ヒューリスティック配線は機械間のbit単位再現を保証しない。検査済み最終CADのハッシュを記録する。

### 局所配線の補正

記録済みSESへ`local_routes.py`と`schematic/local-routes.json`の局所配線を適用する。
M_D1とY_RD_Nの未接続を仕上げ、不要なY_RD_Nビアを1個除去し、U9/U19のGNDを近接接続する。
M_D1のU8側fanoutだけ0.45mm径／0.20mm穴のスルービアを使う。
他は主に0.60mm／0.30mm。製造業者へ0.20mm仕上りビア穴を指定する必要がある。
U8のプラスチック本体下のビアははんだパッドと穴を分離し、ソルダーマスクでtentする。
この例外はICのパッド内へ穴をあける指示ではない。
局所配線の座標はこのSESに対するものなので、自動配線をやり直した場合は必ずDRCを再実行する。

FM受信3本の100k抵抗をU16の近傍へ移し、長い枝配線を避ける。
`critical-routes.json`はCAD上の配線長合計と層数を記録したもので、波形・USB電気適合の測定値ではない。

YMの0.1uF C19はVDD21番端子の近くへ移し、GNDは局所ビアで接地面へ戻す。
`local_layout.py`でSES後の位置を確定し、`placement-refs.json`と実体外形の検査記録を再出力する。
配線候補の仕上げは、記録済みSESへの局所補正を含む。部品数と電気的接続は増やさない。

継続配線のDSNは`resume_routes.py`（KiCad Python）で出力し、
`python3 router_input.py p2-resume.dsn`で同じ3信号層モデルへ変換する。
最終完了判定は`local_routes.py`、`local_layout.py`、電源面補正後のネイティブDRCによる。

確認PDFの再出力にはrsvg-convert、Poppler、Ghostscriptを使用する。結合後にPDF構造を再書き出しし、全19ページを画像化して確認した。
