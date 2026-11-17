# F1 ULX3S 85F：Diamond追加検証の準備

2026-11-15。対象はULX3S PCB v3.0.8 / **LFE5U-85F-6BG381C**。
Windows版Diamond 3.14＋対応するSynplify Proを第一候補とする。
本記録で使用したMacにはDiamondがなく、**ベンダー合成・PAR・Traceは未実行**。
準備ツール／Tclの模擬呼出し検査は、Diamondでの成功を意味しない。

## ソースだけの持ち運び用bundle

プロジェクトルートで実行する。Python 3とGNU patchが必要なのは準備側だけ。
空の出力先へRTL・制約・Tcl・ライセンス・SHA manifestをコピーする。
上流usbcorevは固定SHAを確認し、出力コピーへだけ既存patchを適用する。

```sh
python3 fpga-standalone/boards/ulx3s/diamond/prepare.py --output outputs/f1/diamond-review-01
```

出力ディレクトリ全体をWindowsへコピーする。絶対パスをソースへ埋め込まない。
RTLは元の内容のまま拡張子を`.sv`にし、SystemVerilogとして扱う。
生成wrapperでのみモデル用VID/PID `CAFE:4001`を指定し、USBロジックが消去されるのを防ぐ。
正本topの既定VID/PID=0、既存HOST、プロトコル、端子表は変更しない。
**このbundleは解析専用。Bitgen・Export・programmerを呼ばない。実機用USB IDではない。**

## Windowsでの実行順

Diamondのライセンス、ECP5 device support、Synplify Proの導入を先に確認する。
DiamondのTcl Consoleから、コピーしたパスに合わせて実行する。

```tcl
source {C:/work/f1-diamond/project.tcl}
```

またはDiamond用に環境設定されたshellから`pnmainc project.tcl`を実行する。
`project.tcl`は新規project作成、Synthesis、Translateまでで止まる。
既存の`build/f1_ulx3s.ldf`を上書きせず、再試行は別のbundleを作る。
Tcl APIは公式User Guideの工程を基にした独自scriptで、実機のDiamond版による差異は未検証。

Translate後、Spreadsheet ViewとClock Summaryで次を照合する。

- 49 padすべてのLOCATE／LVCMOS33／pullを`pins.json`と照合。J1/J2は縦型オス番号。
- 12MHz P3専用入力、PLL 1/4/12・PFD12MHz・VCO576MHz・出力48MHz、独立49.152MHz A10、
  2系統のglobal distributionを照合。内蔵25MHzを使用しない。
- LPFの`dut/clk`は**合成前の候補名**。実CLKOP netに一致しなければ修正し、
  `timing-review.json`へ実名・有効制約を記録。unmatched preferenceを無視しない。
  synthesis.sdcのprimary clocksとPLL属性の関係、重複／派生clock認識も確認する。
- control物理周波数48MHzを維持。旧nextpnr検査の50MHzはsetup reserveでありPLL比ではない。
  48MHzでのslackが旧20ns設計目標との差0.833nsやjitter/uncertaintyを吸収できるか別途評価する。
- `io-review.csv`の全49行を分類し、実component／pad／translator／PCB負荷で入力・出力制約を確定する。
  I2Sは転送BCLK立上り基準でDATAとLRCKのsetup **およびhold**を評価する。
  旧予算のpad差4ns・PCB差2ns・受信各10nsは仮定で、部品保証値や配線実測ではない。
  これらは未確定のため、全port一括INPUT_SETUP／CLOCK_TO_OUTを自動発行しない。
- USB／I2C／FM serialの非同期入力、2FFの第1段・第2段、Gray FIFO、bundled-stable通知、
  async assert/sync releaseを個別に追跡する。`check_real_cdc.py`、`check_pnr_cdc.py`、
  `tools/board_checks.py`の既存検査対象を参照し、Synplifyで変わる実名へ対応付ける。
  第1段への例外を採る場合も理由・端点・対象cornerを記録し、同期段間のsetup/holdは残す。
- `usb_dn_bias`のnative OBZと出力disable固定HIGH、他USB bias／TX enable、open-drain I2Cを確認。
  Yosys向け属性とnative primitiveがSynplifyで同じ物理動作になるとはまだ認定しない。
- reset/permitのrecovery/removal、PLL reset幅、clock insertion/skewを確認する。
  **BLOCK ASYNCPATHS、BLOCK RESETPATHS、全clock間false pathは使わない。**

制約が対象netへ適用されたら、同じbundleの`route.tcl`を実行する。
Map、通常PAR、PARTraceまで。setup/hold全corner、recovery/removal、clock skew、
unconstrained paths、未対応／無効preferenceを確認する。
このPARが終了しただけでは、外部IOを含むtiming closureとしない。

```tcl
source {C:/work/f1-diamond/route.tcl}
```

`timing-review.json`の未記入項目を実reportに基づいて埋め、各例外・未制約pathの理由を残す。
Pythonがある環境でreportのSHA一覧を保存できる。

```sh
python collect.py --diamond-version "actual full version/build" --synplify-version "actual full version/build"
```

collectはreportを列挙するだけでPASSを推定しない。`.twr/.par/.mrp/.srr/.ior`等と、
変更したLPF/SDC/strategy、全log、使用版・corner・seed・hashを検証結果へ保存する。
共有前にlog内の個人パスやlicense情報を確認し、binaryやlicense fileをGitへ追加しない。

準備側にYosysがある場合は、生成wrapperを含めて別途mapping/checkできる。

```sh
python3 fpga-standalone/boards/ulx3s/diamond/check_bundle_oss.py --bundle outputs/f1/diamond-review-01 --yosys /path/to/yosys
```

これは追加のOSS構文・mapping検査で、Synplify/Diamondの代用ではない。
最終mapped open-drain／USB biasの極性とPLL比も検査する。旧P&Rの再実行ではない。

## 合否をまだ出せない範囲

前段nextpnrのglobal配線遅延モデルが0になる制限を、Diamondで補うための準備である。
Diamondのclock modelでもcarrierの実配線、Si5351 jitter、PLL基準P3のエッジ、USBアイ波形、
電源立上り、アナログmute、外付け監視のPVTを代替できない。
I/O未制約やclock間違反を一括waiverしてtiming PASSとしない。
HOST互換の機能証拠は既存RTL/HOST/C照合元のSHA一致により維持し、新しいF1実機受入とは分ける。

## 準備側の自動検査

```sh
python3 fpga-standalone/boards/ulx3s/diamond/test_prepare.py \
  --output outputs/f1/diamond-preparation-test-01.json
```

bundle SHA・port/ball・clock・Tcl工程・出力先保護・既存機能照合元を検査する。
Tclは通常のtclshに模擬prj APIを渡した検査であり、vendor binaryは呼ばない。

参照：[Diamond User Guide / Tcl](https://www.latticesemi.com/api/document/download?id=52111)、
[Diamond 3.14公式Tutorial / Timing PreferencesとTrace](https://www.latticesemi.com/-/media/LatticeSemi/Documents/Tutorials/AK/Diamond_3_14_Tutorial.ashx?document_id=54429)、
[ECP5データシート](https://www.latticesemi.com/api/document/download?id=50461)。
ベンダー文書やツールbinaryは同梱しない。
