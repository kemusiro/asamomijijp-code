# Hの制御・停止・互換実装条件

2026-11-18。回路図からfirmwareへ渡す条件。下記はP2実装済みの動作ではない。
既存Rev CのHOSTとC firmwareのソース・過去受入記録はそのまま残す。

## 外部契約

opn1/4MHzに対して既存HOST I2C0 GP20/21、0x42/100kHz、署名YM22S002、
64byte status、PUSH最大32event、FIFO1024event、WYM1 `<IBB`/6byte、1000ms leaseを維持する。
順序・timestamp・CRC・sequence・再試行の意味を変えない。
`executed`はCoreが実YMの書込みを完了した数であり、baseがSPI送信/FIFO格納した数ではない。
Core側の消化停止を成功ACKで隠さず、期限付きでfault→全音停止へ遷移する。

USB CDC/WYM1・MIDI、UNO R3形状/IOREF3.3V、RX/6声LED、clock DIP、RUN/STOP/TESTも維持する。
STOP/TESTボタンはMCP23017の定期poll。独立hardware STOPボタンではない。
RUNボタンはPGA RUNへ直結。resetでGPIOがHi-Zになるとpull-downにより最終mute/ENABLE低となる。
GのGPIO配置は回路へ反映したが、PIO実行・USB descriptors・MIDI応答・UNO shield干渉は未検証。

| 状態と入力 | 必要な結果 |
| --- | --- |
| MIDI所有中のI2C BEGIN | 拒否し、既存MIDI演奏を維持 |
| I2C所有中のMIDI Note On | 不発音、後から再生しない |
| 任意所有者のSTOP | 全音mute・event/PCM破棄・所有権解放 |
| MIDI所有中のUSB切断 | 全音停止・所有権解放 |
| I2C所有中のUSB切断 | 外部5VとHOST leaseが続く限り再生維持 |
| HOST通信断 | leaseで全音停止、queue破棄 |
| USB再接続/status/readback | 消音を維持、新PLAY/Note Onのみ再開 |

UNO A4/A5は内部I2C1（MCP0x20/ADC0x4A/Si5351A0x60）とjumper共用。
jumperを開いてanalogに使う場合、内部clock/ADC依存の演奏は停止状態で無効化する。
汎用5V shield対応、動作中のprofile・clock・バス切替、blind I2C scanは行わない。

## 起動・停止順序

1. 最終DAC/LINE許可=0、MOD_ENABLE=0、data/controlはHi-Zから開始。CLK出力も停止profileで設定。
2. 共通ADC/DACとservice I2Cを設定し、audio clockを開始。起動settlingをmute中に待つ。
3. SPI/parallel/I2Cの手動profileを選ぶ。shared dataは方向とidle値を先に設定してから周辺機能を選ぶ。
4. YMカードはENABLEを上げCore起動。ローカルOE_Nはpull-upでdisabled、RESET_RELEASEはLOW。
   CoreがLINK_TX_DISABLE=HIGHを先に設定し、CS/WR/RD=inactive、A0/data、DIRを準備してU9をenableし、安定clock下でYM resetを保持する。
   reset解除後にprobe/初期化、FM受信を開始しALERT_Nを解放。chip reset幅はYM仕様と波形で確認する。
5. 新PLAY/Note OnでPCMをprimeしてから最終muteを解除。起動・再接続だけでは演奏しない。
6. STOP/lease/faultでは、busの応答を待たず最終許可を下げ、世代tokenを無効化しwriterを取り消す。
   event/PCMをflushし出力をzeroへ。audio clockは継続、mute開始から4ms以上後にENABLE低/reset・clock変更へ進む。
   cleanupを待ってmuteする順序にしない。遅れて届いたSPI完了/PCM/USB Noteを再適用しない。

ENABLE低は音源のSN74LVC1G07からCore RUNをLOWへ引く。
Core GPIOがHi-ZになるとU9 OE_NがHIGH、出力がHi-ZになりYM RESET_Nの10k pull-downでresetを保持する。
YM clockもU9経由なので停止する。次回release前には必ずclockを復帰しreset時間を確保する。
RUNはopen-drainで、Core onboard resetやSWDとpush-pull競合しない。
これは独立したwatchdogではなく、MCU hang・低電圧のすべての状態でresetを保証する回路ではない。

## 内部linkと次の実装

YM用SPIはbase GP0=MISO/GP1=CS/GP2=SCK/GP3=MOSI、Core GP8=RX/9=SS/10=SCK/11=TX。
ULINK1のMISO OE_Nは`CS_N OR LINK_TX_DISABLE`。GPIO27のLINK_TX_DISABLEは10k pull-upで、
Coreが初期化するまでMISO/I2S両出力をHi-Zにする。READY/新sessionを確認してからLOWへし、
STOP/reset前にHIGHへ戻す。未選択時もMISOを解放する。
48kHz/64BCK/24bit-in-32標準I2Sはbase master。Core GP24=data、25=BCK、26=LRCK。
base TX14、BCK15、LRCK16、ADC RX17、source RX18。非同期source-masterは非対応。

session token、event timestamp、credit、CRC、実chip-write完了、STOP取消し、audio-ready/faultを
内部linkで明示的に扱う必要がある。パケット形式・Core/base firmwareは未実装。
GPIOと外部ABIが合うだけで既存HOSTをこの回路に直結して使えるとは判定しない。
PIO0 OUT8 base0/SET4 base8。OUT12でGPIO12 ENABLEを巻き込まない。
PIO1はTX＋2RX候補、命令数・同期・DMA・SRC負荷は実装時に検証する。

次の受入は電源/機構/PCB確認後、まずmute中のbus/ADC/FM受信、次に単音・6声・gain/delay校正、
既存HOSTのYs II全曲、STOP/lease/再開、USB-MIDI/I2C所有権とUSB切断、長時間待機の順とする。
今回のERC・端子検査・既存ソフト試験は、この実機受入を代替しない。
