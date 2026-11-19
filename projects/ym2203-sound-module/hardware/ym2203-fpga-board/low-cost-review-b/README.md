# LC-B：3.3V I2C音色編集パネルと小型ベースMCU

2026-11-19。LC-Aから派生する**構成・端子・費用の検討案**。ベースL・音源K・シールドB、購入資料、LC-A、Rev Cの受入記録を保存する。active-plan、回路図、PCB、firmware、HOSTは変更しない。

推奨候補は、ベースを**Picossci 2 RP2350A**、音源をLC-Aと同じ**Picossci 2B**、操作パネルを**Pico RP2040＋CD74HC4051E**とする構成。パネルは3.3V Grove I2Cの4線・150mmで接続する。パネルでLCD描画・つまみ読取り・EEPROM保存を行い、ベースへ編集値や操作イベントを送る。

| 用途 | 選定候補 | 購入商品価格・税込 | 理由 |
| --- | --- | ---: | --- |
| ベース | Picossci 2 RP2350A SSCI-097956 | 1,760円 | 26.67×15.24mm、RP2350を維持、27 GPIO使用＋予備2本、RUN端子が露出 |
| 音源 | Picossci 2B SSCI-105071 | 2,310円（LC-A内数） | 28 GPIO・既存音源側接続を維持。RUN追加線・LED負荷処置はLC-Aの条件を継承 |
| 編集パネル | Pico SC0915 | 800円 | LCD SPI・操作子・独立した2つのI2Cを収容。音声処理は担当しない |
| 4つまみの切替 | TI CD74HC4051E | 199.10円 | 3.3V、現行品、DIP16。Picoの外部ADC3本という制約を回避 |
| 接続 | Grove 110990037×2＋150mmケーブル | 購入260円 | コネクタ10個袋150円＋ケーブル110円。THTで手実装しやすい |

カタログ確認は[購入条件](part-observations.json)。在庫は観測値で確保ではない。音色編集は現行1.54インチ240×240 LCD、4ノブ、encoder、OP1～4、NOTE、STOP、64音色、JSON入出力を維持する。

- [MCU・端子・電源の採用条件](HARDWARE.md)／[端子候補JSON](gpio-proposal.json)
- [I2Cパネル仕様・互換・停止処理](INTERFACE.md)
- [費用比較](COST.md)／[再計算入力](cost-inputs.json)
- [保全対象ハッシュ](source-lock.json)／[静的検証結果](verification.json)

ベース44 GPIOから、パネル直結18本を外して26本へ減らせる。さらにベースSTOPをI2Cから独立したGPIOへ移す提案を含めて**27本**。RP2350Aの30 GPIOのうちGP25のLEDを残すので29本を使え、予備はGP24/29の2本となる。計算上は収まるが余裕が大きい構成ではない。

Pico 2をベースにすれば商品990円へ下げられるが、51×21mmで大きく、外部26 GPIOを使い切る。実装・電源変更枠を含めると推奨案との差は約435円であり、今回は小型・USB-C分離を保ちやすいPicossci 2を優先する。

I2C化による追加削減は数百円規模。MCUを1枚追加するので、LC-Aより大幅には安くならない。利点は40芯から4線への簡素化と、LCD/操作子処理の分離にある。基板各5枚・部品1セット・YM流用の送料枠・予備費込みで**約4.5万円**の予算目安を継続する。新CADで100mmに収まる保証や確定見積ではない。

## 検証

```sh
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-review-b/tools/review.py
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-review-b/tools/review.py --check
```

Python標準ライブラリで、端子重複・GPIO露出/予備数・I2C/SPI mux候補・アドレス衝突・4ノブ切替・通信量・価格算術・保全対象SHAを照合する。KiCad ERC/DRC、RP2350A上のPIO/DMA実行、I2C slave実測、電流・温度・音声・停止時間の実機試験は未実施。GPIO変更はプロジェクトAGENTS.mdの指示に従い、**回路/HALへ適用する前に確認する未適用提案**として残した。
