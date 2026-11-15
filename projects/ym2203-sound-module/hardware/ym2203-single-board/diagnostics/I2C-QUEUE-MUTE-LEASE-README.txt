YM2203C Rev C - 予約演奏ミュート中の通信休止・自動消音と明示的復帰 v1
2026-11-13

実機結果（2026-11-13）
----------------------
以下の試験は実機合格しました。通信休止で全音自動消音と4秒無音、明示的STOP/PLAYで先頭からFM全9音と伴奏、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行0bytes、2755ブロック、ピーク2976、最大変換1117us、deadline misses=0、max_poll_us=4914、max_idle_poll_us=855。
QUEUE runs=3 completed=1 aborted=2 events=19 pitch_writes=38 partial_cancels=0 max_late_ms=61 max_write_us=4071。
SIX I2C jobs=7 writes=24、期限消音2回、最終ACK84=(61+23)&255、stale_flushes=0、受信402=1440-1038、送信901=3649-2748も一致しました。
以下の実機未確認の記載は配布時点のものです。次はI2C-QUEUE-REPLACE-README.txtの譜面差し替えです。

1. 前回の結果と今回の目的
------------------------
ミュート中STOPは実機合格しました。DAC/ライン各ミュート中STOP後4秒無音、PLAYだけで先頭からFM全9音と伴奏、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
BUS HEAP全6行0bytes、2511ブロック、ピーク2976、最大変換1116us、deadline misses=0。
QUEUE runs=3 completed=1 aborted=2 events=19 pitch_writes=38 partial_cancels=0 max_late_ms=70 max_write_us=4063。
SIX I2C jobs=5 writes=24、QUEUE GATES commands=2 dac_mutes=1 line_mutes=1 restores=0 gates=0。
期限消音0回、最終ACK88、stale_flushes=0、受信418=1456-1038、送信883=3631-2748も整合しました。

今回はSTOPを送らず、ミュートしたまま1.8秒間すべてのI2C通信を休止します。
1秒の通信リースで全音源と残りの予約が停止し、読み出しを再開しても無音が続くこと、
STOPで期限切れフラグを解除してからPLAYを送ると同じ譜面を先頭から再演奏することを確認します。
HOST1ファイルだけを追加し、実機合格したターゲットと既存34ソースは維持します。今回の試験は実機未確認です。

2. 配線と追加ファイル
---------------------
配線・給電・音量は前回合格時のままです。通信休止はプログラムが行うため、実行中に線を抜く必要はありません。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

HOST Picoの最上位へ次の1ファイルを追加します。
  host/rev_c_i2c_queue_mute_lease_host.py
既存34ファイルを残します。rev_c_i2c_queue_mute_host.py、rev_c_i2c_queue_accomp_host.py、rev_c_i2c_queue_stop_host.py等もimportします。
未保存ならZIPのtarget/全17ファイルをRev C、host/全18ファイルをHOSTの最上位へ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

3. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cは前回と同じrev_c_i2c_queue_mute_target.pyを実行します。
   YM2203 Rev C / staged I2C queued gate mute target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_mute_lease_host.pyを実行します。
   YM2203 Rev C / I2C lease while queued output muted HOST v1 / OTHER Pico only
6) 無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録の後に演奏します。全体は約1分です。

4. 聞こえる音と操作
-------------------
  1 FM旋律+SSG低音和音
    最初の数音の後、DAC MUTEでSSG和音だけになります。
    NO I2Cの表示後、残ったSSG和音も約1秒以内に自動消音します。その後4秒間の無音を確認します。
    HOSTは期限切れ/予約中止/全音源停止を読み戻し、STOPを送って期限フラグだけを解除します。
  2 明示的なPLAYによる復帰
    同じ登録譜面をFM旋律+SSG和音として先頭のドから全9音再演奏し、自動終了して1秒無音になります。
    RESTORE、再登録、STARTの再送はありません。
  3 SSG旋律+FM高音和音
    最初の数音の後、LINE MUTEで全音が消えます。
    同様にI2C休止で全音源と残りの予約が中止され、読み出しを再開しても4秒間無音が続きます。
    最後にSTOPで期限フラグを解除して終了します。再演奏はしません。

3はラインミュート時点ですでに無音なので、期限切れによるキー/音量停止はログで確認します。
読み出し再開やSTOPだけで音が戻らず、2のPLAYで初めて演奏が始まることを確認してください。
ミュートされた音符は聞こえません。I2C観測とFM経路の遅延により切り替え位置は多少変わります。
左右、歪み/予定外の音切れ/気になるクリック音も確認します。

5. ログと期待値
---------------
NO I2C区間ではKEEP、STOP、読み出しのすべてを1.8秒間送信しません。ピン解放/断線/バス固定を模擬する試験ではありません。
リース中止後と4秒後に、全16バイトの状態/6音程、期限切れフラグ1、登録9音、同じ進行位置、ゲート0を照合します。
次のSTOPのACKで期限切れフラグ0となり、全音源は停止したままです。復帰のPLAYだけが予約開始時刻と先頭音を初期化します。

  QUEUE: runs=3 completed=1 aborted=2
  QUEUE RUN 1: voice=0 state=5 notes=P1（通常は最初の数音）、残りの時刻は-1
  QUEUE RUN 2: voice=0 state=4 notes=9、先頭時刻0、約500ms周期
  QUEUE RUN 3: voice=3 state=5 notes=P3（通常は最初の数音）、残りの時刻は-1
  events=P1+9+P3、pitch_writes=2*events+partial_cancels、partial_cancels=0～2
  SIX I2C: jobs=7 writes=24 pending=-1 applied=0
  ACCOMP: run_masks=[57,57,15] applied=0
  QUEUE GATES: commands=2 dac_mutes=1 line_mutes=1 restores=0 gates=0
  GATE NOTES 1は途中に2、2は全9音3、3は途中に1、未実行は255
  lease_expirations=2、deadline misses=0、HOST PASS・SAFE・DONE
jobsは2回のリース中止処理を含むため、前回の5から7になります。音源のキー/音量書き込みは24のままです。
全3回のKEEP合計をKとすると、最終ACKは(61+K)&255です。リース中止はACKを増やしません。
LAST CONTROL STATEは[HOST期待ACK,7,0,0]です。今回の自動消音は2回、完奏は間のFM再演奏1回です。
0x29やGATE NOTESはソフトウェアのゲート指示であり、GPIO電圧やアナログ出力の測定値ではありません。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMP/QUEUE GATES/GATE NOTES、SAFE/DONEまで）と、
DACミュート後に残ったSSG和音の自動消音、無音継続、明示的復帰の全9音と伴奏、左右と音質を報告してください。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

6. 検証と制約
-------------
今回追加6項目を含む全277項目のPCテスト、MicroPython WASM 1.28.0での全HOST手順の模擬実行、
mpy-cross 1.29.0で配布35ソースのArm向けコンパイルの結果を同梱します。
独立11.25ms通信モデルで無通信区間にHOST転送がないこと、予約が進んでから期限切れとなり全音源が停止すること、
4秒間の追加音源書き込みなし、期限フラグ/音程/進行/譜面の照合、明示的復帰、1poll最大1レジスタ、
破損状態や復帰STOP転送例外で再演奏しないこと、時刻周回、無音import、古い署名/ACK待機の拒否を確認します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
ターゲット、GPIO、I/O v1.1、音声変換、PIO/DMA/I2S、音量、1秒リースと既存の処理期限/予約遅延上限は変更しません。
実機での音質/可聴時刻は未確認です。固定9音/500ms/3回の診断であり、複数旋律/長時間キュー、楽曲BIN、USB-MIDI、24時間運転は含みません。
