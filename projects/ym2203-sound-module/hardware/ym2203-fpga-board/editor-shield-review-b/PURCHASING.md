# 秋月優先の購入部品表（review B）

2026-11-18参照。全46参照を秋月商品へ対応付けた。商品ページの在庫あり表示を確認。
価格・在庫は注文時点で再確認する。発注はしていない。

| 販売コード | 型番/用途 | 必要数 | 購入単位×数 | 税込小計 |
| --- | --- | ---: | --- | ---: |
| [131019](https://akizukidenshi.com/catalog/g/g131019/) | M154-240240-RGB | 1 | 1個入×1 | 840円 |
| [114827](https://akizukidenshi.com/catalog/g/g114827/) | RK09D117000B B10k | 4 | 1個入×4 | 240円 |
| [114936](https://akizukidenshi.com/catalog/g/g114936/) | RE111F-4S1-152S4-15P-A | 1 | 1個入×1 | 200円 |
| [103568](https://akizukidenshi.com/catalog/g/g103568/) | 24FC256-I/P | 1 | 1個入×1 | 90円 |
| [117166](https://akizukidenshi.com/catalog/g/g117166/) | TVDP01-095BB1 | 6 | 1個入×6 | 90円 |
| [116278](https://akizukidenshi.com/catalog/g/g116278/) | S-42 | 4 | 1個入×4 | 160円 |
| [100167](https://akizukidenshi.com/catalog/g/g100167/) | PH-1x40SG | 48 | 40個入×2 | 70円 |
| [115868](https://akizukidenshi.com/catalog/g/g115868/) | 20cm40P female-female cable | 8 | 40個入×1 | 200円 |
| [116102](https://akizukidenshi.com/catalog/g/g116102/) | CF16J1KB 1k | 6 | 100個入×1 | 170円 |
| [116272](https://akizukidenshi.com/catalog/g/g116272/) | RD16S 2K7 2.7k | 2 | 100個入×1 | 100円 |
| [116472](https://akizukidenshi.com/catalog/g/g116472/) | RD16S 4K7 4.7k | 1 | 100個入×1 | 100円 |
| [116103](https://akizukidenshi.com/catalog/g/g116103/) | RD16S 10K 10k | 8 | 100個入×1 | 100円 |
| [108517](https://akizukidenshi.com/catalog/g/g108517/) | MFS25F33RB 33ohm | 2 | 100個入×1 | 300円 |
| [107549](https://akizukidenshi.com/catalog/g/g107549/) | CL21B105KPFNNNE 1uF10V | 1 | 40個入×1 | 150円 |
| [117591](https://akizukidenshi.com/catalog/g/g117591/) | GRM219B31E106KA12 10uF25V | 1 | 10個入×1 | 150円 |
| [113582](https://akizukidenshi.com/catalog/g/g113582/) | RDER71H104K0P1H03B 100nF50V | 6 | 10個入×1 | 100円 |
| [108138](https://akizukidenshi.com/catalog/g/g108138/) | RDER71H103K0K1H03B 10nF50V | 2 | 10個入×1 | 100円 |

掲載部材の購入小計：**3,160円（税込）**。部品を持っていれば、不要な袋売り/ケーブル等は差し引ける。
PCB・送料・最終嵌合に合わせる支持材・任意DIPソケット・前面パネルは含まない。
LCDケーブルの8本は40本セットから分ける。encoderは付属専用shaftで操作し、RV用6mmノブを流用しない。

`bom.csv`は回路参照単位、`purchase-bom.csv`は袋/本/セットの購入単位。LCDモジュールと4ノブも後者へ加えた。
旧品番117576/117818/115630は販売終了、115331は入荷未定または販売終了のため採用しない。
105772の照光encoderは2026-11-04に次回入荷分の仕様変更注記があるため選外。
メモリーはFRAMからEEPROMへ変更。保存の完了待ち・page境界・中断処理は[STORAGE.md](STORAGE.md)参照。
