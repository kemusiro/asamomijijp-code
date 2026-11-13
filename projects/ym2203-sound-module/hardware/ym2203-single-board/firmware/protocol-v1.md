# Rev C hardware I2C API v1 / firmware 0.2.0-alpha.1

物理Rev C専用。WebLab仮想デバイスAPI、診断プロトコル `RCI2C01!` とは別仕様。
I2Cアドレスは7bit `0x42`、3.3V、10kHz。GPIOは既存承認済み割り当てを維持する。
一つのホストから要求を直列に送る。一般的なレジスタ読み書き形式で、最初の送信バイトが
256バイト窓のポインタ、以降はデータ。ポインタは255の次に0へ戻る。

## 識別・要求・状態

| アドレス | 内容 |
| --- | --- |
| `00..07` | 読み取り専用 ASCII `YM22F001` |
| `08..0F` | 固定capability bytes: `1,1,0,31,128,10,16,48` |
| `10..13` | 状態4バイト。ポインタ`10`指定時にスナップショットを固定 |
| `14` | MIDI制御権を保持中なら1、それ以外0（読み取り専用） |
| `15` | MIDI押鍵の声マスクbit0..5（FM3声、SSG3声、読み取り専用） |
| `16` | USB-MIDIが列挙済みかつSOF進行中なら1（読み取り専用） |
| `40..4F` | 要求16バイトのステージング領域 |
| `50` | `A5`を書いてコミット。16バイト全体の転送が必要 |

capabilityは順にprotocol major/minor/reserved/features、キュー容量、payload最大、
frame長、出力kHz。features=31はCRC/補充キュー/リース/出力ゲート/MIDI共存のbit0..4。
minor1の追加領域14..16以外は旧minor0と互換。旧ホストは継続利用できる。
未定義読み取り領域は0。識別領域と状態への書き込みは無視する。
ステージング中の読み取りでは要求内容を返さない。

要求は `version=1, sequence, opcode, payload_length, payload[10], crc_lo, crc_hi`。
CRC-16/XMODEM、初期値0、poly `1021`、反転なし、xorout0、先頭14バイトを対象。
未使用payloadは0で埋める。ホストは`40`+16バイト、続けて`50,A5`を送る。
未完成/重複commitはCRC_ERRORとして扱い、YMには反映しない。
コミット待ちのフレームを後続書き込みで上書きできない。

sequenceは初期0、次の要求は現在値+1(mod256)。CRC正常・期待sequenceの要求は、
INVALID/BUSY/FULL等で拒否されてもsequenceを消費する。CRC/SEQUENCEエラーは消費しない。
同じsequenceで同じ16バイトを再送した場合、直前の結果を返し再実行・リース延長はしない。
同じsequenceで異なる要求はSEQUENCE。ホストライブラリは自動再送を行わず、明示的STOPで
現在sequenceを読み直して復帰する。タイムアウトを成功として扱わない。

状態は `sequence, result, flags, queued_count`。
resultは0=OK、1=CRC_ERROR、2=INVALID、3=BUSY、4=FULL、5=LEASE_ERROR、
6=SEQUENCE、7=LATE、8=IO_ERROR、9=FAULT、10=PENDING。
非同期処理はPENDING、実書き込み・準備の完了でOK。

| flags bit/value | 意味 |
| --- | --- |
| 0 / 1 | READY: API稼働中。FAULT中でも立つ。発音許可を意味しない |
| 1 / 2 | ACTIVE: 通信リース対象セッション |
| 2 / 4 | DAC出力ゲートON |
| 3 / 8 | LINE出力ゲートON |
| 4 / 16 | WORKING: レジスタ書き込み/準備/停止/排出処理中、またはMIDIが占有中 |
| 5 / 32 | 通信期限切れ。明示的STOPで解除 |
| 6 / 64 | 障害停止。明示的STOPで解除 |
| 7 / 128 | SEAL済み、この演奏の登録終端 |

## コマンド

| opcode | payload | 動作 |
| --- | --- | --- |
| 0 PING | 空 | 識別/疎通。リースは延長しない |
| 1 STOP | 空 | 最優先。ゲートOFF、予約破棄、6声を順次停止。完了でACK。期限/障害フラグ解除 |
| 2 KEEP | 空 | ACTIVEならリースを更新。期限切れ後は復帰しない |
| 3 WRITE | `(register,value)`×1..5 | 全組を検証後、順に実書き込み。完了でACK |
| 4 PUSH | `(delta_lo,delta_hi,register,value)`×1..2 | 全組と空きを検証後、原子的にキュー追加 |
| 5 PLAY | 空 | 非ACTIVEかつキューあり。無音準備後、ゲートON・先頭から開始 |
| 6 GATES | 1バイト、bit0=DAC/bit1=LINE | 出力のみ変更。演奏時刻は継続。ACTIVE/リースを開始 |
| 7 SEAL | 空 | 最後のイベント登録済みを通知。以降のPUSHは禁止 |

STOP/PING/KEEP以外は処理中BUSYとなる。STOPは処理中でも受理しゲートを閉じる。
期限/障害フラグ中はSTOP/PING以外を拒否する。受理されたWRITE/PUSH/SEAL/GATES/PLAYと
KEEPはACTIVEセッションの1000msリースを更新する。読み取りや不正要求は更新しない。
期限判定はコマンド受理前にも行うため、遅れたKEEPで失効済みセッションを再開しない。
キュー満杯や不正バッチは一切追加しない。データ量の総上限はキュー容量と別である。

## 演奏時刻と終了

キューは128イベント、各deltaは0..65535ms。順序は受理順。
第1イベントはPLAYの準備完了時刻+delta、以降は前イベントの予定時刻+delta。
`time.ticks_add/ticks_diff`で折り返しに対応し、累積絶対時刻や無限に増える整数を保持しない。
長時間再生は空き枠を確認してPUSHする。未SEALで空の場合は発音状態を保って補充待ち。
総演奏時間・曲数は制限しないが、1000ms以内の有効更新が常に必要。

alpha.2では、既に受理したYM処理は外部I2C通信中も進める。新要求の受理とPLAYの
準備完了はI2Cアイドル時に行う。レジスタ適用は約11.25msごとに最大1個。同時刻イベントも書き込み順序を保って順次適用し、
完全同時ではない。100msを超えて遅れたイベント、100ms続くYM BUSYはFAULT消音する。
100ms以内の遅れは許容する。この版のキューはサンプル精度を保証しない。
SEALEDかつ最後の適用後、全声停止と135msの排出を経てゲートを閉じる。
先頭から再演奏する場合はSTOPでキューを初期化し、再度イベントを送る。
STOP/通信期限/障害は予約を破棄する。GATESによるミュートは破棄しない。

## 許可レジスタ

SSG `00..0D`（粗周期/shapeは4bit、noiseは5bit、mixerは6bit、volumeは5bit）。
FMタイマ`24..27`（25は2bit、27は6bit）、key`28`（ch0..2、予約bit禁止）。
operator `30..9E`で下位2bit≠3。グループ別有効maskは
30/40=`7F`、50=`DF`、60=`9F`、70=`1F`、80=`FF`、90=`0F`。
通常周波数`A0..A2`と`A4..A6`（後者6bit）、algorithm/feedback`B0..B2`（6bit）。
その他は禁止。プリスケーラ、CSM/CH3特殊モード、SSG I/Oは対象外。
FM3声+SSG3声、SSGノイズ/エンベロープやFM音色の基本パラメータはレジスタで設定する。

## 実装境界

プロトコルとスケジューラは`ym2203_fw.py`、GPIO/PIO/I2S/I2Cは`ym2203_hw.py`と
`ym2203_audio.py`、ホストは`ym2203_revc.py`。旧診断ヘルパー5本はhash固定で取り込む。
新しい署名とバージョンを持つ実験APIであり、将来の互換性変更は別major/署名として扱う。
旧WebLab BINを自動認識する仕様ではない。

## USB-MIDIとの共存（minor1）

USB-MIDIは先行するI2CのACTIVE/処理/登録キューがあるとNote Onを破棄する。
MIDIが制御中はI2CのSTOP/PING以外をBUSY(3)で拒否する。正しいsequenceの拒否要求も
通常どおりsequenceを消費し、同一要求の重複は再実行しない。
I2C STOPはMIDIにも優先し、受信済みMIDIと声の保留書き込みを破棄して全体消音する。
USBの切断/リセット/休止はMIDIだけを停止し、I2Cのセッションには作用しない。
MIDIはI2Cの1秒リースを利用せず、USB SOFの250ms停止を監視する。
全ノートOFFと書き込み終了、135msの排出後にMIDI制御権を解放する。
音色レジスタとクロックは共通のため、同時に両ソースで演奏・音色変更する仕様にはしない。
MIDI1..3=FM1..3、MIDI4..6=SSG A..C。詳細はUSB-MIDI-README.txtを参照。
