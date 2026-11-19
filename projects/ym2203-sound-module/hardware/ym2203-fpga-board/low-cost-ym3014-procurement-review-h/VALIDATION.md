# 購入追補 H の検証

G/Fの回路・PCB・製造CAM・受入履歴を保存し、購入資料だけを更新した。KiCad回路図/PCBを編集していないため、ERC/DRCを再実行したとは報告しない。製造データと検証はGを参照する。

1. Gの在庫確認3行＋価格確認11行と今回の変更IDが過不足なく一致。
2. 86購入行の順序、使用数、全277参照番号はGおよびFのBOMと一致。重複・欠落なし。
3. 14行以外の72行はJSON内容を保存。XLSXでも行の値が保存され、全購入行の計算式がGと一致。
4. 包装数・購入個数・余り・税込小計を検証。DigiKeyとSwitch Scienceの送料無料条件を満たし、Mouserへ誤って送料無料を適用していない。
5. 合計をDecimal/JSONとXLSX計算式で照合。商品19,789.26円、部品送料/枠3,050円、PCB5,209.60円、予備費2,000円、総計30,048.86円。
6. Summary/Purchaseをレンダリングし、変更した金額・部品・注意書きの表示を目視確認。Excel実アプリでの確認は未実施。
7. F/Gの保存ファイルSHA-256と、今回のテキストに環境固有絶対パスや不要バイナリがないことを確認。XLSXはローカルのGit管理外。

ツール：Python 3（標準csv/json/decimal/hashlib）、bundled Node.jsと@oai/artifact-tool。GのXLSXをimportし、シート構成・購入計算式・行順を保持して更新する。依存パッケージや第三者ソースをリポジトリへコピーしない。

検証コマンド：

```sh
python3 tools/update_plan.py
node tools/build_purchase.mjs
python3 tools/verify_purchase.py .
git diff --check
```

これは公開カタログ照合・外形/電気仕様の静的比較・購入計算の検証であり、現物確保・試作基板の実測受入ではない。元TDKからWürthへのコンデンサー変更も実機のADC/DAC音質やノイズ、実装温度を測定した合格ではない。
