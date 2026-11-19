# HOST・USB・停止処理の維持条件

本書は設計契約。P2の新firmwareを実装・受入した記録ではない。Rev Cで合格したコード・受入記録・HOSTを保存し、同じ外部挙動を移植先でも試験する。

## 外部ABI

- HOSTは既存[protocol-v2.md](../../../firmware-c/protocol-v2.md)のYM22S002、0x42/100kHz。操作Pico GP0/GP1、base GPIO20/21を維持。
- 最大208バイト要求、64バイト状態、CRC32、32イベント/PUSH、1024イベントFIFO、1000ms lease、再送の非二重実行、SEALとperiod終了の意味を維持。
- WYM1形式・レジスタ順・時刻・既定4MHz・FM100%の基準を維持。任意クロックは停止中の対応profileへ限定し、旧HOSTへ新コマンドを必須化しない。
- USB CDC/MIDI1.0・6チャンネルの既存挙動とdescriptorを継承する方針。新モジュール用board設定・flash領域・P2専用HALは別途実装する。Rev C用UF2を書けば動くと案内しない。
- USB WYM1、LOCAL_EDIT、EEPROM・JSON取出しは以前からのP2実装要件として残す。未実装部分を完成扱いしない。

## 所有権と停止

I2C/MIDI/LOCAL_EDITの単一所有者を維持する。所有中の競合BEGIN・Note Onを拒否/破棄し、後から再生しない。
パネル表示・つまみ操作だけでI2C/MIDIの所有権を奪わず、編集内容はstageし、明示ENTER EDITと新NOTEで試聴する。
既存editor Bの[UI契約](../editor-shield-review-b/UI-FIRMWARE.md)と[保存契約](../editor-shield-review-b/STORAGE.md)を維持する。

global STOPはLCD・EEPROM・SPI転送の完了を待たず、最終DAC/LINEを閉じ、queue取消し・全声停止・世代更新・所有権解放を行う。
FIFO不足、CRC異常、期限超過、lease失効も消音し、read/PING/重複要求でleaseを延長しない。
USB切断でMIDI/USB/LOCAL_EDIT所有者を停止し、I2C所有中は有効なHOST leaseが続く限り再生を維持する。
再接続・read・押されたままのNOTE/STOPだけで自動再発音しない。
モジュールのRUN追加配線、ENABLE既定LOW、出力バッファのdisable、DAC/LINE既定消音を省略しない。

## 移植後の受入

1. 起動/リセット/USB接続なしで無音、各レールと逆給電・LDO温度を確認。
2. HOSTから診断191イベント、YsII全123137イベント・CRC・全period・fault0/gates0を確認。
3. STOP→4秒無音→明示再送、lease→4秒read無音→STOP/BEGIN、Ctrl+C・再接続・repeat/allを確認。
4. USB-MIDI単独6声・和音・panic、I2Cとの制御権切替、MIDI中USB喪失停止、I2C中USB喪失継続を確認。
5. LCD更新・4つまみ読取り・SAVE処理中も音声DMAとSTOP/leaseを処理し、長時間無音待機・全曲繰返しを確認。
6. 64音色slot、OP順序0/8/4/12、pickup、EEPROM page/CRC・途中電源断、JSON再importを確認。

今回行うのはGPIO/端子と保存ファイルハッシュの静的照合、費用・包絡の計算。P2での上記試験はすべて未実施。
