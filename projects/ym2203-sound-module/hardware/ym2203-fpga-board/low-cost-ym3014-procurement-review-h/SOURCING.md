# 在庫確認3行と代替候補

2026-11-19。取得できた販売店の直接商品ページ・公式一覧・商品検索収録を使用する。直接ページの在庫0は、同じSKUの検索結果に残った在庫ありより優先する。価格/在庫を保証する購入予約は行っていない。

## C_1u：3個

GのTDK C2012X7R1H105K125ABは、検索には6,826個とある一方、直接商品ページは在庫0で、調達確実とは扱わない。秋月115331も販売終了/入荷未定表示のため採用しない。

今回の購入候補は**Würth 885012207103R**。DigiKeyの商品検索収録に在庫5,031個、CT1個31円税別、3個102.30円税込を確認。

| 確認項目 | 元のTDK | 採用候補Würth |
| --- | --- | --- |
| 容量/許容差 | 1µF ±10% | 1µF ±10% |
| 耐圧/温度特性 | 50V / X7R | 50V / X7R |
| 長さ×幅 | 2.0×1.25mm | 2.0±0.2×1.25±0.2mm |
| 最大高さ | 1.45mm | 1.25±0.2mm、最大1.45mm |
| 極性/ランド | 無極性 / 0805 | 無極性 / 0805 |

ベースC30・CADCVREF、パネルC1の3個に適用する。Fの標準0805ランドを使い、部品高さを元の最大値より増やさない。回路/ネット/GPIO/実装座標は変更しない。Gの文章にあった「高さ1.25mm以内」は元MPNの公称値と最大値を混同した条件だったため、本追補ではメーカー公差を含む最大1.45mmで比較した。これはF PCBの変更ではない。

予備候補はKYOCERA AVX **08055C105KAT4A**（1µF/50V/X7R/±10%/0805、DigiKey掲載在庫96,098、税込78.10円/個）。主候補を確保できない場合は、最新メーカー外形/高さを照合してから使用する。今回は購入表へ加算しない。

一次資料：

- [Würth メーカー資料](https://www.we-online.com/components/products/datasheet/885012207103R.pdf) p.1：寸法、1µF/50V/±10%/X7R。
- [TDK 元MPN](https://product.tdk.com/ja/search/capacitor/ceramic/mlcc/info?part_no=C2012X7R1H105K125AB)
- [採用候補のDigiKey商品](https://www.digikey.jp/ja/products/detail/w%C3%BCrth-elektronik/885012207103R/21719367)
- [予備候補のDigiKey商品](https://www.digikey.jp/ja/products/detail/kyocera-avx/08055C105KAT4A/9749270)

## C_2.2u：2個

秋月[114788](https://akizukidenshi.com/catalog/g/g114788/)の直接ページで、**GRM21BR71E225KE11、10個入り100円、通販購入可能数2パック、在庫僅少**を確認した。1パックで必要2個を賄い8個余る。ページの「7月下旬入荷予定」は確認日との整合が取れないため、今後の納期見込みとして転記しない。

売切時はDigiKeyの**GRM21BR71E225KE11L**が候補。末尾Lは包装指定で、2.2µF/25V/X7R/±10%/2012を維持する。同店の商品掲載在庫789,037、CT1個29円税別、2個63.80円税込。同梱額が送料無料条件を満たすため、この2個のための新規送料は不要。秋月優先で主表は1パック100円を維持し、予備候補を重複計上しない。

- [DigiKey 同一系列・包装違い](https://www.digikey.jp/ja/products/detail/murata-electronics/GRM21BR71E225KE11L/6606096)

## U07 / UAUX：1個

TI **TLV1117LV33DCYR**はDigiKeyの直接商品ページで在庫0だった。検索の59,720個は現物確保の根拠にしない。今回は同型番を**MouserでCT1個**調達する候補へ変更する。商品/シリーズ掲載に1,450個、1個54.8円税別の表示を確認し、10%税込60.28円を計上した。別の一覧には43.2円の表示もあり、高い54.8円側を予算へ採用した。

Mouserの商品ページ/カートの再取得にはアクセス制限があり、掲載在庫・単価・CT1個の購入条件を発注時に再照合する必要がある。検索結果の古いDCYT包装や別電圧品を注文せず、**メーカー型番TLV1117LV33DCYR・3.3V・SOT-223・CT1個**を確認する。

同型番を維持するので、GND=1、OUT=2/タブ、IN=3、入力5V・出力3.3V・1A・セラミック出力コンデンサー対応を保持する。FのUAUX、CAUXIN/CAUXOUT、放熱ゾーンを変更しない。負荷予算440mAと実装後の温度確認条件もFを継承する。

代替ICの評価結果：

- **TLV1117LV33DCYR.A / .B**：TIは元品と同一と案内しているため将来の調達候補。ただし今回この枝番のCT在庫/価格を確保できておらず主表へ採用しない。
- **NCP1117LPST33T3G**：3.3V/1A/SOT-223で在庫候補はあるが、メーカーは出力容量4.7µF以上・ESR20mΩ〜20Ωを要求する。Fの既存MLCCでESR下限を保証できないため、無変更での代替には採用しない。
- **AP7361C-33ER-13**：SOT-223Rは互換のピン配置だが掲載在庫0。末尾Eの通常SOT-223版はピン配列が異なるため代用しない。
- 秋月の一般的な1117系を、型名だけで置き換える案は未採用。

一次資料：

- [Mouser 同型番](https://www.mouser.jp/en/ProductDetail/Texas-Instruments/TLV1117LV33DCYR?qs=sGAEpiMZZMug9GoBKXZ754ENSUSpJrT1oXgLIl6RErY%3D) / [公式シリーズ一覧](https://www.mouser.jp/ja/c/power/power-management-ics/?series=TLV1117LV)
- [TI メーカー資料](https://www.ti.com/lit/ds/symlink/tlv1117lv.pdf) / [TI 同一型番案内](https://www.ti.com/product/ja-jp/TLV1117LV/part-details/TLV1117LV33DCYR)
- [onsemi NCP1117LP](https://www.onsemi.com/download/data-sheet/pdf/ncp1117lp-d.pdf)
- [Diodes AP7361C](https://www.diodes.com/datasheet/download/AP7361C.pdf)

この部品だけ別送になる。Mouserは6,000円超の多くの注文を送料無料と案内しているが、今回は60.28円なので適用しない。少額送料を確定取得できなかったため、0円や他社の2,000円規定を流用せず、**送料/税差の枠2,500円**を計上する。確定した送料ではない。
