# review K 製造・購入資料 L

2026-11-20。[秋月Si5351Aモジュール採用review K](../low-cost-ym3014-pcb-review-k/README.md)から製造データを生成し、
基板価格と日本向け送料を再確認した。K以前のCAD・Gerber・HOST/firmwareは保存。
基板3種類各5枚、部品1セット、すべて手実装。YM2203CはRev C流用、YM3014B-Fは提供品。

| 基板 | 外形 / 層数 | 枚数 | 製造用ZIP |
| --- | --- | ---: | --- |
| ベース | 100×100mm / 4層 | 5 | [ベースGerber](local-output/p2-base-k-5pcs-gerber.zip) |
| YM2203音源 | 100×80mm / 2層 | 5 | [音源Gerber](local-output/p2-module-k-5pcs-gerber.zip) |
| I2C編集パネル | 100×76mm / 2層 | 5 | [パネルGerber](local-output/p2-panel-k-5pcs-gerber.zip) |

ZIPは各基板を別々にアップロードする。3枚種を1つに混在させない。
ZIP/XLSX/画面確認用PNGはGit管理外の`local-output/`、テキストGerber/Excellonと検証資料は`artifacts/`に保存。
旧F用のGerberや、K PCBそのものを製造ZIPへ混ぜない。

- [製造条件](ORDERING.md)：1.6mm・鉛フリーHASL・標準ビア。実装委託なし。
- [購入ガイド](PURCHASING.md) / [85行CSV](purchase-plan.csv) / [購入JSON](purchase-plan.json)
- [購入表XLSX](local-output/outputs/review-l/purchase-plan.xlsx)：SummaryとPurchase。注文包装数・余り・税込費用・送料を計算。
- 購入先別：[秋月](orders/akizuki.csv) / [スイッチサイエンス](orders/switch-science.csv) / [Mouser型番・数量](orders/mouser.csv)
- [送料込み概算](COST.md)：OCSで**27,358.48円**、予備費2,000円を含む。目標30,000円。
- [検証](VALIDATION.md) / [CAM照合](cam-verification.json) / [製造ファイルSHA256](manufacturing-manifest.json)
- [見積観測](quote-observations.json) / [部品送料の一次情報](source-observations.json)

3基板のERC/DRC・未接続・回路図差分0。CAM外形・銅層構成・全穴/長穴をnative KiCadと照合。
Kの8端子クロックモジュール用穴も含む。これは業者CAM審査や実物嵌合、P2実機受入を完了した意味ではない。

## 見積の範囲

JLCPCBの公開画面を匿名で操作し、手入力の寸法・層・枚数・HASL条件と、日本1kgの送料を2026-11-20に確認。
Gerberを業者へアップロードしたり、カート投入・注文・支払いはしていない。
配送先郵便番号に応じた最終カート、CAM追加料金、輸入諸費用は未確定。
部品の単価・在庫は原則K/J/Iの確認記録を継承し、今回全85行を再調査したとは扱わない。
秋月のクロック650円、SSの2モジュールの金額・送料区分、各部品店の送料規定は再確認した。18行の外貨価格は予算換算。

HOST v2・USB-MIDI・STOP/lease・G40・ADC/I2S/DACの設計契約と承認GPIOはKから変更しない。
P2 firmware移植、CL8pF起動設定、実機受入は未完。

## 再生成

KiCad CLI10.0.5、同梱pcbnew Python3.9.13、Gerbonara1.6.3を使用。
`PCB_PYTHON`と`CAM_PYTHON`は対応環境のPythonを指定する。

```sh
python3 tools/build_manufacturing.py --pcb-python "$PCB_PYTHON" --cam-python "$CAM_PYTHON"
"$CAM_PYTHON" tools/test_cam.py .
python3 tools/verify_purchase.py .
```

購入XLSX/CSVはbundled artifact-toolの`tools/build_purchase.mjs`から再生成する。
依存パッケージはリポジトリへ複製しない。全276参照との照合を行い、数量変更時は価格帯と送料を再確認する。
