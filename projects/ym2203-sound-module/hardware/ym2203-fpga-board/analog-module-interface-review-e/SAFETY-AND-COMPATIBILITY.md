# review E 停止・所有権・既存HOSTとの境界

本書は未実装の契約。Rev C firmware/実機受入、D回路図/PCBは変更しない。

## STOPの順序

1. 外部/内部I2CやSPIの完了を待たず、ベースの最終DAC/LINE出力ゲートを閉じる。
2. 世代番号を更新し、event FIFO・PCM FIFO・未完了write/ready待ちを無効化する。
3. MOD_ENABLEをLへ戻し、機種別のkey-off/mute/reset/INHIBITを有限時間で行う。
4. 各経路の古いPCM/ADC filter履歴を排出。読み取り/USB再接続では解除せず、新PLAY/Note Onのみで
   初期化→clock/ADC lock確認→無音prime後に開く。共通ADC/clockの通常STOPでの電源断は行わない。

1が先なので、カードがSDAをLに固着させても全音停止はバス応答に依存しない。
取引timeoutは5msを候補とし、音声変換のdeadlineに合わせて最終確定する。
長いready待ち（発声/選局）をblocking取引にせず、期限付き状態機械で扱う。
再開には必要な全経路の復旧を要求し、壊れたADCを片側だけ鳴らしたまま継続しない。

MOD_ENABLEは共通の許可信号で、全ICに同名のresetがあるという契約ではない。
SN76477はINHIBIT反転、SN76489は書込み停止＋音量初期化など、局所適合を音源基板で行う。
ATP3012のsleepは発声中直ちに効くとは限らず、cancelまたはresetを使う。
ラジオは音声が常時存在しても所有権/リースを延長しない。

保持する最低限の回路は、3.3V I/O条件、ICが必要とする電圧変換・decoupling、
MOD_ENABLE/default gateのpull抵抗、RUN reset、既存の最終muteと電源入口の基本対策。
独立watchdog/監視IC、二重停止ラッチ、電源絶縁、追加MCU、hot-plug回路、I2C mux、カードEEPROMは必須にしない。
CPU完全停止を独立に検出する保証はない。RUN resetは残すが、外付けwatchdogと同等の保証とはしない。
不用意な電源逆流対策の積増しを避けるため、別電源/活線挿抜を初期使用条件から外す。
アナログ入力のAC結合・レベル合わせ・未通電時定格確認は信号経路の成立に必要な範囲で残す。

## 所有権の契約

| 状況 | 必須挙動 |
| --- | --- |
| MIDI所有中にHOST BEGIN | 拒否。演奏中MIDIは保持 |
| HOST I2C所有中にMIDI | 破棄。後で再演奏しない |
| いずれか所有中にSTOP/panic/STOPボタン | 全音源/全返送経路を停止・所有解除 |
| MIDI所有中にUSB切断 | 停止、再列挙だけでは復帰しない |
| I2C所有中にUSB切断 | 外部5VとHOSTの有効リースがあれば続行 |
| HOST通信断 | opn1は既存1000ms lease後に全音停止、残event取消し |
| status読取り/USB再接続 | 無音を維持。leaseを更新しない |
| 再PLAY/Note On | 明示要求でのみ再初期化/primeして発音 |

UNOシールドが内部service busを妨害しても、HOST用I2C0と最終muteのGPIOは共有しない。
clock DIP/profile変更は全音停止中のみ。clock不成立、未知profile、入力経路欠落は発音禁止。
RX LEDは有効な受信、6声LEDはYM実書込み由来の状態を維持。他機種の発音割当は別途定義し、
未対応profileをYM6声と偽って表示しない。ハードRUN、STOP/試聴、USB CDC/MIDI、UNO配置を維持する。

## wire互換はopn1・4MHzから

既存HOST player/libは変更しない。opn1はWYM1 `<IBB`6byte、YM22S002、status64byte、
PUSH32event、FIFO1024、lease1000ms、timestamp/CRC/sequence/STOPとackの意味を維持する。
音源SPIへのenqueue完了をYM書込み完了と数えず、実chip書込み後にexecutedを進める。
署名だけの互換ではなく、HOST側のSTOP/lease/replayとUSB所有権切替の回帰を必要とする。

PSG/発声/ラジオ/SN76477はYMレジスタ列を解釈できないため、YM22S002を名乗らせない。
機種選択/文字列/選局/presetの公開packetとMIDI mappingは別実装で、現時点のversion/formatは未割当て。
物理共通化と、全音源が既存Ys IIデータを再生できることを混同しない。

## 実装後の受入項目

- 電源ON/不明profile/リセット中の無音、音声LR・mono複製、入力最大振幅/clip/負荷、I2S lock。
- 既存HOST診断191eventとYs II 123137eventの全件・CRC・正常終了・再演奏。
- 途中STOP、1000ms lease、4秒無音、read-only再接続、明示再PLAYのみの復帰。
- USB-MIDI6声、I2C排他、USB切断I2C続行、USB再接続時無音。
- ADC/I2S欠落や内部bus timeout時に最終muteが先に閉じ、古いデータが再出力されないこと。
- FM/SSG遅延・音量の校正、48kHz連続負荷、UNOシールド併用、clock切替後のprime。

以上は受入計画であり、review Eの試験済み結果ではない。
