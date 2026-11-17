# 内部SPI・二MCUの時刻と安全停止

2026-11-16。[レビューB](README.md)の設計要件。新firmware・通信試験を行った記録ではない。
公開I2C v2と、base⇔音源Core2350B0の内部SPI層を分ける。

## 外部互換とFIFO

- YM2203×1・4MHz/WYM1の既存HOSTプレーヤーは変更しない。0x42/100kHz、signature `YM22S002`、
  status64、PUSH32イベント、FIFO1024、lease1000ms、CRC/sequence/各errorの意味を保つ。
- 内部SPIはmode0・初期4MHz・最大32イベントbatchを候補にする。内部version/session・CRC・要求sequence・イベントindexを持つ。
  受信確認、FIFO受理、YM書込み完了を別にする。具体的なpacket byte配置はまだ実装/確定していない。
- 公開`executed`は**実YMへの書込み完了**で更新する。moduleのSPI ACKやFIFOへの格納を実行済みとして数えない。
  リトライで同じregisterを二重実行しない。slotを解放する前にmoduleの完了indexを確認する。
- baseが受理した未完了イベントはmoduleへ転送済みのものも含めて1024枠へ数える。module内256枠はこの内数。
  statusの`queued`をbaseに残った件数だけへ変えてはならない。SEQ/CRC・SEAL終端と曲periodもbaseで正本を持つ。
- module ID/capabilityはMCU flashからSPI返信し、種別・内部wire版・audio format・clock範囲・消費枠を検証する。
  未知moduleや電力枠超過はgateを開けない。旧EEPROMのraw-audio format番号で認可しない。

baseは先読み転送し、音源MCU core0が時刻実行・BUSYを処理する。
`PLAY`のorigin、順序indexとtimestampをmoduleへ渡すが、二つのMCUの `time_us_64()` を同じ時刻とは見なさない。
共通LRCK frame counterとSPI同期往復のoffset範囲を照合する設計とし、起動同期誤差の目標は1frame以内。
この同期は未実装。まずlogic analyzerでoffset/最大lateを測り、範囲外ならPLAY拒否・無音にする。
baseが「期限になってから転送」するだけの方式では、SPI待ち/割込のたびに遅れを追加するため比較対象に留める。

転送予算の例は16byte/event・header/CRC32byte、32件で544byte/4MHz=1088µs、1件平均34µs（線上時間だけ）。
module実書込みサービスの暫定目標は100µs以内、17同一msイベントで1.7ms、起動93件で9.3msの算術。
Ys IIの平均約413件/sだけでなく、最大sliding1s569件と同時刻burst、USB/ADC/DMA競合を実測する。
C版Rev Cの実機合格はこのSPI層や二MCU同期の合格ではない。

## clockと遅延

baseをI2S clock masterにし、ADC/両MCU/DACが同じBCK/LRCKを使う。MCUのCPU clockやYM clockは別。
可変YMclockはSTOP中にprofileの許容範囲で設定し、moduleがdecoder/SRCを再設定する。
ADC PLL、電源flags、無音sample、DMA充填、frame同期が揃うまでbase DAC/LINEは閉じる。
SRC固定比125/108を異なるYMclockへ使わない。FM/SSGの枝間遅延も測定・補正する。
I2S形式一致だけでは、ADC filterのgroup delayやbase転送bufferの遅延まで一致しない。
clock停止・FIFO over/underflow・SPI CRC異常・module resetでは、音量を上げて隠さず無音状態へ移す。

## STOPをSPI応答に依存させない

`MOD_ENABLE`はHで起動許可、module側10kΩでdefault L。独立線でmoduleのRUNを低くし、YM reset clampにも直接効かせる。
module側電源のIoff Schmitt receiverを通し、RUNはGPIOから覆せない。ADC用TLV755のENも同じ条件で落とし、reset pinのないADCをpowercycleする。YMのreset解除には外部ENABLEとlocal解除の両方を要求する。
baseのreset中/無電源時もENABLE入力が浮いて起動許可にならないようにする。

STOP、lease満了、owner変更、audio fault時の順序：

1. baseのDAC XSMTと左右LINE gateを直ちに閉じる。最終gateはmodule MCUの応答なしで閉じる。
2. MODULE_ENABLEをLにし、module RUN/YM resetをassert。module SPI/DMA/FIFO/audio bufferを破棄する。
3. baseもevent FIFO、SPI in-flight完了待ち、I2S RX/TX遅延bufferを無効にし、session generationを更新する。
4. 古いsessionの遅延ACKやDMA完了は破棄。音源側resetで完了indexが0になっても、旧曲のexecutedへ加算しない。
5. 最終出力を閉じたままmoduleを起動し直すことは可能。ID/ADC/clock/無音bufferを再確認し、明示的新sessionだけをARMする。

毎回module MCUをresetするため、非volatileなcapability以外の曲/音符/bufferは保持しない。
既存HOSTのBEGIN準備timeout内にquiet-readyへ戻れるか測り、必要ならSTOP後に無音で先行初期化する。
BEGINを勝手に成功扱いしたり、既存HOSTへ非公開待ち命令を要求したりしない。
正常終了もperiod末と最後のaudio tail policyを区別し、明示終了後に古い音が出ないようgateとbufferを処理する。

base MCUの内部watchdog、module MCUの内部watchdogと独立した短い内部session timeoutを使う。
内部timeout候補100ms、内部keepは最大25ms周期で更新し、module自身もYM reset/音声ゼロ化を行う。
**内部keepやstatus読取りは、外部HOSTの1000ms leaseを延長しない。**
prototype要件として独立外付けwatchdog/電源監視ICは必須追加しない。二MCU同時停止の製品保証を宣言しない。
実測停止時間、DACのmute ramp、遅延buffer末尾・clock復帰clickを回帰する。

## 制御権・USB・表示

USB CDC/MIDIの終端はbase。MIDI所有中BEGINは拒否、I2C所有中MIDIはconsume/rejectし、再生予約として残さない。
グローバルSTOP/panicは全音と両gateを止める。切替後は新Note On/PLAYだけで発音する。
I2C所有中のUSB切断はI2Cと外部5Vが生きていれば演奏継続、MIDI所有中の切断はpanic。
USB再接続・status読取り・moduleのready通知だけで所有権/音符を復元しない。
UNOのSPI1は内部SPI0と分離し、HOST I2C0とservice I2C1/UNO A4/A5の既存境界も保つ。
RX LEDは検証済み外部データ受信、6声LEDは実行済みYM状態を基準に更新する。
音声mix後の波形で休符/発音を推定してLEDを点ける実装には変えない。

## 新実機で再確認する項目

1. 無音起動/長期待機、ADC/MCUの片側rail off・clock未供給、ID不一致とprofile拒否。
2. 既存HOST無変更のrecovery.bin、Ys II全曲、選曲・repeat/全曲loop、Ctrl+C。
3. FM/SSG比・6声加算・発音開始の揃い・clipping・左右独立性・遅延。
4. STOP/通信断lease/panic/module reset中も最終gate閉、4秒読取りで無音、明示再開だけで先頭演奏。
5. MIDI/I2Cの相互排他、USB切断時MIDI停止・I2C継続、再接続無音。
6. 電流/電圧/温度、sharedclockの波形、PIO/DMA負荷と最大late、frame slip、USB/I2C連続処理。

これらは未実行であり、この文書や静的検査をHOST PASS・SAFE・実機受入に読み替えない。
