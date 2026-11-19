# HOST・USB・停止互換の維持条件

この回路版ではfirmwareやHOSTのソースを変更していない。P2で実装・受入済みとする記録ではない。

- protocol-v2のYM22S002、0x42/100kHz、要求最大208byte、状態64byte、32event/PUSH、FIFO1024event、CRC32・sequence・timestamp順、1000ms lease、duplicate非二重実行、SEAL/periodを維持。
- 既存HOSTプレーヤーのWYM1、曲選択/repeat/all/Ctrl+C、opn1/4MHz・FM100%の基準を維持。新操作を必須にしない。実YMへの書込み完了でexecutedを数え、内部SPI送信数で代替しない。
- USB CDC/MIDI1.0・6ch（FM3＋SSG3）のdescriptorと排他/NoteOn/NoteOff/panicを維持。USB-Bは物理コネクタとケーブルだけの変更で、USBモードやデータの形式を変更しない。
- I2C所有中のMIDI NoteOnを後から再演奏しない。MIDI所有中BEGINは拒否。global STOPで全音・queue/PCM・所有権を破棄。
- USB切断でMIDI/USB/LOCAL_EDIT所有者を停止。I2C所有者は外部5Vと有効HOST leaseが続く限り継続。USB再接続/status読取りだけで再開しない。
- panelは0x30の別バスで編集値/状態を送る。HOST/MIDI所有中はstageのみ、ENTER EDIT＋新NOTEで試聴。panel通信だけでHOST leaseを延長しない。LOCAL_EDIT中のpanel喪失は300ms期限で停止し、再接続時NOTE解放→新押下を要求。
- LCD/EEPROM/JSONの仕事を音声DMA補充loopへ持ち込まない。I2C timeout・panel STOP/NOTE解放を優先する。64slot record CRCとOP順序、pickup、JSON形式はeditor Bの仕様を継承する。

base RP2350A用board設定・PIO/DMA割当・flashJEDEC、source Picossci用HAL・時刻/credit/CRC/STOP内部リンク、base ADC＋FM合成、panel MCUのslave/UIが別途必要。既存Rev C UF2を書くだけで使えるとは案内しない。

## 移植後の受入

1. 無USB/無panel/起動/resetで無音、逆給電・温度・レールとADC入力biasを測定。
2. mute中bus、ADC/FM受信、単音/6声、FM/SSG gain・delayを校正。
3. 無変更HOSTで診断191event、YsII123137event全period/CRC/fault0/gates0、I/IIIを再受入。
4. STOP4秒無音、lease失効/read-only再接続無音、明示BEGIN/PLAY、Ctrl+C、長時間待機・repeat/all。
5. USB-MIDI6声/panic、I2C排他、MIDI中USB喪失停止、I2C中USB抜去でも継続。
6. panel連打/全画面更新/SAVE中、panel reset/ケーブル抜去/SDA LOW時、直接STOP。再接続だけでは再発音しない。
7. EEPROMの途中電源断、CRC、64slot、JSON往復・旧epoch/重複/CRC異常を確認。

今回の合格範囲はKiCad ERC、全netlist一致、GPIO/電源/停止配線の静的照合、旧設計の保存ハッシュ。上記の実機合格を代替しない。
