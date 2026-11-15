YM2203C Rev C - 予約再生のミュート中STOPとPLAYだけでの再演奏 v1
2026-11-13

実機結果（2026-11-13）
----------------------
以下の試験は実機合格しました。DAC/ラインミュート中のSTOP後4秒無音、PLAYだけで先頭からFM全9音と伴奏、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行0bytes、2511ブロック、ピーク2976、最大変換1116us、deadline misses=0。
max_poll_us=4912、max_idle_poll_us=862、QUEUE runs=3 completed=1 aborted=2 events=19 pitch_writes=38 partial_cancels=0 max_late_ms=70 max_write_us=4063。
SIX I2C jobs=5 writes=24、QUEUE GATES commands=2 dac_mutes=1 line_mutes=1 restores=0 gates=0、再演奏9音のゲート指示は全3。
期限消音0回、最終ACK88=(61+27)&255、stale_flushes=0、受信418=1456-1038、送信883=3631-2748も一致しました。
以下の実機未確認の記載は配布時点のものです。次はI2C-QUEUE-MUTE-LEASE-README.txtのミュート中通信中断と自動消音です。

1. 前回の実機結果と今回の目的
----------------------------
予約再生中のミュート/解除は実機合格しました。DACミュートではSSG和音だけが残り、ラインミュートでは全消音、
解除後は旋律の途中から継続しました。最後の自動消音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEも確認済みです。
BUS HEAP全6行0bytes、2164ブロック、ピーク2976、最大変換1117us、deadline misses=0。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=70 max_write_us=4065。
SIX I2C jobs=6 writes=24、QUEUE GATES commands=4 dac_mutes=1 line_mutes=1 restores=2 gates=0。
期限消音1回、最終ACK99=(73+13+13)&255、stale_flushes=0、受信448=1486-1038、送信909=3657-2748が整合しました。

今回はミュートしたままSTOPを送り、全音源と残りの予約が停止し4秒無音が続くこと、
RESTOREなしのPLAYだけでミュートが解除され、同じ譜面を先頭から可聴で再演奏することを確認します。
新HOSTだけを追加し、前回実機合格したターゲットと全33ソースは維持します。今回の試験は実機未確認です。

2. 配線と追加ファイル
---------------------
前回合格した配線/給電/音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

HOST Picoの最上位へ次の1ファイルを追加します。
  host/rev_c_i2c_queue_mute_stop_host.py
前回の全33ファイルを残します。rev_c_i2c_queue_mute_host.py、rev_c_i2c_queue_accomp_host.py、
rev_c_i2c_queue_stop_host.py等もimportします。未保存ならZIPのtarget/全17ファイルをRev C、host/全17ファイルをHOSTへ保存します。
ターゲットは前回と同じです。main.py / boot.pyへの保存やUF2更新は不要です。

3. 実行
-------
1) 両側を停止し、新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cで前回と同じrev_c_i2c_queue_mute_target.pyを実行します。
   YM2203 Rev C / staged I2C queued gate mute target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_mute_stop_host.pyを実行します。
   YM2203 Rev C / I2C STOP while queued output muted HOST v1 / OTHER Pico only
6) 無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録の後に演奏します。全体は約1分です。

4. 聞こえる音
-------------
  1 FM CH1の高い旋律+SSG A/B/Cの低いドミソ
    最初の数音の後、DAC MUTEでSSG和音だけになります。
    ミュート中に予約がさらに2音以上進んだらSTOPを送り、SSG和音も消え、4秒間全音無音になります。
  2 同じ登録譜面をPLAYだけでFM旋律+SSG和音として再演奏
    RESTORE/CLEAR/APPEND/STARTを送らず、出力が通常状態へ戻ります。
    FMの「ドレミファソファミレド」全9音とSSGの持続和音が聞こえ、終端で停止して1秒無音になります。
  3 SSG Aの低い旋律+FM CH1/2/3の高いドミソ
    最初の数音の後、LINE MUTEで全音が消えます。
    ミュート中に予約がさらに2音以上進んだらSTOPを送り、その後も4秒間全音無音が続きます。

1/3はミュートされた音符が聞こえません。STOPのタイミングはI2C観測で多少変わります。
2では先頭のドから全9音がミュートなしで鳴ること、STOP後に残りの予約が復活しないこと、左右と音質を確認してください。
今回は意図的な通信断の自動消音試験はありません。lease_expirationsの期待値は0です。

5. ログと期待値
---------------
HOSTはQUEUE MUTE、STOP WHILE MUTED、4000ms無音、RESTART FM、全9音完了、SSG側のLINE MUTE/STOPを表示します。
停止直後と4秒後に、全16バイトの状態/6音程、登録9音、進行位置、ゲート0を照合します。
署名RCQMT01!、0x29のゲート指示、mode=1の予約進行と1秒リースは前回どおりです。
ゲート指示はソフトウェア状態であり、GPIO電圧やアナログ信号の測定値ではありません。

  QUEUE: runs=3 completed=1 aborted=2
  QUEUE RUN 1: voice=0 state=5 notes=P1（通常5音前後）
  QUEUE RUN 2: voice=0 state=4 notes=9、先頭時刻0、約500ms周期
  QUEUE RUN 3: voice=3 state=5 notes=P3（通常5音前後）
  events=P1+9+P3、pitch_writes=2*events+partial_cancels、partial_cancels=0～2
  SIX I2C: jobs=5 writes=24 pending=-1 applied=0
  ACCOMP: run_masks=[57,57,15] applied=0
  QUEUE GATES: commands=2 dac_mutes=1 line_mutes=1 restores=0 gates=0
  GATE NOTES 1: 3で始まり、途中に2、未実行の残りは255
  GATE NOTES 2: [3,3,3,3,3,3,3,3,3]
  GATE NOTES 3: 3で始まり、途中に1、未実行の残りは255
  lease_expirations=0、deadline misses=0、HOST PASS・SAFE・DONE
STOPが音程2レジスタの途中で受理されるとpartial_cancelsが増える場合があります。
全3回のKEEP合計をKとすると、最終ACKは(61+K)&255です。HOSTが具体値を表示します。
LAST CONTROL STATEは[期待ACK,7,0,0]です。今回は途中中止2回と、間の完奏1回です。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMP/QUEUE GATES/GATE NOTES、SAFE/DONEまで）と、
DACミュート中STOPでSSG和音も消えること、ラインミュート後も無音が続くこと、各4秒無音、
PLAYだけのFM全9音と伴奏、左右、歪み/予定外の音切れ/気になるクリック音を報告してください。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

6. 検証と制約
-------------
今回追加6項目を含む全271項目のPCテスト、MicroPython WASM 1.28.0での全HOST手順の模擬実行、
mpy-cross 1.29.0で配布34ソースのArm向けコンパイルの結果を同梱します。
実レジスタモデルでミュート中のSTOP受理、全キー/音量/ゲートの停止、4秒間の音源書き込みなし、
PLAYだけの先頭/通常出力への復帰、1poll最大1レジスタ、状態破損検出、両ミュートでのSTOP転送例外を再試行せず
既存リースで全音を停止すること、時刻周回、無音import、古い署名/ACK待機の拒否を検証します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
既存ターゲット、GPIO、I/O v1.1、FM変換、PIO/DMA/I2S、音量、処理期限と予約遅延上限は変更しません。
実機の音質/可聴時刻は未確認です。固定9音/500ms/3回の診断仕様で、複数旋律/長時間キュー、楽曲BIN、USB-MIDI、24時間運転は含みません。
