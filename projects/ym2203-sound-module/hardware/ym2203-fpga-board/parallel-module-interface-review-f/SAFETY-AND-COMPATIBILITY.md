# review F：モード選択・安全停止・HOST互換

[E停止契約](../analog-module-interface-review-e/SAFETY-AND-COMPATIBILITY.md)を継承し、以下を追加する。
機械可読仕様は[architecture.json](architecture.json)。実装や新しい実機受入ではない。

## モード切替

1. 所有者なし/停止状態だけで切替を許可する。演奏中やFIFO予約中は拒否する。
2. 最終gateを閉じMOD_ENABLEをL、世代更新・event/PCM FIFOを破棄する。
3. SPIとbus writerを止め、共用dataとauxをHi-Zにする。
4. 手動profileの電圧、接続カード、clock、I2C address、使用方向を確認する。
5. profile固有のinactive control値を先に用意し、GPIO function/directionを設定する。
6. 消音状態でchip/ADC/I2Sを初期化。新PLAY/Note Onまで発音しない。

pin8（SPI MISO）はparallelではD0となり、base出力になる。
SPIカードをparallelで動かすと出力同士が衝突し得るため、modeを自動推測しない。
32pin旧カードの部分挿しも禁止する。EEPROM等を必須化せず、電源OFF交換と手動profile照合で扱う。
未確定/不明profileはgate閉、共用data/aux Hi-Z。SPIとparallel同時駆動は禁止。
I2C0 HOSTは別線、内部I2C1はADC/clock等に引き続き必要。全内部busを一緒に止める切替にはしない。

## 停止

STOP/lease/USB-MIDI切断/STOPボタンは、READYやSPI/I2C応答を待つ前に最終gateを閉じる。
次に世代を無効化し、strobeをinactive、dataをHi-Zへ戻す。音源にRESETがあれば許可信号で停止し、
無ければ期限付き消音書込みを試みる。cleanup失敗でもgate閉を維持する。
data/PCM・未完了bus処理を残したままread-only再接続で再開しない。
電源監視・独立watchdog・二重停止ラッチ等は試作の必須条件にしない。CPU hangを独立検出する保証はない。

## 外部API

opn1・4MHzは既存SPI/Core経路とWYM1 v2を維持する。
YM22S002、6byte event、64byte status、PUSH32、FIFO1024、lease1000ms、CRC/sequenceとSTOPを保持。
executedは実YM書込みの完了で進める。GPIO並列化を理由にenqueue数へ意味を変えない。
SPI/parallel/I2Cのcard内方式を既存HOST playerへ露出させない。

直接AY/SNカードはYMレジスタ列を解釈できず、YM22S002を名乗らせない。
PSG別driver・曲形式・MIDI channel mappingは未実装で、既存HOSTでそのままPSG楽曲を再生できるという意味ではない。
汎用bus書込み公開コマンドを今回追加しない。

MIDI中BEGIN拒否、I2C中MIDI破棄、USB-MIDI切断時停止、外部給電下I2C所有中USB切断での継続、
status/再接続だけでは再演奏しないという所有権契約は維持する。
UNO、clock DIP、RUN、STOP/試聴、RX/6声LEDも維持する。新音源の発音表示は別profileの定義が必要。

実装後はEの受入項目に、模式誤選択の拒否、Hi-Z/方向切替、AY pulse上限、SN READY timeout、
全256byteの物理bit順、parallel負荷中の音声連続性とUSB/HOST排他を加える。
