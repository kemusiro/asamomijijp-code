# 購入用部品表と組立

2026-11-20。PCB Kの全276参照を85購入行へ集約し、部品は1セット分だけ購入する。
予備4セット分の部品を購入する計算ではない。包装の余りは購入表で表示する。

| ファイル | 用途 |
| --- | --- |
| purchase-plan.csv / local-output/outputs/review-l/purchase-plan.xlsx | 全体表。発注包装数と1包装個数、購入個数、余り、税込単価/小計、在庫/出典URL |
| orders/akizuki.csv | 秋月の包装数を基準にした注文候補 |
| orders/switch-science.csv | Picossci2A/2Bを各1個 |
| orders/mouser.csv | 41行のメーカー型番・個数。日本円DDP、カットテープ/少量バルク |

秋月優先・SS第2、残る海外分をMouserでまとめる。Arrow/DigiKey/Waveshareの追加注文を必要としない構成。
現物未確保であり、メーカー型番をそのまま在庫保証と扱わない。

## Kで確定した数量差

- U01は秋月110679 AE-Si5351A-B 1セット、650円税込。裸Si5351Aの欠品待ちを避ける。
- X01の25MHz水晶は購入しない。モジュールに内蔵。
- PH-1x40SGは3本/120端子を維持し、モジュール用8端子を追加消費。使用95・余り25。付属ヘッダーの有無に依存しない。
- U10はSN74LV4T125QPWRQ1を3個、U17はSN74LVC1G32DBVRE4を1個。通常リール一括や有料MouseReelを選ばない。
- YM2203CはRev Cから1個流用、YM3014B-Fは提供済み1個。購入費0円だがBOMから除外しない。

## 実装条件

[KのASSEMBLY.md](../low-cost-ym3014-pcb-review-k/ASSEMBLY.md)を正本とする。
U13は新8端子モジュールのTOP VIEW、両電源3.3V。旧10端子ICの番号を当てはめない。
モジュール全高6mm以下、ベース/音源間隔12mm、音源下面リード2.5mm以下を確認する。
G40のKEY6、YMソケット、MCUの向き・裏面端子、Picossci2BのRUN/SWD手配線、パネル給電の条件を維持する。

P2 firmwareでは25MHz/0x60/CL8pFを使用し、RESET保持・出力消音中に設定する。
製造資料の完成は、P2 firmware完成や実機受入を意味しない。
