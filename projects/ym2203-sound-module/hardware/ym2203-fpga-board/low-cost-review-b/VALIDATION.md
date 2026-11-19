# 検討資料の検証記録

2026-11-19、Python 3.15.2、静的検査と既存モデル試験。

| 検査 | 結果 |
| --- | --- |
| LC-B tools/review.py と --check | PASS、GPIO重複/露出/mux候補、I2C分離/アドレス、4ノブ切替、通信量、販売単位・価格算術 |
| source-lock.json | PASS、現行CAD・active-plan・LC-A・C firmware/USB・HOST等63ファイルのSHA-256を保持 |
| LC-A tools/verify.py | PASS、旧44/28 GPIO、矩形48組、既存結果・予算・保全ハッシュ |
| procurement-review-d/tools/verify.py | PASS、87元BOM行と96購入行、数量・販売単位・税/送料/為替分離と旧CAD等 |
| editor-shield-review-bで python3 -m unittest -v | 13モデル試験PASS、保存/電源断/CRC/JSON/pickup等。新パネル実機の試験ではない |
| git diff --check / LC-B全テキストの行末空白検査 | PASS |

LC-Bの新回路図/PCBは未作成なのでERC/DRCを実行したとはしない。RP2350A上の音声/PIO/DMA/USB、I2C panel firmware、消音応答・電流・熱・音声は未実装/未検証。
新GPIO候補は未適用。既存Rev Cの合格記録は保存したまま、P2の合格へ読み替えない。
