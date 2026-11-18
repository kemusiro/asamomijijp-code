# P2 ベース review L：USB-Cの図面照合修正

2026-11-18 / revision **3.8-pcb-review-l**。
主案のベースJ・4層を保存し、[発注前部品照合A](../preorder-review-a/README.md)で見つかったUSB-Cの寸法差を修正した。
ベース220×142mm・4層、音源K100×100mm・2層、開口なしシールドB76×100mm・2層を維持する。
各基板5枚・部品1セットの条件も維持する。未製作で、実部品の嵌合・USB動作の実機受入は未完。

| 確認 | 結果 |
| --- | --- |
| ERC／DRC／未配線／回路図差分 | すべて0 |
| 電気部品／PCB固定穴 | 152／12、増減なし |
| 電気パッド照合 | 571パッド、pin/net維持 |
| セグメント／ビア | 2055／227（Jは2055／229） |
| 設計ルール・違反除外 | Jから変更なし・個別除外0 |
| G40／シールド嵌合 | 40接点／32接点、座標誤差は丸めで0mm |
| USB-C以外のfootprint | 全163個の位置・角度・表裏・pad・値・型維持 |
| USB局所以外の配線／ビア | 中心線・幅・層・net・穴を照合、一致 |
| Gerber／ドリル | 4層・外形・PTH431／NPTH14、CADと独立照合 |

[回路図](base/p2-base-l.kicad_sch)／[PCB](base/p2-base-l.kicad_pcb)／[検証記録](verification.json)。
[CAM表面](manufacturing/inspection/top.svg)／[USB-C拡大](manufacturing/inspection/usb-top.svg)。
元J・比較ベースK・音源K・シールドB・既存注文一式は上書きしていない。

## USB-Cの変更

対象はJUSB、購入表J10。**HRO TYPE-C-31-M-12／LCSC C165948**の2020-12-08メーカー図面を基準とする。
16接点で、GND/VBUSの共用により信号のはんだ付け位置は12か所。BOMの旧noteの「12接点」は修正対象。
[専用footprint](P2L.pretty/USB_C_HRO_M12_20201208.kicad_mod)をプロジェクト内に保持し、外部ライブラリ更新で置換しない。

原点は位置決め穴2個の中点。+yはUSB開口方向。原点から基板端まで5.79mm、基板上の原点(133,5.79)mm・回転180度。
USB-Cの原点の定義を変えたため、Jの(133,4.5)mmとの単純な部品移動量比較は使わない。
実際の位置決め穴列はJより基板端へ1.31mm、信号ランド列は1.685mm移動する。

| 寸法 | Lでの設定 |
| --- | --- |
| 位置決め穴 | x=±2.89mm、y=0、NPTH径0.60mm |
| 信号ランド | y=−1.07mm、長さ1.14mm。幅は外側GND/VBUS0.60mm、他0.30mm |
| GND／VBUSの左右中心間隔 | 6.40mm／4.80mm |
| シェル中心 | x=±4.325mm、y=−0.50／3.68mm |
| シェル長穴 | 幅0.60mm、全長1.70／1.40mm |
| シェル銅箔 | 幅0.90mm、全長2.00／1.70mm |

外側GND4ランドは長円、他の信号ランドは角丸率25%とした。
図面のランド外形寸法・中心座標を維持しつつ、既存の穴クリアランス0.25mmを満たす形状とする。
図面の四角いランドをそのまま写した銅箔形状ではない。ルールを緩めたり違反を除外したりしていない。
図面版との一致未確認の旧STEPモデルは専用footprintから外し、旧図形のF.Fab／courtyardは包絡参考として残した。
メーカー図面・現物が寸法の根拠であり、3D表示による実物嵌合の保証は付けない。
派生footprintの[ライセンス・帰属](P2L.pretty/ATTRIBUTION.md)を明記した。

USB近傍のD+/D−、CC、VBUS、GNDと、コネクタ固定脚を避けるV3_AUXの一部分を引き直した。
変更領域は基板座標x127～140mm・y0～12.5mm。領域外の配線・ビアの幾何はJと一致する。
旧Jでの4本のUSB周辺GNDビアを2本へ整理した。信号線の追加ビアはない。
新しいGNDビアはランドのはんだ吸込み判定領域から離し、既存ベースの先埋め3か所を増やさない。

## 維持する仕様・実装条件

G40／KEY6、UNO R3／3.3V、USB-MIDI・CDC、HOST I2C、STOP／lease／制御権切替の仕様は維持要件。
GPIO・電気回路・MCU・音源・部品数・基板外形・支持穴・DIP/STOP/TEST位置は変更しない。
P2ファームウェアと新基板でのHOST/USB-MIDI実機試験は未実施。Rev Cの受入を転記しない。

USB-Cは上辺にあり、音源の領域(90,38)..(190,138)mmとシールド(7,7)..(83,107)mmの外側。
それ以外の部品・接点は不変で、J/K/Bの既存の条件付き高さ検討を引き継ぐ。
MCUソケット・Samtec・支柱・LCD裏面リードの現物確認は引き続き必要。
先埋めはベース3か所＋音源K4か所。標準のマスクPluggedを樹脂充填・平坦化の代わりにしない。

## 製造データと購入表の扱い

[LのGerber](manufacturing/gerbers/FABRICATION.txt)はベースの差し替え用。
Git管理外の`outputs/p2-review-l-usb-20261118/p2-base-l4-gerber.zip`へ同一内容をまとめる。
PCB枚数は5。音源K・シールドBの既存Gerberは変更しない。
従来の`primary-order-5pcb-1set`はJ4/K2/B2の保存済みスナップショットで、今回書き換えない。
Lの製造データをその旧まとめZIPへ手で混在させない。残る部品確認後に注文用一式を再生成する。

[購入差分](procurement-delta.json)に、PCB1の版L・5枚、J10の調達コードC165948・1個・16接点を記録した。
それ以外の必要数は既存の1セット表を維持する。新規価格・送料・販売単位は今回確定していない。
C14（CACL/CACR）のDCバイアス込み容量・最終型番は引き続き未確定。
今回発注・購入・commit・pushは行っていない。

## 検証と再出力

KiCad／pcbnew10.0.5、Gerbonara1.6.3。
[検査スクリプト](tools/verify.py)は保存済みCADとレポートを照合し、旧Jランドと4つの不正変異を拒否する。
パッド位置・穴・スロット・D+/D−の誤配線・接点欠落を検出する。実機USB品質や管理インピーダンスの試験ではない。
Gerber照合は[元CAD形状](manufacturing/native-geometry.json)に対し、独立パーサーで層・外形・穴を比較した。
全銅箔図形の数学的逆変換や工場CAM承認まで行ったという意味ではない。

プロジェクトルートから、pcbnewの使えるPythonで次を実行する。

```sh
python3 hardware/ym2203-fpga-board/clean-sheet-pcb-review-l/tools/verify.py
python3 hardware/ym2203-fpga-board/clean-sheet-pcb-review-l/tools/rebuild_cam.py --work /path/to/new-work --kicad-cli kicad-cli --kicad-python python3 --cam-python /path/to/gerbonara-python
git diff --check
```

再出力は新しい空の作業ディレクトリで行い、保存済みCADを上書きしない。
CADが最終配線の正本であり、初期配置生成器や旧J/Kの生成器で上書きしない。
