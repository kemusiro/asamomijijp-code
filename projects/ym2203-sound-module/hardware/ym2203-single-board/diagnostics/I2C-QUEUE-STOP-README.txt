YM2203C Rev C - 予約演奏の途中STOPと再開始診断 v1
2026-11-12

直前の実機結果
--------------
9音の予約演奏はFM/SSGとも一定間隔で全音階が聞こえ、左右正常、音質正常でした。
最後のSSGは約1秒で中止され、その後も無音、HOST PASS・SAFE・DONEと期限超過0を確認。
BUS HEAP全6行0bytes、2128ブロック、ピーク992、最大変換1117us、max_poll_us=4954、max_idle_poll_us=638。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=58 max_write_us=4116。
FMのキーオフ4556ms/出力終了4700ms、SSGは4557msで終了。最後は2音で中止されました。
SIX I2C jobs=6 writes=6、最終ACK102=(69+17+16)&255、期限消音1回、stale flush 0。
受信416=1454-1038、送信890=3638-2748も一致しています。

次は明示的なSTOPで予約の残りを中止し、再開始した場合に先頭から演奏できることを確認します。
中止後は元の曲の終了予定時刻を越えるまで4秒待ち、後続の音が出ないことを検査します。
今回はHOST1ファイルの追加だけです。STOP/再開始診断も実機合格しました。
FM/SSG途中停止と4秒無音、FMの先頭から全9音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2244ブロック、ピーク992、最大変換1116us、期限超過0、max_poll_us=4763、max_idle_poll_us=676。
QUEUE runs=3 completed=1 aborted=2 events=15 pitch_writes=30 partial_cancels=0 max_late_ms=58 max_write_us=4123。
SIX I2C jobs=5 writes=6、最終ACK84、期限消音0回、stale flush 0、受信354=1392-1038、送信807=3555-2748が一致。
次はI2C-QUEUE-ACCOMP-README.txtです。

1. 配線と追加ファイル
---------------------
前回合格した配線・給電・音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

HOST Picoの最上位へ、次の1ファイルだけを追加します。
  host/rev_c_i2c_queue_stop_host.py
既存のrev_c_i2c_queue_host.py等はimportするため残します。
Rev Cは前回合格したrev_c_i2c_queue_target.pyをそのまま実行します。
未保存の場合はZIPのtarget/全15ファイルをRev C、host/全13ファイルをHOSTへ保存します。
以前の27ファイルはバイト単位で同一です。main.py / boot.pyへの保存やUF2更新は不要です。

2. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cでrev_c_i2c_queue_target.pyを実行します。
   YM2203 Rev C / staged I2C nine-note queue target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_stop_host.pyを実行します。
   YM2203 Rev C / I2C queue STOP and restart HOST v1 / OTHER Pico only
6) 従来の無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録を経て、5秒待機後に発音します。
全体で約1分が目安です。ターゲットの再生回数を3回使うため、新しいターゲット実行から始めます。

3. 音の順序
-----------
  1 FMの「ドレミファソファミレド」を開始し、最初の数音でSTOP。4秒間無音。
  2 同じ登録譜面をFMで先頭のドから再開始し、全9音を再生。正常終了後にSTOP、1秒間無音。
  3 同じ譜面をSSGで開始し、最初の数音でSTOP。4秒間無音の後に終了。

中止のタイミングは、HOSTが発音済み3音以上を観測した後です。
通信時間により実際の中止音数Pが3音より多くなる場合もあるため、ログのPと照合します。
FMには取り込み/I2Sの遅延があるため、STOP直前の最後の音は短く聞こえる場合があります。
再開始ではCLEAR/再登録/取り込みSTARTを送り直さず、同じ譜面へのPLAYだけを送ります。
2回目は途中のファ等から続けず、先頭のドから全音階が聞こえることを確認してください。
左右は同じ音です。音程・再開始位置、無音継続、左右、歪み/予定外の音切れ/気になるクリック音を確認します。

今回は通信期限による中止の試験ではありません。正常時のlease_expirationsは0です。
すべての中止で、ACK付きSTOP、期限フラグ0、全音源停止、予約状態ABORTEDを照合します。
4秒待機中にはKEEPもPLAYも送りません。停止後の状態と譜面をもう一度読み、音数が増えていないことを確認します。
失敗時の1秒リースによる消音は従来どおり維持しています。

4. ログと期待値
---------------
HOSTは次の順序で表示します。
  STOP REQUEST / FM / observed notes=...
  STOP acknowledged / notes=... / expect4000 ms silence; no KEEP or PLAY
  PASS: STOP cancelled remaining notes and preserved score; progress stayed...
  RESTART FM / same uploaded score / full C D E F G F E D C
  PASS: queued FM scale complete ...
  SSG STOP / same score / short C D E then STOP
  STOP REQUEST / SSG ...
  STOP acknowledged ...
  PASS: STOP cancelled remaining notes ...

Rev Cの期待値は以下です。
  QUEUE: runs=3 completed=1 aborted=2 events=... pitch_writes=... partial_cancels=0～2 max_late_ms=0～100
  QUEUE RUN 1: voice=0 state=5 notes=P1、未実行のtimes_msは-1
  QUEUE RUN 2: voice=0 state=4 notes=9、times_msの先頭は0、以降500ms周期
  QUEUE RUN 3: voice=3 state=5 notes=P3、未実行のtimes_msは-1
  SIX I2C: jobs=5 writes=6 pending=-1 applied=0
  lease_expirations=0、deadline misses=0
eventsはP1+9+P3です。HOSTのEXPECTED QUEUEにも具体値を表示します。
2回のSTOPが音程レジスタ2回書き込みの途中に入った場合、未完了の1回分をpartial_cancelsに計上します。
pitch_writes=2*events+partial_cancelsで、正常範囲は2*events～2*events+2です。
途中までの音程処理は再開せず、新しいPLAYでは先頭音の両レジスタを設定し直します。

主試験3回で送信したKEEP合計をKとすると、最終ACKは(59+K)&255です。
HOSTのEXPECTED TARGET FINAL ACKとRev CのLAST CONTROL STATE=[最終ACK,7,0,0]を照合します。
正常終了1回/明示的中止2回なので、前回のcompleted=2 aborted=1 lease_expirations=1とは異なります。
共通DONEのall nine sound sectionsという文言によらず、今回は上記3回の実行です。

両側のログ全文（BUS HEAPとQUEUE RUNを含む）と、2回の途中STOPと無音継続、FMが先頭から全9音で再開したこと、
左右と音質、HOST PASS・SAFE・DONEを報告してください。
異常時はHOSTを再実行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

5. 検証と制約
-------------
全244項目（今回追加6項目）のPCテストが合格しました。独立11.25ms通信モデルで、
2回の中止/4秒後の状態不変、同じ登録データでの先頭再開始、全9音の時刻、音数/レジスタ回数/ACKの照合を確認しました。
STOP転送失敗の再送/後続再生なし、状態破損の検出、時刻周回、旧ヘルパー拒否も検証しました。
MicroPython WASM 1.28.0で全HOST手順を模擬実行し、mpy-cross 1.29.0で配布28ファイルをArm向けコンパイルしました。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
既存ターゲット/プロトコル/27ヘルパー/GPIO/音量/音色/PIO/DMA/I2S/期限監視は変更していません。
実機でのSTOPと再開始位置は上記条件で確認済みです。ログのレジスタ時刻は可聴音の到達時刻ではありません。
多音予約、可変長キュー、長い曲、USB-MIDI、24時間運転は今回含みません。
