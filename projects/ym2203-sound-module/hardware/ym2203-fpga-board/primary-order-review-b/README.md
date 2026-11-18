# 発注準備 review B：ベースL4・音源K2・開口なしシールドB2

2026-11-19。USB-C修正版のベースLを採用する新しい購入資料。
基板は各5枚、実装は各1枚、部品は1セットの条件を維持する。
旧`primary-order-5pcb-1set`（J4/K2/B2）は保存記録として変更しない。
購入・製造発注・支払いは行っていない。現物嵌合・P2実機受入は未確認。

| 基板 | 寸法mm | 層/厚み | 購入/実装/予備 | 個別製造ZIP |
| --- | --- | --- | --- | --- |
| ベースL（USB修正版） | 220×142 | 4/1.6mm | 5/1/4 | `p2-base-l4-gerber.zip` |
| YM2203音源K | 100×100 | 2/1.6mm | 5/1/4 | `p2-module-k2-gerber.zip` |
| 開口なし音色編集シールドB | 76×100 | 2/1.6mm | 5/1/4 | `p2-shield-b2-gerber.zip` |

工場には基板別ZIPを個別に送り、各数量5を指定する。
まとめZIP`p2-primary-review-b-5pcb-1set.zip`は保管・確認用であり、パネルとして発注しない。
FR-4、緑マスク/白シルク、ENIG 1µinch、外層1oz、ベース内層1oz、単体基板、標準積層。
0.20mm最小穴・長穴を維持。外形はEdge.Cuts中心線、裏面は反転しない。
PCBA、ステンシル、管理インピーダンス、工場樹脂充填/銅蓋は指定しない。
7か所のビアはSMT実装前に手で埋めて平坦化する条件を継続する。

## 今回の変更

- PCB1：ベースJから[ベースL](../clean-sheet-pcb-review-l/README.md)へ。
  メーカー図面へ合わせたUSBランドと近傍配線のみ変更。LのERC/DRC/未配線/回路図差分0、CAM照合済み。
- J10：HRO TYPE-C-31-M-12をLCSC **C165948**で指定。2020-12-08の推奨ランドへ照合。
  16接点、信号のはんだ付け位置は12か所。旧注記「12接点」を訂正。
- C14（ベースCACL/CACR）：**GRM21BZ71C106KE15L**を試作採用。
  公称10µF/16V・0805は同じためCAD形状・回路定数は変更しない。
  小信号ACも含む[選定根拠と条件](CAPACITOR.md)を確認する。
- その他の部品85行は型番・数量・価格等を保存版から維持。音源K・シールドBのCAMは同一。

GPIO・40接点・UNO配列と既存HOST API・USB-MIDI・STOP/leaseの維持要件を変更しない。
P2用ファームウェア、USB/音声/熱の実測と新基板の実機受入は未実施。
Rev Cの受入結果を新基板の結果として扱わない。

## 購入資料の使い方

[購入用BOM](purchase-bom.csv)90行、[秋月分](akizuki-order.csv)30行、[他店/PCB分](other-suppliers.csv)60行。
[参照対応](reference-map.csv)274参照（ベース152＋音源76＋シールド46）。
MCU JCORE1～4はMCU1枚、独立レセプタクルJ02は合計128個。
PH-1x40SGは199接点使用＋注文予備40接点、40接点×6本で実装後41接点残る。

Excelは「購入リスト」「参照対応」の2タブ。
E5=部品セット数、F5=基板種類ごとの枚数、G=販売数、H=手持ち、I=予備、L=販売単位あたり税込円価格。
J=発注袋/本/ロット数、K=実装後残数。販売数が空欄なら発注数も未確定。
ソケット8個を先行購入して再使用する場合はHへ8を記入する。
販売数1を確認できた場合の本注文は128−8=120個。先行8個を加えて136個発注しない。
廃棄した試用品は手持ちに数えず、必要に応じIへ実際の予備数を入力する。

M5は価格入力済みの小計 **6,413.20円**、N5は未入力59行。
内訳は旧秋月保存価格6,290円＋C14の表示税込61.60円×2個=123.20円。
**総購入費ではない。** 在庫0のC14も参考価格として含む。税丸め・決済・送料は実カートで確認する。
C14だけ2026-11-19に再調査し、他行の価格・在庫は各行の旧確認日を保持した。
価格0と未入力を分け、端数を表示する。Artifact Tool再計算と保存XLSX検査済み。
Excelデスクトップでの再計算・実カート発注は未確認。

## 残る確認と費用

1. [現物確認票](FIT-CHECK.md)：MCU独立ソケット、G40 KEY6、UNO・LCD裏面リードを確認する。
   [記録JSON](fit-record.json)は全項目未実施のまま。少数端子試用で嵌合・底付き・支柱長を決める。
2. C14はDigiKey CTで2個、現在在庫0。2026-11-24入荷表示は予定で納期保証ではない。
   LCSC C162430は同型番の代替先だが、価格・在庫・最低数は未確認。別型番へ無条件代替しない。
3. J10・J02等、空欄の販売単位/価格/送料を発注前に確認する。
4. **新ベースLの送料込み確定見積は未取得。**
   [過去のJ4/K2/B2見積](../manufacturing-review-k/procurement/PCB-QUOTES.md)は同寸法・同層の参考履歴であり、Lの見積へ読み替えない。
   製造業者・発送方法・CAM審査後に今回の3ZIPで再見積する。部品送料・輸入費用も別。

## 再生成・検査

プロジェクトルートから次を実行する。旧版を出力先に指定しない。

```sh
python3 hardware/ym2203-fpga-board/primary-order-review-b/tools/build_order.py
python3 hardware/ym2203-fpga-board/primary-order-review-b/tools/verify.py
```

Excelは既存同様bundled `@oai/artifact-tool`で生成し、アプリの依存関係へ追加しない。
作業用ディレクトリへ`tools/build_workbook.mjs`をコピーし、bundled node_modulesを参照させる。

```sh
node build_workbook.mjs /path/to/order-plan.json /path/to/new-output
python3 hardware/ym2203-fpga-board/primary-order-review-b/tools/verify_workbook.py /path/to/new-output/p2-primary-l4-k2-order.xlsx
python3 hardware/ym2203-fpga-board/primary-order-review-b/tools/package_order.py --output /path/to/new-output --workbook /path/to/new-output/p2-primary-l4-k2-order.xlsx
python3 hardware/ym2203-fpga-board/primary-order-review-b/tools/verify.py --outputs /path/to/new-output
git diff --check
```

納品用ZIP/Excel/PNGはGit管理外`outputs/p2-primary-review-b-20261119/`。
テキストCAM、CSV/JSON、生成/検査コード、ハッシュ記録を版管理する。
保存版と新CADの入力SHA・生成物SHAは検査するが、再生成したXLSXのバイト一致は要求しない。
