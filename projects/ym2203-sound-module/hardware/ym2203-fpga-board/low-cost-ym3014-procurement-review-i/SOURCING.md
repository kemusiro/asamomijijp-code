# Mouser43行の調達確認

確認日2026-11-19。秋月・スイッチサイエンスの既存購入43行はHから保持し、残る海外調達43行をMouserへ集約した。全86行・277参照番号を維持する。数量と元通貨の価格・最低発注数・発注倍数・価格/在庫/販売単位の出典は[mouser-43.csv](mouser-43.csv)、機械読取用の観測値は[price-observations.json](price-observations.json)を参照。

## 在庫表示の扱い

40行で1セットに必要な数量以上の公開在庫表示を確認した。残る3行は以下の通り。公開ページの取得日と、検索に収録された時期を区別する。直接取得でもページ側のキャッシュがあり、実在庫の引当や納期確約ではない。在庫がある別品番の数量を、欠品している元品番へ転記しない。

| ID | 維持する購入型番 | 必要数 | 採用した在庫 | 判断 |
| --- | --- | ---: | ---: | --- |
| U01 | SI5351A-B-GTR | 1 | 0 | GTRの掲載在庫0。GTも直接取得ページで0。過去のGT在庫あり検索表示を不採用 |
| U10 | SN74LV4T125PWR | 3 | 0 | 3週前の収録0を採用。古い別URLの350/189在庫表示を即納根拠にしない |
| U17 | SN74LVC1G32DBVR | 1 | 0 | 商品ページ収録0を採用。DBVRE4等の別品番や古い一覧の在庫を転記しない |

3品とも公開ページでは取り寄せ注文の対象だが、表示された入荷予定日を納期保証にしない。GT/GTRの切替、U10の別グレード、U17の別包装については、在庫と元メーカーの適合性を確認してから購入表を改訂する。この版の注文CSVへ未確認の代替を混ぜていない。Mouserへの調達先一本化と「今すぐ全品を揃えられる」は別の状態である。

- [Si5351A GTR](https://www.mouser.jp/en/ProductDetail/Skyworks-Solutions-Inc/SI5351A-B-GTR?qs=p9T7GgSe1IEYql%252BRMAlVcw%3D%3D)
- [GTの直接商品ページ](https://www.mouser.jp/ProductDetail/Skyworks-Solutions-Inc/SI5351A-B-GT?qs=p9T7GgSe1IEO%252BMfC%2FKPFfA%3D%3D)
- [SN74LV4T125PWR](https://www.mouser.com/en/ProductDetail/Texas-Instruments/SN74LV4T125PWR?qs=%2Fd%252bFzHvH4c3%252biZGZ%252bu8B9g%3D%3D)
- [SN74LVC1G32DBVR](https://www.mouser.com/en/ProductDetail/Texas-Instruments/SN74LVC1G32DBVR?qs=3pnr37ZAbK%2F6ArGi%2FPb2Ng%3D%3D)

## 基板を変えない購入品の変更

抵抗1.33kΩだけ、RC0805FR-071K33LからAC0805FR-071K33Lへ変更した。Mouserの日本向け掲載で在庫18,063、最低1個・1個倍数、1個16.6円/10個帯3.7円（税別）を確認。必要3個に対し10個購入・消費税見込み込み40.70円とした。

採用品はYAGEO、厚膜1.33kΩ±1%、125mW、±100ppm/℃、0805/2012、2.0×1.25mm、厚さ公称0.5mm、150Vで、元のR_0805ランドへ実装する。車載グレードの追加によって抵抗値・許容差・定格を下げない。実装試験の合格を意味するものではなく、カタログ仕様の静的照合。CADの部品値は1.33kのままなので回路図/PCBの編集は不要。

[採用品の仕様・価格・在庫](https://www.mouser.jp/en/ProductDetail/YAGEO/AC0805FR-071K33L?qs=sGAEpiMZZMtG0KNrPCHnjb7pwTm6OtIuUdkTBvJm96Y%3D)

その他42行はHの同一メーカー型番を維持した。Si5351AはGTRのまま、TSSOP/SSOP/SOTの末尾違いを無断で小型パッケージへ変更していない。M3/M2の12mmスペーサー、LCD支持部の対辺4mmも維持した。

## 販売単位と価格の制約

- 43行とも最低1個・1個倍数を確認。工場包装数と小口販売数は異なる。CT/少量チューブ/バルクを指定し、MouseReel料金を加算しない。
- 日本円掲載価格を優先。USD/EUR掲載の行は元単価を残し、JPYの確定カート価格と区別した予算換算にする。[費用前提](COST.md)を参照。
- R_2.2kとC_10nは同一MPNの別地域Mouserページで在庫・販売単位と価格を別々に確認し、両方のURLを記録した。R_33/R_6.8kは最低数欄の取得を別の同一MPN掲載で補完した。
- U08/U11は直接取得の在庫・価格を優先し、古い欠品表示を置換した。U07も直接取得の61.5円税別・在庫140,743へ更新した。
- C_22uのTDK品はHのNRND注意を継承する。今回1個分の掲載在庫はあるが、将来の長期供給保証ではない。
- 秋月C_2.2uの僅少在庫はHの注意を継承し、今回43行の新しい確認結果とはしない。

## 互換性

FのベースADC・I2S入力・DAC、音源YM3014B-F、G40、電源・停止回路を保存した。既存HOSTのI2C v2 0x42/100kHz、USB-MIDI、STOP/リース処理を変更する作業ではない。購入先の変更を、P2専用firmware完成・実機動作確認と解釈しない。
