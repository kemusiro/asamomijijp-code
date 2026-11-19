# 検証手順と範囲

2026-11-20。KiCad10.0.5 native CLI、KiCad同梱Python3.9.13/pcbnew、Python3.15.2。
局所配線には保存したF用のグリッド探索をK用に適用し、ネイティブDRCで仕上げた。
外部ルーター/グリッドの一時データ、メーカーPDF、実行ファイルは配布しない。
完成した`.kicad_pcb`が配線の正本。初期状態を作る`revise_pcb.py`だけで最終配線を再現できるとは案内しない。

## 結果

| 基板 | ERC | DRC違反 | 未接続 | 回路図差分 |
| --- | ---: | ---: | ---: | ---: |
| base | 0 | 0 | 0 | 0 |
| module | 0 | 0 | 0 | 0 |
| panel | 0 | 0 | 0 | 0 |

個別DRC除外0。全276参照の全パッド番号とネットをネイティブ回路図XML/PCB間で照合。
新U13の全8端子をメーカーTOP VIEWから独立定義した座標と照合した。
Y1だけを削除し、変更対象外の部品値・全MCU GPIO・G40信号・その他の実装原点/表裏をFと照合する。
G40は全40接点のXYと表裏、外形・層数・通常ビア・線幅・AUX放熱ビアと電源ゾーンも照合。
モジュール11×11mmのcourtyard投影と他部品のbboxの重なり0を確認し、積層は6mm高を上限条件とする。

PCB規則の有効/非適用項目はFから継承し、結果JSONの`ignored_checks`に列挙する。
短絡・クリアランス・未接続・穴間隔・courtyard・シルク・回路図差分を有効のまま検査。
U13に古いMSOP用のカスタム規則は残さない。GND/電源の銅箔を再充填して検査する。

保存したF/G/H/I/Jと、それ以前のHOST/firmware等のSHA256を検査した。
既存C版MIDIモデル14件、streamモデル18件中17件成功・1件は曲データ未指定のためスキップ。
新しいGPIO/HAL・P2上で実行した試験ではない。
購入表85行・全276参照・ヘッダー8端子追加消費・水晶削除と27,358.48円を独立計算した。

## 再検証

```sh
python3 tools/native_checks.py --pcb-python /path/to/kicad/python3
python3 tools/purchase.py
```

`native_checks.py`は回路図を`inputs/*-f.json`から`design.py`の明示差分で再生成し、native ERC/XMLを照合。
3枚の配線済みPCBを`--refill-zones --save-board --schematic-parity --severity-all --exit-code-violations`で検査し、
最後に`tools/verify_pcb.py`の独立した端子/機構/保存ハッシュ検査を実行する。
一時コピーで検査する場合は`P2_REFERENCE_ROOT`へリポジトリのhardware/ym2203-fpga-boardを指定する。
`tools/clock_footprint.py`は新ランドだけを再生成する。最終PCBを初期化する`revise_pcb.py`を通常の再検証では実行しない。

## 未完了

現物の穴・ヘッダー・ソケット嵌合、高さ、電源・熱、クロック周波数/波形/ジッタ、音質、USB電気特性は未受入。
P2 firmware移植ではregister183=8pF、出力無効での初期化、異常停止、HOST/MIDI制御権切替を実装/実測する。
全曲、STOP、通信断、USB切断・復帰を実機で回帰し、古い受入結果をKの合格へ転記しない。
Kの新Gerber、最終CAMカートと送料、現物購入は未実施。
