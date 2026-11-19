# LC YM3014 procurement review J

2026-11-20。review Iの在庫0の3行を再調査し、購入候補表を更新した。
秋月・スイッチサイエンスを第1・第2優先、残る海外調達はMouserへまとめる。
基板各5枚・部品1セット。YM2203CはRev C流用、YM3014B-Fは提供品。

ロジックIC2行は同じ基板パッドで使用できる候補を選定した。裸Si5351Aの包装違いは在庫0のため据置。
追加指示を反映し、**在庫優先の次案は秋月のSi5351Aモジュール650円を使うベース基板変更**とした。
[代替品適合確認](ALTERNATIVES.md) / [在庫優先の変更案・接続表](STOCK-PRIORITY.md) / [費用](COST.md) / [検証](VALIDATION.md)

| 購入資料 | 内容 |
| --- | --- |
| purchase-plan.json / .csv | 現F基板を維持する86行。3行の調達情報を更新、83行を保存 |
| stock-priority-purchase.csv / stock-priority-option.json | 次期変更用。U01を秋月モジュールへ置換する参考購入表、未配線・水晶削減未控除 |
| mouser-order.csv / mouser-43.csv | 現F用の43行。型番・数量取込用と根拠付き一覧。欠品U01を含むためそのまま発注しない |
| local-output/outputs/review-j/purchase-plan.xlsx | Summary/Purchaseの2シート。現F用明細と在庫優先比較を表示。Git管理外 |
| baseline-plan.json / baseline-price-observations.json | review Iの購入条件と43行観測を保存 |
| price-observations.json | 今回調べ直した3行だけの観測。残る40海外行はIの確認記録を継承 |

現F維持の概算は27,216.46円。在庫優先モジュール案は保守的に27,453.52円。
いずれも部品送料550円、基板送料込み換算5,209.60円、予備費2,000円を含む。
Jの2つの円価格は検索収録、他19行は外貨予算換算で、日本円カートの確定総額ではない。

既存F/G/H/I、承認GPIO、HOST・firmwareは保存。本追補でCAD/firmwareの変更、発注、commit/pushはしない。
新モジュールの基板変更は提案段階で、配置・配線・ERC/DRC・製造額の検証は次のCAD改版で行う。

再生成はPython標準ライブラリの`tools/update_plan.py`、XLSXはbundled artifact-toolの`tools/build_purchase.mjs`を使う。
XLSX入力はreview I出力または`--source-workbook`指定。`tools/verify_purchase.py`で参照番号・差分・金額・保存ハッシュを照合する。
