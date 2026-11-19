# review Kの製造用Gerberと4/2・2/2比較

2026-11-18。review Kの2層CADを製造用データへ出力し、主案用の4層ベースJと共通シールドBも同時に再検査した。
**試作発注の検討用。P2実機受入・現物嵌合・ADC結合容量の確定は未完了。発注・決済は行っていない。**
旧J/I/K CAD・旧Gerber・購入/見積記録は上書きしない。

## 発注する組み合わせ

| 案 | ベース | 音源 | シールド | 数量 |
| --- | --- | --- | --- | --- |
| 主案 | J・4層（`base-j4`） | K・2層（`module-k2`） | B・2層（`shield-b2`） | 各5枚、実装各1枚 |
| 比較案 | K・2層（`base-k2`） | K・2層（`module-k2`） | 同じB・2層 | 各5枚、実装各1枚 |

どちらか一案を選んだ場合は計15枚、予備12枚。部品は1セット。両案を同時に発注する数量ではない。
[送料込み見積比較](procurement/PCB-QUOTES.md) / [部品1セットの数量正本](procurement/order-profile.json)。

## CAM内容と検査

| 出力セット | 外形mm | 銅層 | 最小配線mm | PTH穴/長穴 | NPTH穴/長穴 |
| --- | --- | ---: | ---: | ---: | ---: |
| [base-j4](gerbers/base-j4/FABRICATION.txt) | 220×142 | 4 | 0.17 | 433（長穴4） | 14（長穴0） |
| [base-k2](gerbers/base-k2/FABRICATION.txt) | 220×142 | 2 | 0.15 | 1187（長穴4） | 14（長穴0） |
| [module-k2](gerbers/module-k2/FABRICATION.txt) | 100×100 | 2 | 0.18 | 450（長穴0） | 4（長穴0） |
| [shield-b2](gerbers/shield-b2/FABRICATION.txt) | 76×100 | 2 | 0.25 | 174（長穴8） | 9（長穴1） |

Gerber X2は銅箔・表裏マスク・表裏シルク・外形・jobを含み、ExcellonはPTH/NPTH別、mm絶対原点、長穴route形式。
2層ファイルに内層を混ぜない。4層の層順はF.Cu→In1.Cu→In2.Cu→B.Cu。裏面Gerberは反転しない。
外形は4直線、Edge.Cuts中心線で切削する。jobサイズは線幅0.10mmを含むため、仕上がり寸法へ流用しない。
手実装のためペースト・ステンシル・PCBAは含めない。ENIGを見積条件とする。標準マスクPluggedは樹脂充填/銅蓋とは異なる。

- KiCad10.0.5で作業コピーをzone再充填・保存し、4種類すべてERC/DRC/未配線/回路図差分0。
- 元CADと出力コピーのpad/net・track/via・zone外形が同じことを照合。ベースJの旧title/revisionは出力コピーだけJへ修正。
- Gerbonara1.6.3（Apache-2.0、ツールのみ使用）で層構成・4辺の外形・合計2,285個の穴/長穴を1対1照合。
- Excellonの丸め誤差は最大0.0005mm、許容0.0006mm。銅箔全プリミティブを数学的に逆照合した意味ではない。
- CAM再読込の表裏プレビュー8点を`inspection/`に分離。既知のG90、RoundRect、未出力pasteに関するパーサー注記のみ許容。
- 実CAMの穴欠落・0.1mm穴ずれ・内層欠落・job層数不一致・未配線レポート混入の5変異を拒否。
- H由来の参照名を保持したnetlist exportのannotation警告は元設計と同じ。ERCと全pin/net照合は別途0件を確認。

[CAM検査結果](verification/cam-verification.json)、[元CADとの形状一致](verification/source-equivalence.json)、
[入力SHA](verification/source-manifest.json)、[成果物SHA](verification/manifest.json)を保存する。
DRC0はUSB信号品質・電源温度・音声ノイズ・現物嵌合を保証しない。工場CAM審査と実機試験は未実施。

## 実装条件

G40/UNO/MCUソケット・支持穴の位置、開口なしシールドとの干渉条件、GPIO・既存HOST/USB-MIDI/STOP/leaseの仕様は変更していない。
[Kの配置・実装条件](../clean-sheet-pcb-review-k/README.md)と[Jのソケット高さ](../clean-sheet-pcb-review-j/ASSEMBLY.md)を継承する。
主案はベースJの先埋め3点＋音源Kの4点＝**7点**、比較案はベースKの2点＋音源Kの4点＝**6点**。
[先埋め座標一覧](verification/hand-assembly-vias.json)を使い、U8-7/U9-4などのパッド内穴をSMT実装前に埋めて平坦性を確認する。
工場で樹脂充填・銅蓋を依頼する場合は別料金で再見積となる。部品の現物嵌合とC14の有効容量/型番確定等は旧購入表の未完事項を引き継ぐ。

## 発注用ZIP

ZIPはプロジェクトGit管理外の`outputs/p2-review-k-fabrication-20261118/`に作成する。
`p2-base-j4-gerber.zip`、`p2-base-k2-gerber.zip`、`p2-module-k2-gerber.zip`、`p2-shield-b2-gerber.zip`の4種類。
**発注画面には基板ごとのZIPを個別に**渡し、数量を各5枚に設定する。
`p2-primary-4-2.zip` / `p2-comparison-2-2.zip`は選択用まとめZIPで、工場の単一基板アップロード用ではない。
ZIP内はテキストGerber/Excellon/jobと製造指定だけ。マップやプレビューを加工用ファイルに混ぜない。
ZIPとまとめのSHAは同出力先`SHA256SUMS.txt`、テキスト成果物のSHAは`verification/manifest.json`へ保存。

## 再生成と再検査

プロジェクトルートで、KiCad10.0.5、pcbnewを使えるPython、Gerbonara1.6.3を使うPythonを用意する。
既存フォルダーを上書きせず、新しい`--work`へ出力する。公開価格は後日変わるため、再計算だけでは新しい見積にならない。

```sh
python3 hardware/ym2203-fpga-board/manufacturing-review-k/tools/rebuild.py \
  --hardware-root hardware/ym2203-fpga-board \
  --work outputs/review-k-cam-rebuild \
  --kicad-cli kicad-cli --kicad-python python-with-pcbnew \
  --cam-python python-with-gerbonara
python-with-gerbonara hardware/ym2203-fpga-board/manufacturing-review-k/tools/test_cam.py outputs/review-k-cam-rebuild
python3 hardware/ym2203-fpga-board/manufacturing-review-k/tools/build_comparison.py
python3 hardware/ym2203-fpga-board/manufacturing-review-k/tools/verify.py
```

Gerber/Excellonはユーザーが明示的に求めた製造用テキスト成果物として管理。第三者ライブラリ本体は同梱しない。
参照：[KiCad CLI](https://docs.kicad.org/10.0/en/cli/cli.html)、[Gerbonara](https://gerbolyze.gitlab.io/gerbonara/api-concepts.html)。
