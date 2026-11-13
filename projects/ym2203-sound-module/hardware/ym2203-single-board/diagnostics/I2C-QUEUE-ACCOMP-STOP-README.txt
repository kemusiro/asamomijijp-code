YM2203C Rev C - 伴奏付き予約演奏の途中STOPと再開始 v1
2026-11-12

実機結果
--------
以下の試験は実機合格しました。FM/SSGともSTOPで旋律と伴奏が全消音し4秒無音、同じ譜面をFMで先頭のドから全9音、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行bytes=0、2309ブロック、ピーク2976、最大変換1119us、deadline misses=0。
max_poll_us=4758、max_idle_poll_us=724、SIX I2C jobs=5 writes=24、lease_expirations=0。
QUEUE runs=3 completed=1 aborted=2 events=15 pitch_writes=30 partial_cancels=0 max_late_ms=44 max_write_us=4051。
ACCOMP run_masks=[57,57,15] applied=0、最終ACK82=(59+23)&255、stale_flushes=0。
受信373=1411-1038、送信828=3576-2748も一致。以下の実機未確認の記載は配布時点のものです。
次はI2C-QUEUE-MUTE-README.txtの、予約を進めたままのDAC/ラインミュートと解除です。

1. 直前の実機結果と今回の目的
------------------------------
伴奏付き予約再生は実機合格しました。FM/SSGの旋律と持続和音、最後の全音自動消音、左右正常、
歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
BUS HEAP全6行0bytes、2162ブロック、ピーク2976、最大変換1119us、deadline misses=0。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=62 max_write_us=4113。
SIX I2C jobs=6 writes=24、ACCOMP run_masks=[57,15,15] applied=0、期限消音1回、最終ACK99。
受信429=1467-1038、送信894=3642-2748も整合しています。

今回は、途中STOPで予約旋律だけでなく伴奏3音も止まり、元の終了予定時刻を過ぎても無音が続くこと、
登録済みの同じ譜面をFM旋律+SSG和音で先頭から再演奏できることを確認します。
新しいHOSTファイルだけを追加し、実機合格済みの伴奏ターゲットと全30ソースは変更しません。
今回のSTOP試験は実機未確認です。正式な公開APIや永続データ形式の変更ではありません。

2. 配線と追加ファイル
---------------------
前回合格した配線/給電/音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

HOST Picoの最上位へ次の1ファイルを追加してください。
  host/rev_c_i2c_queue_accomp_stop_host.py
前回の全30ファイルを残します。特にrev_c_i2c_queue_accomp_host.py、rev_c_i2c_queue_stop_host.pyもimportで必要です。
未保存ならZIPのtarget/全16ファイルをRev C、host/全15ファイルをHOSTの最上位へ保存してください。
main.py / boot.pyへの保存、ターゲット差し替え、UF2更新は不要です。

3. 実行
-------
1) 両側を停止し、新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cは前回と同じrev_c_i2c_queue_accomp_target.pyを実行します。
   YM2203 Rev C / staged I2C accompanied queue target v1
5) PHASE 0 READY後、HOSTで新しいrev_c_i2c_queue_accomp_stop_host.pyを実行します。
   YM2203 Rev C / I2C accompanied queue STOP HOST v1 / OTHER Pico only
6) 既存の無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録の後、演奏します。全体は約1分です。

4. 聞こえる音
-------------
  1 FM CH1の高い旋律+SSG A/B/Cの低いドミソ。最初の数音の後、STOPで全4音を停止し4秒無音。
  2 同じ登録譜面を再演奏。FMの「ドレミファソファミレド」全9音+SSGの持続和音。自動終了して1秒無音。
  3 SSG Aの低い旋律+FM CH1/2/3の高いドミソ。最初の数音の後、STOPで全4音を停止し4秒無音。
1/3のSTOPはHOSTが3音以上の進行を観測してから送信します。I2CとFM経路の待ち時間で、
聞こえる音の数や最後の音の長さは多少変わります。STOP後に旋律/伴奏が残らず、再開もしないことを確認します。
2はCLEAR/APPEND/STARTを再送せず、PLAYだけで先頭のドから全9音へ戻ります。
今回は意図的な通信断の自動消音試験はありません。STOP後はmode=0のままなので期限消音回数の期待値は0です。
左右同じ音、伴奏の持続、歪み/予定外の音切れ/気になるクリック音も確認してください。

5. ログと期待値
---------------
HOSTはACCOMP STOP、全音消音後の4000ms無音、RESTART FM、全9音完了、SSG側ACCOMP STOPを表示します。
各途中停止で、全16バイトの状態/音程、登録9音、進行位置を停止直後と4秒後に照合します。
発音中は短いマスク読み出し、ACK待機の40ms空きを使います。再試行や自動再演奏は行いません。

  QUEUE: runs=3 completed=1 aborted=2
  QUEUE RUN 1: voice=0 state=5 notes=P1（3以上9未満）
  QUEUE RUN 2: voice=0 state=4 notes=9、先頭時刻0、約500ms周期
  QUEUE RUN 3: voice=3 state=5 notes=P3（3以上9未満）
  events=P1+9+P3
  pitch_writes=2*events+partial_cancels（partial_cancelsは0～2）
  ACCOMP: run_masks=[57,57,15] applied=0
  SIX I2C: jobs=5 writes=24 pending=-1 applied=0
  lease_expirations=0、deadline misses=0、HOST PASS・SAFE・DONE
STOPが音程2レジスタの途中で受理された場合はpartial_cancelsが増えることがあります。
全3回のKEEP合計をKとすると、最終ACKは(59+K)&255です。HOSTが具体値を表示します。
LAST CONTROL STATEは[期待ACK,7,0,0]です。共通DONEのall nine sound sectionsによらず、今回は上記3回の再生です。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMPとSAFE/DONEまで）と、途中STOP後の全音消音/4秒無音、
FM先頭から全9音、伴奏の持続、左右と音質を報告してください。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存してください。

6. 検証と制約
-------------
今回追加6項目を含む全258項目のPCテスト、MicroPython WASM 1.28.0での全HOST手順の模擬実行、
mpy-cross 1.29.0で配布31ソースのArm向けコンパイルを実施します。結果は同梱ログに記載します。
独立11.25ms通信モデルと実レジスタモデルで、4音のキー/音量/音程保持、全音源停止、1poll最大1レジスタ、
4秒間に音源書き込みがないこと、同じ登録譜面の再演奏、時刻周回、マスク/進行/譜面の破損検出、
STOP転送例外を再試行せず既存リースで全音停止すること、古い署名/ACK待機の拒否を検証します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs

GPIO、I/O v1.1、音声変換、PIO/DMA/I2S、ゲイン、1秒リース、100ms予約遅延監視、処理期限は維持しています。
実機での音質や可聴停止時刻は模擬試験では確認できません。固定9音/500ms/3回の診断仕様です。
独立した複数旋律、長時間/可変長キュー、楽曲BIN、USB-MIDI、24時間運転は後続の対象です。
