> 以下は旧案の検証記録。現在のM1の算術確認は[module-hand-check.json](module-hand-check.json)、構成は[M1仕様](../MODULE-HAND-SOLDERED.md)。ツール未導入の記述は旧案検討時点の記録であり、後続のJT03合成結果とは分けて読む。

# 構成検討の検証記録

2026-11-14。対象はこのディレクトリーの構成案と解析ツール。基板、RTL、ファームウェアの実機受入ではない。

## 実施結果

| 確認 | 結果 |
| --- | --- |
| 実行環境 | Python 3.14.6、標準ライブラリのみ |
| `analyze_architecture.py --write`と再計算照合 | PASS。JSON/CSVを再生成し、保存内容との一致を確認 |
| クロック計算 | 指定8周波数＋10 kHz刻み351ケースで、VCOと分母の範囲を満たす偶数整数出力分周案を確認 |
| 端子予算 | 通常I/O 34／36、別枠の構成端子2。bankと実端子への配置は未検証 |
| メモリー予算 | EBR 20／30、SPRAM 1／4。対応するメモリー構成単位で丸めて集計 |
| DSP予算 | 3／8。合成した使用量ではない |
| Rev C主要部品対応 | A/Uの15個が漏れ・重複なく比較表へ対応。初期14〜15個の予算を電源等の具体化で17配置へ更新。総実装点数削減の証明ではない |
| 参照元のRev C静的検査 | PASS。106オブジェクト・95ネット・承認済み25 GPIOを既存検査で照合 |
| 実装方針 | Pico 2維持、他ICの直接実装、片面SMT委託。高額時の部分委託・手実装を文書化 |
| 面積予算 | 100×100／120×100 mmの機能領域の矩形重複・範囲と面積比を再計算。実フットプリントや配線の検証ではない |
| 全委託予算シナリオ | 公開料金と仮定を分離し、Decimalで2／5／10枚の計算・生成CSV／JSON照合を実施。正式見積り・価格上限の保証ではない |
| 5枚・片面SMT＋ソケット自前比較 | Uから共通費を引き継ぎ、ソケット80点×5枚と片面料金の差、部品代配分、追加送料、Economic感度を再計算。正式見積りではない |
| Economic候補BOM | 委託29品種（Extended16、Basic13）にEconomic表示あり。候補ref、区分、5枚数、自前ピッチ条件、生成CSVを照合。実寸・在庫・最終受託を検証したものではない |
| H1手はんだ案 | 180×140 mm、16機能領域・4取付予約の範囲／干渉、30／31本のI/O予算、Rev CのU2/U3ピッチとR1形状、図・JSONの再生成一致を照合。実フットプリントや購入版モジュールの配線成立は未確認 |
| Python構文・JSON・文書相対リンク | PASS |
| 空白検査 | `git diff --check`と新規ファイルの検査を実施 |

Rev Cの既存`verify.py`はレポートを書き出すため、今回の再確認ではその出力だけを捕捉し、歴史的な`rev-c/verification.json`を上書きしなかった。元のKiCad ERC/DRCレポート、ネットリスト、幾何情報の整合検査であり、KiCadを再実行した結果ではない。

面積予算は[layout-check.json](layout-check.json)、生成した配置検討図は[../layout-study.svg](../layout-study.svg)。仮領域の座標は`architecture.json`の`layout_study`にあり、`analyze_layout.py --write`で再生成する。費用は未見積りで、発注・予算承認は行っていない。

全委託の一次予算は[../UPPER-COST-ESTIMATE.md](../UPPER-COST-ESTIMATE.md)、入力は[../upper-cost-inputs.json](../upper-cost-inputs.json)、計算結果は[upper-cost-check.json](upper-cost-check.json)。業者への照会や発注はしていない。

5枚比較は[../FIVE-BOARD-COST-COMPARISON.md](../FIVE-BOARD-COST-COMPARISON.md)、入力は[../socket-cost-inputs.json](../socket-cost-inputs.json)、結果は[socket-cost-check.json](socket-cost-check.json)。最終演奏試験はPico／YM装着後に必要で、業者の同等検査受託を確認したものではない。

Economic候補の正本は[../economic-bom-plan.json](../economic-bom-plan.json)、検討内容は[../ECONOMIC-BOM.md](../ECONOMIC-BOM.md)、検査結果は[economic-bom-check.json](economic-bom-check.json)。メーカー未選定の自前部品と、回路・温度・電源・CPL・在庫の未確認事項を残しており、製造用BOMではない。

資料のハッシュと算術結果は[architecture-check.json](architecture-check.json)、主要IC／モジュールの対応は[../bom-comparison.csv](../bom-comparison.csv)を参照する。資料の正本・版は[構成案](../INITIAL-DIRECT-MOUNT.md#12-参照した一次資料)に記録した。

## 未実施

RTLシミュレーション、合成、配置配線、タイミング収束、具体的pinoutへの割当、Si5351レジスタ生成、PLLロック確認、電源立上げ、完全なBOM、回路図ERC、PCB DRC、試作基板・音声の実測は未実施。

探索したPATHおよびHomebrewの通常の実行ファイル配置に、yosys、nextpnr-ice40、iverilog、verilator、icepackは見つからなかった。今回の作業では追加インストールを行っていない。将来のFPGA実装開始時にツールとコミットを固定し、別の検証記録を作る。

既存`firmware-c`、Rev CのGPIO・回路・受入記録、サイト記事は変更対象にしていない。構成検討ブランチ上の未コミット資料として保存し、commit／push／Release／基板発注は行っていない。

## H1の再計算

```sh
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/tools/analyze_hand_assembly.py --write
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/tools/analyze_hand_assembly.py
```

[../hand-assembly-plan.json](../hand-assembly-plan.json)が正本。[hand-assembly-check.json](hand-assembly-check.json)と[../hand-layout-study.svg](../hand-layout-study.svg)は生成物。I/Oは32本からオンボード発振器用1本を保守的に予約した予算であり、購入版UPduinoのpin割当や動作検証ではない。
