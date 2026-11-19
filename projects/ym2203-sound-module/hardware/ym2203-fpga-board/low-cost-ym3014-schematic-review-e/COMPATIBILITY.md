# HOST・USB-MIDI・停止互換と移植条件

review Cの[既存契約](../low-cost-schematic-review-c/COMPATIBILITY.md)を継承する。今回firmware/HOSTソースは変更しない。ハードウェア移植後の合格とは区別する。

- HOSTは0x42/100kHz/protocol-v2/YM22S002、32events/PUSH、1024FIFO、CRC・連番・1000ms lease・STOP・SEAL/periodを維持。書込み完了を実行件数にし、SPI送出件数で代用しない。
- 既存HOSTのWYM1 opn1/4MHzとplayerの曲選択/repeat/all/Ctrl+Cを維持し、新しいprofileコマンドを既存曲の必須操作にしない。
- 新base HALはsplit-analogを基板設定として選択。ADC L=FM、R=SSG、I2S寄与0。左右には同じ合成音声を出す。ADC/PGAとDC除去・gain/clip・delayを適切に実装する。現在のRev C sample gain式を無校正でunity相当としない。
- source MCU・SPI・承認済み28GPIOは保持。専用DAC使用時はFM capture処理を音声の必須処理にせず、GP27 TX_DISABLE HIGHを保つ。FM receiver配線は診断/将来用として残す。誤ってアナログFMと同じFMをI2Sからも加算しない。
- base ADC・I2S入力・DAC・Si5351A・service0x20/0x30/0x4A/0x60、HOST専用I2Cとpanel専用MCU/保存64slot/JSONを保持。
- USB CDC/MIDI1.0と6ch=FM3+SSG3、I2Cとの排他・panic・global STOPを保持。USB切断でUSB/MIDI/LOCAL_EDITを止め、I2C所有は外部5V＋有効HOST leaseなら継続。status/再接続のみでは再開しない。
- STOPはbase GP23直結のまま。最終mute→queue/ADC/I2S寄与の破棄→source停止を優先し、遅延ACKや再初期化から旧音を再生しない。
- Picossci2B R5/R6のGP24/25 LED負荷切離しとSW1 RESET追加線、base2A RESET J1.18、JEDEC実容量・実機電源/熱確認はCから継続。

将来のYM2608/YM2610は別profile/音源基板/書式・ADPCMメモリ等の拡張対象で、既存opn1の互換を根拠に再生済み・追加費用込みとしない。

## 新実機の受入項目

1. 実DACの品名・16SOPの端子/寸法、RB/MPと5V、アナログ入力のbias/振幅、各Cの温度と起動過渡。電源OFFで挿抜。
2. 最終mute中にFM/SSG・ADCを確認し、ADCのPGA0dBからgain/左右同一合成を校正。I2S寄与0、clippingなし、CRBとcouplingのsettling後に明示発音。
3. 既存HOSTでrecovery191events、YsII123137eventsと全period/CRC/fault0/gates0、YsI/III、repeat/all/Ctrl+C・待機後再生。
4. STOP後4秒無音、lease失効・読取専用再接続でも無音、明示BEGIN/PLAYで先頭から再開。停止時にDACが保持していても出力muteが効くこと。
5. USB-MIDI6声/panic・I2C制御権、MIDI中USB切断停止、I2C中USB抜去継続、USB再接続のみでは無音。
6. panel描画/SAVE/SDA LOW/切断中の直接STOP、LOCAL_EDITのpanel喪失期限。電源再投入・source reset・clock復帰時に再発音しない。
7. 4MHzを基準にFM/SSG balance、低高域、歪み・雑音・click・delayをRev Cと音量を合わせて比較。追加clock設定はCLK/SH/SD実測と両ICの仕様内確認後に受入。

ADCと出力DACを含む新実装は未稼働であり、上記は次工程の受入条件。保存C/D/Rev Cの合格結果を転記しない。
