# 一次資料・ランドの来歴

2026-11-19参照。メーカー図面から寸法・番号を読み、独自ランドを作成した。メーカーPDF・第三者ライブラリ・ルーティングJARは同梱しない。

| 部品/対象 | 一次資料 | 使用した情報 |
| --- | --- | --- |
| Picossci2A | https://www.switch-science.com/products/9795 | 26.67×15.24mm、1.27mm端子とGPIO、電源/USB端子 |
| Picossci2B | https://www.switch-science.com/products/10507 | 36.83×17.8mm、56端子、SWD3穴とRESET配線、GPIO24/25のLED |
| USB-B | https://akizukidenshi.com/catalog/g/g100161/ / https://akizukidenshi.com/goodsaffix/5075BR-04-WH.PDF | Neltron5075BR-04-WH、TOP view端子、2.5mm信号列、12.04mmシェル間隔、リード/外形 |
| Grove 110990037 | https://akizukidenshi.com/catalog/g/g112634/ / https://akizukidenshi.com/goodsaffix/110990037-Model.pdf | 10mm幅、2mmピッチ、横向き開口、リード寸法 |
| Grove番号 | https://github.com/Seeed-Studio/OPL_Kicad_Library/blob/master/Seeed%20Fusion%20Component%20Libraries%20for%20KiCad/OPL_Connector.pretty/GROVE-HW4-2.0-90D.kicad_mod | 開口−YのTOP viewで1番−X、4番＋X。コードをコピーせず端子方向を照合 |
| Grove互換外形 | https://www.seeedstudio.com/blog/2022/11/18/seeed-grove-designers-guide-pcb-design-guidelines-and-more/ / https://statics3.seeedstudio.com/fusion/opl/datasheet/320110034.pdf | 110990037/1125R-4P対応。1.0mm穴で0.5mm角端子も許容する方針 |
| Groveケーブル | https://wiki.seeedstudio.com/Grove_System/ / https://wiki.seeedstudio.com/How_To_Choose_The_Right_Cable/ | 黄/白/赤/黒と信号/電源/GND。3.3V専用として接続 |
| YM3014B-F | [review Eの資料台帳](../low-cost-ym3014-schematic-review-e/sources.json) | 16SOP、RB/MP/TO_BUFF、DAC専用CLK、外形・タイミング条件 |
| LCD・可変抵抗・エンコーダ | [保存した購入資料](../procurement-review-d/README.md) | 現行LCD M154、RV16、保存エンコーダの実寸。別のWaveshare LCD図面と混用しない |

独自フットプリントと生成・検証スクリプトはプロジェクトMIT。標準フットプリントはKiCad10.0.5同梱ライブラリを使用し、回路基板内に埋め込まれる。KiCadライブラリのCC-BY-SA-4.0＋library exceptionの対象であり、標準ライブラリを本プロジェクト独自作成と表示しない。参照のみのSeeed公式ライブラリはCC-BY-SA-4.0で、スタンドアロン複製は追加していない。

ルーティングにはFreerouting2.1.0を外部ツールとして使用し、結果をKiCad10.0.5のnative DRCで再検証した。FreeroutingのJAR/Javaランタイムを再配布しない。接続・形状を独自コードで追補した最終`.kicad_pcb`を正本として保存し、自動ルーターの出力を無検証の完成品として扱わない。
