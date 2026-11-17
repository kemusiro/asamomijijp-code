# F1 USB CDC・USB-MIDI RTL

2026-11-15。`revc_usb_ym_top`へUSB Full-Speedを接続した。実YM2203C、
Si5351A、独立48 MHz制御clock、49.152 MHz音声clockを使うFPGA単独案。
USB／I2Cの機能モデル試験とECP5 mappingの結果であり、OSでの列挙・実機受入ではない。
以前のRev CのUSB受入結果をF1へ流用しない。

## 接続と機能

`revc_usb_composite`がPHY/SIE、EP0、CDC ACM、MIDIStreamingを担当する。
`revc_midi_planner`が音符を実YMバス要求へ変換し、`revc_clocked_ym_top`を介して
既存のreset／BUSY／FM受信／PCM／I2Sへ接続する。CPU・ソフトCPU・MicroPythonは使わない。
USBのreset／configuration／suspendはSi5351・音声clock・I2C sessionのresetと分離した。

| インターフェース | エンドポイント | 初期機能 |
| --- | --- | --- |
| EP0 | 0、最大64 byte | descriptor、address、configuration、status、interface、halt/clear |
| CDC ACM control 0／data 1 | interrupt IN 0x81（8 byte）、bulk OUT 0x02／IN 0x82（64 byte） | line coding、DTR、SerialState通知、限定console |
| AudioControl 2／MIDIStreaming 3 | bulk OUT 0x03／IN 0x83（64 byte） | MIDI 1.0、cable 0。INは現在送信なしでNAK |

CDC consoleは`status`、`help`、`stop`／`s`／Ctrl+C、`panic`を受け付ける。
`status`はF1のaudio_ok／fault／state／executed／gatesとMIDI所有・maskの**16進snapshot**。
`stop`はI2Cを含む全体停止、`panic`はMIDIだけの停止。DTRを閉じてもMIDIは止めない。
16文字を超える行や未対応コマンドは明示的に拒否する。応答の未読・backpressure中もSTOPを処理する。
新しい応答で未送信応答を置換できる簡易consoleであり、C版console全体の互換やREPLではない。
C版の`play/test/capture/dump/fm/bus/reboot/bootsel`は実装していない。

MIDIはchannel 1〜3＝FM CH1〜3、4〜6＝SSG A〜C、各channel単音。
Note On／Off、velocity 0のOff、CC123（channel停止）、CC120（MIDI全音停止）、
System Reset（FF）を実装した。音程表・88件の初期設定・発音レジスタ列は既存C版と照合する。
velocityはOn/Off判定だけで、音量はC版と同じ固定値。Program Change、pitch bend、
sustain、SysEx、GM音色・voice allocationは対象外。MIDIは4 MHz専用で、他clock profileでは取得を拒否する。

受信時はCRC／bit stuffing／EOPを検査し、成功後に最大64 byteをclass bufferへ公開する。
OUTの同一DATA toggle再送はACKだけ返し、音符・CDC命令を二重実行しない。
INの未ACK packetは内容・toggleを保持し、status ACK完了前にはaddress等を変更しない。
USB-MIDI packet長が4の倍数でなければ、そのpacketの全イベントを破棄する。
各class OUTは1 packet buffer。処理待ち中のNAKは通常のUSB backpressureであり、無制限FIFOではない。

## I2Cとの制御権と停止

既存の0x42／YM22S002／v2要求、64 byte status、WYM1、HOST library／playerは変更していない。
内部の`source_reserved`を追加して、検査済みBEGINから準備完了までのMIDI新規取得を防ぐ。
既にMIDIが所有中ならBEGINを拒否し、演奏は維持する。MIDI初期設定・release中も所有状態に含む。
I2C所有中はUSB-MIDIを受信・消費して破棄し、I2C終了後に保留音符として再生しない。
停止／handover時はbuffer flushと受信時のblocked tag、200 msのquarantineを使う。
これはデバイス内部の古いイベントの抑止であり、PCが後から新送信したNote Onの由来を判別するものではない。

| 条件 | 処理と再開条件 |
| --- | --- |
| I2C STOP／CDC stop／外部global_stop | ゲートを閉じ、FIFOとMIDI希望音を破棄。実YMへ全声cleanup。明示BEGINまたは新しいNote Onで再開 |
| I2C lease期限切れ | v2 error8、FIFO破棄・全声消音。従来どおりSTOP／BEGINが必要 |
| MIDI所有中のUSB VBUS消失 | raw VBUSでMIDI出力ゲートを即時抑止。同期処理でcleanup、所有権を返却 |
| USB bus reset／unconfigure／suspend | MIDIだけを停止し、保留音符を破棄。再列挙・SOF復帰だけでは発音しない |
| I2C所有中のUSB切断／reset／suspend | I2C演奏・リース・音声pipelineは継続。USB由来panicでI2Cを停止しない |
| MIDI CC120／FF／不正な対応MIDIメッセージ | MIDI所有時だけpanic。別所有者を奪わない |
| 音声／clock異常 | 既存backendのfault消音。MIDIのBUSY／prepare／cleanupにも100 ms上限 |

MIDI内部のtimeout／writer faultはlatched faultとし、FPGA resetを要する。
USB suspend監視は正常CRCのSOF番号が3 ms進まない場合。11 bit番号の周回を許容する。
VBUSなしやSE0 resetのUSB-local resetは非同期assert・同期releaseを使う。
CDCのDTR切替やUSBの再列挙がI2C scoreを再開する経路はない。
全clock停止・FPGA無給電・未configurationに対する**外付け最終許可回路**は別途必要。

## USBコアと識別子

[avakar/usbcorev](https://github.com/avakar/usbcorev)のcommit
`8f799bb9f188f0266ff7926fdc93fad0fc754eae`を固定した。
元のLICENSE（No-notice MIT License）とソースを`vendor/usbcorev`へ無改変で保持し、
SHA-256 manifestを検査後、build出力コピーにだけ`patches/f1-validation.patch`を適用する。
パッチはSOF／transaction開始の公開、受信stuff検査、完全なACK終端待ち、
malformed受信の抑止、halt中のduplicate OUTに対するSTALL優先、duplicateのCRC検査を追加する。
class処理・descriptor・MIDI・console・結合RTLは本プロジェクトのMIT実装。
Verilatorの既存style警告免除はbuild先のvendorファイルだけに限定する。

`USB_VID=0`／`USB_PID=0`が既定で、そのままではpull-upも送信も許可しない。
試験では`cafe:4001`をモデル上だけで指定する。PicoのVID/PIDを転用しない。
出荷・実機用の正当なVID/PIDと必要なserial番号は、利用者が確保して設定する。
記述子のself-powered・bMaxPower=2 mAは試作の宣言値で、実回路の電流測定を表すものではない。

D+/D-入力、送信値・enable、pull-up許可、VBUS入力までが論理境界。
FPGA module・I/O pad・USB受信回路／抵抗・保護・電源逆流防止・VBUS検出・pin/制約は未確定。
上流もdifferential receiverなしの単純pad接続をUSB規格準拠とは扱っていない。
このRTLのビット列試験で電気適合・ホストOSでの列挙・USB認証を主張しない。

## 再現検証

プロジェクトルートから実行する。Python標準ライブラリ、C/C++、Verilator、Yosys、patchが必要。
コアのネットワーク取得は不要。空の出力先を指定する。

```sh
python3 fpga-standalone/check_usb.py --output outputs/f1/usb-01
```

既存I2C／音声／Si5351の回帰を先に行い、その後、descriptor構造・ROM再生成、
768通りのC版MIDI照合、理想USB hostのビット列試験、USB＋実YM結合、ECP5 mappingを実行する。
同じソースで実行済みの`check_clocks.py`結果は`--regression outputs/f1/clocks-01/summary.json`で再利用できる。
再利用時も既存topが使うRTLのSHAを検査する。既存topから未接続のUSB／MIDIモジュールは新しくbuild・検証する。結合試験は複数のclockを逐次評価するため時間がかかる。

[新しい検証記録](verification/usb-20261115.json)を追加し、過去の検証記録・実機受入を上書きしない。
CDC/MIDIだけでなくSi5351・実YM bus・FM serial・PCM・I2Sを含めて合成する。
LUT4等はYosysのmapped cell数で、最終配置後のslice数・収容・48 MHz達成を保証しない。
統合配置配線、全clock STA／CDC・電源／USB電気確認とF1実機受入が次の工程となる。

一次資料：
[USB-MIDI 1.0仕様](https://www.usb.org/sites/default/files/midi10.pdf)、
[固定USBコア](https://github.com/avakar/usbcorev/tree/8f799bb9f188f0266ff7926fdc93fad0fc754eae)、
既存`firmware-c/src/midi.c`・`midi_pitch.h`。


## 内部配置配線の追加評価

[TIMING.md](TIMING.md)にUSBを保持したECP5の内部OOC配置配線を追加した。
MIDI4 byte取出しを登録し、保持語もflush対象にした。fault・gateのcontrol側参照は2段同期する。
I2C/MIDI所有権と切断時の停止範囲は本書の契約を維持し、変更後の結合試験で確認する。
この追加評価はOS列挙、USB電気適合、物理IO／clock treeや実機受入を含まない。
