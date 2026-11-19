# パネルI2Cの提案契約・外部互換・停止

**未実装の設計契約**。今回のGPIO提案はCAD/HALへ未適用で、既存HOSTやUSB firmwareを変更していない。Rev C実機受入をP2へ転記しない。

## バス分離

- 操作Pico→base: 従来I2C0 slave GP20/21、0x42、100kHz、YM22S002、protocol v2を保持。208byte要求、64byte状態、32event PUSH、1024event FIFO、WYM1時刻/順序/CRC32、1000ms lease、duplicateの非二重実行、SEAL/periodを維持。
- base→panel: service I2C1 master GP26/27、panel I2C0 slave GP0/1、アドレス0x30、100kHz。MCP0x20、ADC0x4A、Si5351A0x60と衝突しない。HOSTバスへパネルをつながない。
- panel→24FC256: panel I2C1 master GP2/3、0x50。uplinkとは独立し、EEPROM write-cycleでuplinkをclock-stretchしない。

## 転送する情報

uplinkは32byte以下の固定長status/操作ブロックを20msごとにpollする案。100kHzで32byte+address/registerを9bit/byteで見積もると306bit/20ms、約15.3%の占有（START/STOP等を除く）。patch更新も32byte以下へ分割し、通常時は1pollあたり1writeを上限とする。EEPROM/描画/USB転送完了待ちは禁止。上限5msのI2C転送とtimeout・回復処理を音声loop外で行う実装が必要。音声DMA補充・PCM変換は別coreで継続し、STOP GPIOの消音処理はI2C転送lockを取得しない経路にする。通常poll20msと5ms timeoutは独立hardware停止時間を保証する数字ではなく、最終応答時間を実測する。

version、kind、boot/session epoch、sequence、payload length、CRCを持たせる。version/CRC/length不一致と古いepochを適用しない。操作はknob値・button状態・encoder差分・patch変更・ENTER EDIT/NOTE/STOP/保存要求で、LCD画素や音声PCMはuplinkへ流さない。再送は同じsequenceなら二重発音・二重SAVEをしない。32byteに入るwire配置とCRC方式はfirmware着手時に確定し、現在のHOST v2形式には混ぜない。

STOPとNOTE解放はキュー最後尾へ追加する方式にせず、次のstatusに残るsticky flag/現在のheld状態として優先し、baseのACKで消す。encoder/knobは古い差分を間引けてもSTOP/NoteOffを欠落させない。USB CDC JSONの搬出入は停止中にchunk転送し、既存editor Bのrecord・OP順序0/8/4/12・slot CRC・JSON schemaを保持する。

## 単一所有者と障害時

既存I2C/MIDIの排他、CDC/USB WYM1の所有権要件を保ち、LOCAL_EDITを同じarbiterへ接続する。ノブ操作やpanel読取りでHOST/MIDIの所有権を奪わない。所有中は編集stageのみ、ENTER EDIT＋新NOTEで試聴。panelは独立MIDI USBデバイスとして音源制御を追加しない。

| 入力/障害 | 必要な結果 |
| --- | --- |
| ベースSTOP GPIO | service I2CがSDA LOWでもDAC/LINE/ENABLEを閉じ、session無効化・queue取消し・所有権解放 |
| panel STOP | 受信した時点でglobal STOP。I2C依存なので独立hardware STOPとは称さない |
| LOCAL_EDIT中panel喪失 | 有効status/ACKの300ms期限で全音停止、held noteと世代破棄 |
| HOST演奏中panel喪失 | HOST leaseとaudioが正常なら演奏継続、編集リンクだけofflineへ |
| MIDI/USB/LOCAL_EDIT所有中USB喪失 | LC-Aの契約どおり全音停止・所有権解放。panel給電だけで自動再開しない |
| HOST所有中USB喪失 | 外部5VとHOST leaseが有効ならI2C演奏継続 |
| HOST lease失効/CRC/fault | 既存どおり全音停止・FIFO取消し。panel pollではHOST leaseを延長しない |
| panel再接続・MCU再起動 | 無音/未所有から開始。押されたままNOTEや古いイベントで自動再開しない |

読み取りだけでLOCAL_EDIT試聴の有効性を無条件に延長しない。panelのboot epoch、単調なscan counter、baseへの最新ACKでpanel loopが進行していることを確認し、停止したstatusの反復では300msを更新しない。panel MCU hangのclock stretchにも5ms期限で抜ける。300msはローカルリンク用提案で、HOSTの1000msを変更しない。

旧HはベースSTOP/TESTもMCP23017 pollだった。外付けpanelをserviceへ増やす案では、ベースSTOPを1本の直結GPIOへ移すのが最小の追加対策。独立watchdogや電源監視を新設する意味ではなく、CPU hang時の保証はない。hard RESETはRUNへ直結し、reset/Hi-Z時にDAC/LINE/ENABLEが既定LOWとなる回路は残す。cleanupのI2C/SPI完了を待ってからmuteする順序にしない。

## 実装後の受入

1. 起動・無USB・再接続・panelなしで無音、外部5V/USB/3.3Vの逆給電と熱を確認。
2. 既存HOST無変更で診断191eventとYsII123137event全period・CRC・fault0/gates0、repeat/all/Ctrl+C、STOP4秒無音、lease/read-only再接続/明示再開。
3. USB-MIDI6声・panic、I2C排他、USB抜去中I2C継続、MIDI抜去停止。新GPIOで音声DMAとPIOを検証。
4. LCD最大更新、全ノブ/encoder連打、SAVE/JSON中にSTOP/lease。音声無停止、出力ゲートの停止実時間を測定。
5. LOCAL_EDIT中panelケーブル抜去・panel停止・SDA/SCL固定LOW、baseSTOP直結で消音、再接続時NOTE release→新押下まで無音。
6. 64slot保存・途中電源断・CRC・JSON往復・duplicate/旧epoch/CRC異常・操作飽和時のSTOPとNOTE解放。

この文書だけで以上の試験が合格したとはしない。既存コードとCADをSHAで保全しており、P2新構成の実装・受入は別工程。
