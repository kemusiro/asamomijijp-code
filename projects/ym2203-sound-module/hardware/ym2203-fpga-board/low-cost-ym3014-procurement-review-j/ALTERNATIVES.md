# 在庫0の3行の再調査と採用判断

2026-11-20。review Iを保存した購入候補の追補。掲載情報は予約・確定見積ではない。
日本Mouser商品ページの直接取得はできず、公式一覧の検索収録を使った。価格と在庫の収録時期を分ける。

| ID・必要数 | 現行品 | 選定結果 | 少量購入と費用 |
| --- | --- | --- | --- |
| U10・3個 | SN74LV4T125PWR | SN74LV4T125QPWRQ1へ。掲載在庫18、2日前収録 | カットテープ、最低1・倍数1、282.4円税別/個、税込小計931.92円 |
| U17・1個 | SN74LVC1G32DBVR | SN74LVC1G32DBVRE4へ。米国一覧の1週前収録は在庫1,656 | カットテープ、最低1・倍数1。古い日本円価格112.9円税別、税込124.19円 |
| U01・1個 | SI5351A-B-GTR | 現PCBを維持する購入表では据置・欠品。GTも在庫0 | 375.4円税別はreview Iから継承。税込412.94円の仮枠 |

U17の日本一覧は4か月前収録で在庫3,376。より新しい米国一覧1,656を在庫欄に使った。
同じ米国一覧の税別USD0.79を160円/USDで換算すると税込139.04円。
円価格124.19円との差14.85円は確定カートで更新する。税別通貨を混同しない。
Mouserの商品ページの直接確認・日本配送カートでの確保は未実施。

## U10の基板変更なしの適合確認

TIの通常品SCLS749CとQ1品SCLS874Aを比較した。ともにPW/TSSOP14、0.65mmピッチ、
本体4.4×5mm。機能は4回路・非反転・独立LOW有効OE。
端子は1=1OE、2=1A、3=1Y、4=2OE、5=2A、6=2Y、7=GND、8=3Y、9=3A、
10=3OE、11=4Y、12=4A、13=4OE、14=VCCで一致する。

FのU16・ULINK0・ULINK1はいずれも14番=MCU_3V3、7番=GND。
Q1の3.3V動作・入力5.5V許容と、VCC=0VでのIOFF最大5µAを確認した。
Q1の3.3V/50pFでの最大伝搬遅延は15.1ns。元品の遅延と同一ではない。
同パッドで機能・電源条件に適合する購入候補であり、実機のFM受信・I2S/SPIタイミング合格を意味しない。

- [TI通常品](https://www.ti.com/lit/ds/symlink/sn74lv4t125.pdf)
- [TI Q1品](https://www.ti.com/lit/ds/symlink/sn74lv4t125-q1.pdf) pin p3、推奨条件p5、IOFF p6、遅延p7
- [Mouser日本一覧](https://www.mouser.jp/ja/c/semiconductors/logic-ics/buffers-line-drivers/?m=Texas+Instruments&series=SN74LV4T125)

## U17の同一デバイス注文区分

TI SCES219Wの注文表でDBVRとDBVRE4は同じDBV/SOT23-5、端子配置も一致。
E4はNiPdAu仕上げの注文区分。端子1=A、2=B、3=GND、4=Y、5=VCC。
FのUTXORは5番MCU_3V3で使うORゲートで、部品パッド・ネット変更は不要。

- [TI資料](https://www.ti.com/lit/ds/symlink/sn74lvc1g32.pdf)
- [Mouser円価格一覧](https://www.mouser.jp/ja/c/semiconductors/logic-ics/logic-gates/?m=Texas+Instruments&series=SN74LVC1G32)
- [Mouserの新しい在庫・米ドル価格一覧](https://www.mouser.com/en/c/semiconductors/integrated-circuits-ics/logic-ics/?number+of+output+lines=1+Output&package+%2F+case=SOT-23-5&supply+voltage+-+max=5.5+V)

## U01の包装違いと工場設定品

10-MSOPのブランクGT（チューブ）とGTR（リール/カットテープ）はともに掲載在庫0。
GTRの2026-12-10入荷予告は納期確約として扱わない。A世代は旧品で採用しない。
QFN20のGM/GMRは同じパッドに載らない。

在庫表示のあるB02075-GTはカスタム設定品。DigiKey技術回答では27MHz水晶、
CLK0初期24.576MHz、I2Cアドレス0x6F。B04486-GTは25MHz、アドレス0x62だがMouserでは利用不可表示。
Skyworks FAQも工場設定によりアドレスが変わることを明記している。
現在の25MHz・0x60・起動時クロック無効の前提に対して、包装だけの置換にはしない。
02075を使うなら水晶、CL、初期出力、設定レジスタと起動順序を別途確認する必要がある。

- [Mouser GT/GTR一覧](https://www.mouser.com/en/c/semiconductors/clock-timer-ics/clock-generators-support-products/?package+%2F+case=MSOP-10&series=Si5351)
- [02075商品](https://www.mouser.com/en/ProductDetail/Skyworks-Solutions-Inc/SI5351A-B02075-GT?qs=p9T7GgSe1IHt8ib3k5KY5Q%3D%3D)
- [04486商品](https://www.mouser.com/en/ProductDetail/Skyworks-Solutions-Inc/SI5351A-B04486-GT?qs=IPRQZ7PlV82XwS7Ndxpy4w%3D%3D)
- [Skyworks FAQ](https://www.skyworksinc.com/-/media/SkyWorks/SL/documents/public/application-notes/AN1423_Si5350_Si5351_FAQs.pdf)
- [カスタム品設定の販売店技術回答](https://forum.digikey.com/t/using-multiple-si5351as/30055)

基板変更も許容するという追加指示を受け、欠品待ちを避ける次案を[STOCK-PRIORITY.md](STOCK-PRIORITY.md)に具体化した。
