# P2 revision 3.1 / 分離基板 PCBレビューD

PGA2350ベース基板と、Core2350B0＋実YM2203C＋PCM1863音源基板の**配置・配線済みKiCad候補**。
承認済み[回路レビューC](../digital-module-review-c/README.md)の全292 ref・ピン接続・GPIOを維持し、
ソケットの物理フットプリントと基板形状を具体化した。回路C、一体型P2、Rev Cの過去資料は変更しない。

|対象|外形|電気部品|パッド照合|配線セグメント|ビア|ERC / DRC / 未接続 / 回路図差分|
|---|---:|---:|---:|---:|---:|---|
|[ベースPCB](base/p2-base-d.kicad_pcb)|194×142mm|147|567|1519|205|0 / 0 / 0 / 0|
|[音源PCB](module/p2-ym2203-d.kicad_pcb)|100×100mm|145|588|1657|263|0 / 0 / 0 / 0|

4層。In1.CuをGND面専用とし、信号はF.Cu・In2.Cu・B.Cuへ配線した。
ネイティブPCBは編集対象のCAD正本。ルーターの途中DSN/SESや一時探索ファイルは正本に含めない。
KiCad標準フットプリントはPCB内に埋込み、独自のP2Dライブラリも同梱した。
将来の編集では、このPCBと回路図をKiCadで更新し、下記検証・図面出力を再実行する。

## 配置と組立

- ベース左上にUNO R3の38接点を公式CAD由来の座標で固定。3.3V信号・IOREFを維持する。
- 音源基板の基準点はベース上の(90,38)mm。シールド予約領域の右端83mmから7mm離す。
  特定のシールドの張出しや追加コネクタまで無条件に装着できる意味ではない。
- ベースJMODは表面の雌、音源JMODは**裏面の雄**。実パッド32点すべての嵌合座標を照合する。
  32番の雄ピンを除き、雌側を塞ぐ。4本の非対称支持位置で行ずれ・回転を抑える。通電中は抜き差ししない。
- 一般的な四辺2×8ソケットは角で樹脂が干渉する。PGAとCoreには合計128個の個別端子ソケットを使う。
  CoreのP1..P4は論理的な16接点群であり、通常の長方形2×8ソケットを4本注文する指示ではない。
- 狭ピッチICを含め手実装する候補。最終点検でSMTパッドに近いビアを207か所移動した。
  **音源基板に残る5か所は、IC取付前のビア先埋め・平坦化が必要**。位置は
  [組立手順](ASSEMBLY.md)と[座標一覧](hand-assembly-vias.json)を参照する。

[高さモデル](mechanical-review.json)と[組立手順](ASSEMBLY.md)に、ソケット挿入量、支持穴、
スペーサーと部品高さの条件を記録した。CADによる条件付き検査であり、実部品の嵌合合格ではない。

## 電源・音声

電源系・ADC保護の回路は[レビューC](../digital-module-review-c/POWER-SEQUENCE.md)を維持する。
5V主幹は0.50mm以上の配線とIn2.Cuの補助面。MCUの3.3VはB.Cuにも面を配置する。
ADC用3.3VとMCU用3.3Vは別ネット、各基板の3.3Vレギュレーター出力も接続しない。
GNDを分断するアナログ用スリットは設けず、ADC・DACの戻り電流に連続した参照面を用意する。

DAC L/Rと基板間I2Sは短い表面配線にした。音源のSD/SH、CLK、SSG、USBを含む実配線の総長・層・ビア数を
[routing-review.json](routing-review.json)へ記録する。分岐込みの総長であり、伝搬遅延やインピーダンスの実測ではない。
[電源・配線レビュー](POWER-ROUTING.md)の制約を参照する。

## 外部との互換

HOST側GP0=SDA、GP1=SCL、GND共有、基板側GP20/21、0x42・100kHz、I2C v2、
YM22S002、64byte STATUS、32event/PUSH、1000msリースの仕様を維持する。
既存HOST/CファームウェアとRev Cの実機受入記録は変更していない。
既存モデル／HOSTの回帰検査は115件中111成功、非公開楽曲が必要な4件はスキップ。

UNO R3、USB CDC/MIDI、VBUS検出専用経路、RUN連動DAC/LINE遮断、MODULE_ENABLEから音源RUN/YM RESET/ADC電源への
直接停止経路を回路Cと比較して保持する。P2用MCU2台へのファームウェア移植は別工程であり、
**このCAD検査をP2上のHOST再生・MIDI切替・通信断試験の実機合格とは扱わない**。

## 検証と再出力

KiCad/pcbnew10.0.5を使用。pcbnewをimportできるKiCad Pythonで`verify.py`を実行する。
KiCadフットプリントライブラリが見つかる環境で両プロジェクトを開く。個人別のライブラリパスは保存しない。

```sh
kicad-cli sch erc --format json -o base/erc.json base/p2-base-d.kicad_sch
kicad-cli sch erc --format json -o module/erc.json module/p2-ym2203-d.kicad_sch
kicad-cli pcb drc --refill-zones --save-board --schematic-parity --format json --exit-code-violations -o base/drc.json base/p2-base-d.kicad_pcb
kicad-cli pcb drc --refill-zones --save-board --schematic-parity --format json --exit-code-violations -o module/drc.json module/p2-ym2203-d.kicad_pcb
python3 verify.py
python3 export_review.py --output /path/to/ignored-output/p2-digital-module-pcb-review-d.pdf
# exporterに別のPythonを使う場合: --kicad-python /path/to/kicad/python3
```

`verify.py`は1155パッドのネット、32嵌合座標、38 UNO接点、64 Core接点、4支持穴、電源・停止回路のCとの一致、
ソケット穴・パッド、GND信号禁止、積層部の背高部品を検査する。11条件の正常系と11件の拒否変異検査も実行する。
`verification.json`、両`drc.json`、`erc.json`が検査記録。
DRC個別除外は0。KiCad標準で無効な5検査（missing_courtyard、track_not_centered_on_via、
tuning_profile_track_geometries、footprint_filters_mismatch、footprint_type_mismatch）はそのまま記録する。
独自ソケットの実体外形は別の高さ・外形モデルで検査する。DRC0は製造／USB／音質／熱の保証ではない。

PDF出力はKiCad Python/CLI、rsvg-convert、Poppler、Ghostscriptを使用する。出力はGit管理外。
組立図は小さい番号＋対応表にし、長い受動部品名の重なりを避ける。回路図・PCB本体の参照名は変更しない。
再出力後は全ページを画像化し、特に支持穴・接地面・ADC/DAC周辺を目視確認する。
メーカー寸法の出典は[sources.json](sources.json)。メーカーPDF／写真、ルーターJARは再配布しない。
