# 一次資料とランド

Kの追加ランドは秋月の公式モジュール図面p1のTOP VIEWから原点・端子座標を独自に記述した。
メーカーPDFや商品画像そのものはリポジトリへ複製しない。

- [秋月110679商品・在庫・税込650円](https://akizukidenshi.com/catalog/g/g110679)
- [AE-Si5351Aマニュアル](https://akizukidenshi.com/goodsaffix/AE-Si5351A.PDF)：10×10mm、2.54mmピッチ/7.62mm列間、8端子、25MHz、0x60、CL8pF
- [Skyworks AN619](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN619.pdf)：register183 pp60–61、8pF=10、予約bit=010010
- [TI SN74LV4T125-Q1](https://www.ti.com/lit/ds/symlink/sn74lv4t125-q1.pdf)：PW14端子、3.3V、5.5V入力、IOFF、伝搬遅延
- [TI SN74LVC1G32](https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf)：DBV5、E4注文区分

その他のMCU/USB/Grove/G40・YM/DACの来歴は保存した[FのSOURCES.md](../low-cost-ym3014-pcb-review-f/SOURCES.md)を参照。
既存独自ランドのMIT表示を保持し、KiCad標準ライブラリを使う。他社のフットプリントや素材を無断複製しない。
