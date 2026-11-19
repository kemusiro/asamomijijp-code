# review F 購入資料：Mouser集約 I

確認日2026-11-19。[H](../low-cost-ym3014-procurement-review-h/README.md)を保存し、海外調達43行をMouserへまとめた。秋月を第1、スイッチサイエンスを第2優先として既存購入分を維持する。基板は各5枚、部品は1セット、YM2203CはRev C流用、YM3014B-Fは支給品。回路図・PCB・Gerber・GPIO・HOST・firmwareは変更していない。

| 費目 | 今回I / 円 | 保存H / 円 |
| --- | ---: | ---: |
| 秋月商品代 | 7,475.00 | 7,475.00 |
| Switch Science商品代 | 4,070.00 | 4,070.00 |
| Mouser商品代・部品消費税見込み含む | 7,378.47 | 60.28 |
| DigiKey商品代 | 0.00 | 8,183.98 |
| 部品商品代 | **18,923.47** | 19,789.26 |
| 部品送料・別送枠 | **550.00** | 3,050.00 |
| 裸基板3種類各5枚＋OCS送料 | 5,209.60 | 5,209.60 |
| 商品・送料計 | **24,683.07** | 28,048.86 |
| 一般予備費 | 2,000.00 | 2,000.00 |
| 総予算 | **26,683.07（切上26,684円）** | 30,048.86 |

**約26,700円**。H比3,365.79円低減、30,000円まで3,316.93円の余地がある。ただし、これは確定カートではなく条件付きの購入予算。部品の消費税10%を含め、未確定の基板輸入諸費用・外貨換算と日本円カート価格の差等は2,000円の予備枠で扱う。実装委託費・工具・新しいHOST Picoは含まない。

## 購入表

- [全86行の購入表CSV](purchase-plan.csv) / [計算の正本JSON](purchase-plan.json)
- [Mouser43行の在庫・販売単位・元通貨価格・出典CSV](mouser-43.csv)
- [Mouser入力用MPN・数量CSV](mouser-order.csv)：注文は実行していない。Mouser側のメーカー照合・包装・納期・価格を確認してから使う。
- [XLSX](local-output/outputs/review-i/purchase-plan.xlsx)：Hの2シートと購入計算式を維持。
- [調達確認・代替・欠品](SOURCING.md) / [費用・送料・税の前提](COST.md) / [検証](VALIDATION.md)

43行すべてで公開掲載の価格・販売単位・在庫表示を調査した。**40行は必要数量以上の在庫表示、U01/U10/U17の3行は在庫0表示**を採用した。検索収録と直接商品ページを区別し、在庫の引当・即納保証とはしない。全43行の日本円カート価格を取得したという意味でもない。外貨掲載価格の行はCSVに元通貨と換算前単価を残す。

Si5351AのGT包装品にも在庫0の直接表示があり、以前の検索表示による「GT在庫あり」は即納根拠から取り下げた。GTRを維持し、製造データを変更せずに納期確認待ちとする。欠品3行が揃わなければ1セットを完成できない。

## 再生成

`baseline-plan.json`はHの保存スナップショット。Python標準ライブラリで数量帯・税・為替・合計を計算し、bundled `@oai/artifact-tool`でHのXLSXをimportして必要セルを更新する。XLSXはGit管理外。

```sh
python3 tools/update_plan.py
node tools/build_purchase.mjs
python3 tools/verify_purchase.py .
git diff --check
```

`node`はbundled runtimeを使用する。依存モジュールはruntimeの`node_modules`へリンクし、リポジトリへコピーしない。別保存場所からの生成には`--source-workbook <HのXLSX>`を指定できる。F/G/Hと既存HOST/USB-MIDI/停止処理のファイルハッシュを保存・照合した。CAD変更がないためERC/DRCは再実行していない。新たな実機受入・部品購入・commit・pushは実施していない。
