# 主案の発注準備：ベース4層・音源2層、各5枚・部品1セット

2026-11-18。ユーザー選択により、**ベースJ・4層＋YM2203音源K・2層＋開口なし音色編集シールドB・2層**を採用する。
発注入口をこのフォルダーへ一本化した。比較用の2層ベースK、旧4層音源Iは今回の発注一式に含めない。
旧設計・Gerber・見積は履歴として保持する。部品購入・PCB発注・支払いは行っていない。

| 基板 | 寸法mm | 層 / 厚み | 必要数 | 実装 | 未実装予備 | 基板別ZIP |
| --- | --- | --- | ---: | ---: | ---: | --- |
| ベースJ | 220×142 | 4 / 1.6mm | 5 | 1 | 4 | `p2-base-j4-gerber.zip` |
| YM2203音源K | 100×100 | 2 / 1.6mm | 5 | 1 | 4 | `p2-module-k2-gerber.zip` |
| 開口なしシールドB | 76×100 | 2 / 1.6mm | 5 | 1 | 4 | `p2-shield-b2-gerber.zip` |

合計15枚を購入し、3枚だけ実装する。部品を5セット分購入しない。
[数量正本](order-plan.json)の`boards`が今回の選択で、古いPCB1〜3の版名に読み替える必要はない。

## 製造用ファイル

- [ベースJ・4層](gerbers/base-j4/FABRICATION.txt)、[音源K・2層](gerbers/module-k2/FABRICATION.txt)、[シールドB・2層](gerbers/shield-b2/FABRICATION.txt)。
- 各フォルダーはGerber X2・PTH/NPTH別Excellon・job・製造指定。検証済み[製造資料K](../manufacturing-review-k/README.md)から内容を変えずに選別した。
- 各基板のERC・DRC・未配線・回路図差分0、CAMの層・外形・穴位置照合、元CAD形状一致を確認済み。
- ZIP、Excel、確認用PNGはプロジェクトGit管理外の`outputs/p2-primary-order-20261118/`へ保存する。
- まとめZIP `p2-primary-order-5pcb-1set.zip`には、今回の3基板別ZIPと購入CSV・Excel・説明を入れる。
  **工場の発注画面には、中の基板別ZIPを個別にアップロードし、それぞれ数量5を指定する。**
  まとめZIPを1枚のパネルとして送らない。

材料FR-4、緑マスク・白シルク、ENIG 1µinch、外層1oz、4層ベースの内層1oz。単体基板・標準積層。
Edge.Cuts中心線を仕上がり寸法とし、jobの線幅込みサイズへ拡大しない。裏面Gerberも反転しない。
0.20mm最小穴・長穴を維持し、ステンシル・PCBA・管理インピーダンス・工場の樹脂充填/銅蓋は追加指定しない。

## 購入用部品表

| 資料 | 内容 |
| --- | --- |
| [購入用BOM](purchase-bom.csv) | 90行。必要数、使用数、販売数、手持ち、予備、注文単位、実装後残数、調達URLを分離 |
| [秋月注文一覧](akizuki-order.csv) | 30行。保存済みの価格確認分は税込6,290円 |
| [他店・製造見積一覧](other-suppliers.csv) | 60行。Waveshare・Pimoroni・DigiKey等と今回のPCB3行 |
| [回路参照対応](reference-map.csv) | ベース152＋音源76＋シールド46＝274参照。銅箔ジャンパー3点は追加購入なし |
| [数量JSON](order-plan.json) | 元表との一致、主案の版名・層数・数量、参照入力のSHAを保存 |

部品87行の型番・必要数・包装・手持ち・予備を旧1セット表から維持し、PCB3行を今回の版へ更新した。
Core2350B0のJCORE1〜4はMCU1枚、独立MCUレセプタクルは128個。
PH-1x40SGは199接点使用＋注文予備40接点を考慮し、40接点×6本。実装後41接点が残る。
YM2203C等を手持ちから流用する場合は、購入表の手持ち欄へ入力して控除する。

Excel `p2-primary-4-2-order.xlsx`は「購入リスト」「参照対応」の2タブ。
E5=部品1セット、F5=各基板5枚。G列=販売数、H列=手持ち、I列=注文予備、L列=販売単位あたり円価格。
J列は発注する袋/本/ロット数、K列は実装後残数。Gが空欄ならJ/Kも未確定のままにする。
M5は計算できた価格入力行の小計で、総購入費ではない。N5は価格未入力の行数。
包装・手持ち・セット数・基板枚数・価格0の変更を再計算し、保存XLSXの数量・274参照・エラーセルなしを検査した。
生成/計算エンジンはArtifact Tool。Excelデスクトップでの再計算は未確認。

## 費用記録と残る確認

[送料込み比較](../manufacturing-review-k/procurement/PCB-QUOTES.md)の主案欄を使う。
2026-11-18の匿名計算ではJLCPCB/UPS 237.05 USD（1USD=160円の仮定で37,928円）、PCBWay/SF 271.49 USD（43,438円）。
各5枚の製造費と日本向け同梱送料の推定で、部品代・部品送料・輸入税・通関/立替料・決済為替手数料は別。
実カート・住所・工場CAM審査後の確定見積ではない。配送業者や製造業者の発注を決定した記録ではない。
価格・在庫・販売単位は今回再調査せず、元資料の確認日を残す。秋月6,290円を全購入費として扱わない。

- [先埋めビア一覧](assembly-vias.json)：ベースJ3点＋音源K4点＝7点。SMT実装前に手作業で埋めて平坦化する条件。
  工場標準のソルダーマスクPluggedは樹脂充填/銅蓋やパッド平坦性の保証ではない。
- MCU独立レセプタクルとピン、G40/UNOコネクタ・支柱高さ、LCD裏面リードの現物合わせを引き継ぐ。
- C14のDCバイアス込み有効容量・型番、未見積品の販売単位/送料等は旧購入表の確認事項を引き継ぐ。
- P2 firmware、USB/音声/熱の実測と実機受入は未実施。Rev Cの受入結果を新PCBへ転記しない。

## 再生成と検証

プロジェクトルートから、Python標準ライブラリで数量表とZIPを再生成できる。既存の履歴フォルダーは上書きしない。

```sh
python3 hardware/ym2203-fpga-board/primary-order-5pcb-1set/tools/build_order.py
python3 hardware/ym2203-fpga-board/primary-order-5pcb-1set/tools/package_order.py --output outputs/p2-primary-order-rebuild
python3 hardware/ym2203-fpga-board/primary-order-5pcb-1set/tools/verify.py
```

Excel再生成にはCodexのbundled `@oai/artifact-tool`を使う。アプリのNode依存関係へ追加しない。
作業用ディレクトリへ`build_workbook.mjs`をコピーし、bundled node_modulesへのsymlinkを用意して、次を実行する。

```sh
node build_workbook.mjs /path/to/order-plan.json /path/to/new-workbook-output
python3 hardware/ym2203-fpga-board/primary-order-5pcb-1set/tools/verify_workbook.py /path/to/new-workbook-output/p2-primary-4-2-order.xlsx
```

バイナリのZIP・ExcelはGit管理外とし、テキストGerber・CSV/JSON・生成/検査スクリプト・ハッシュ記録をcommit対象にする。
