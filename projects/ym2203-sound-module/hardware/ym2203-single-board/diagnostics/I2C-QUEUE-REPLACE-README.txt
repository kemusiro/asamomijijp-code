YM2203C Rev C - 登録譜面の差し替えとFM/SSGでの再利用 v1
2026-11-13

実機結果（2026-11-13）
----------------------
以下の試験は実機合格しました。従来音階と差し替え旋律をFMで完奏し、同じ新譜面をSSGでも完奏、左右正常、
歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行0bytes、2578ブロック、ピーク2976、最大変換1118us、deadline misses=0、max_poll_us=4936、max_idle_poll_us=854。
QUEUE runs=3 completed=3 aborted=0 events=27 pitch_writes=54 partial_cancels=0 max_late_ms=61 max_write_us=4081。
SIX I2C jobs=5 writes=24、期限消音0回、最終ACK114=(69+15+15+15)&255、stale_flushes=0、受信514=1552-1038、送信1086=3834-2748も一致しました。
以下の実機未確認の記載は配布時点のものです。次はI2C-QUEUE-REST-README.txtの旋律の休符です。

1. 前回の結果と今回の目的
------------------------
ミュート中の通信休止/復帰は実機合格しました。通信休止で全音自動消音と4秒無音、STOP/PLAYで先頭からFM全9音と伴奏、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
BUS HEAP全6行0bytes、2755ブロック、ピーク2976、最大変換1117us、deadline misses=0。
QUEUE runs=3 completed=1 aborted=2 events=19 pitch_writes=38 partial_cancels=0 max_late_ms=61 max_write_us=4071。
SIX I2C jobs=7 writes=24、期限消音2回、最終ACK84、stale_flushes=0、受信402=1440-1038、送信901=3649-2748も整合しました。

予約再生の基本・ミュート・STOP・通信期限切れからの復帰に続き、今回は別の譜面への差し替えを確認します。
停止中に従来の9音を新しい9音へ登録し直し、古い音が混ざらず、同じ新譜面をFM/SSGで再利用できることを確認します。
HOST1ファイルだけを追加し、既存35ソースと実機合格済みターゲットは維持します。今回の試験は実機未確認です。

2. 配線と追加ファイル
---------------------
配線・給電・音量は前回合格時のままです。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

HOST Picoの最上位へ次の1ファイルを追加します。
  host/rev_c_i2c_queue_replace_host.py
既存35ファイルを残します。rev_c_i2c_queue_mute_host.py、rev_c_i2c_queue_accomp_host.py等をimportします。
未保存ならZIPのtarget/全17ファイルをRev C、host/全19ファイルをHOSTの最上位へ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

3. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cは前回と同じrev_c_i2c_queue_mute_target.pyを実行します。
   YM2203 Rev C / staged I2C queued gate mute target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_replace_host.pyを実行します。
   YM2203 Rev C / I2C queued score replacement HOST v1 / OTHER Pico only
6) 無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録の後に演奏します。全体は約1分です。

4. 聞こえる音
-------------
  1 FM CH1の高い旋律「ドレミファソファミレド」+SSG A/B/Cの低いドミソ
    従来譜面を全9音完奏し、自動終了して1秒無音になります。
  2 FM CH1の高い旋律「ドミソミドレファレド」+同じSSG低音和音
    停止中にCLEARと9音のAPPENDで譜面を差し替えます。新旋律を全9音完奏して1秒無音になります。
  3 SSG Aの低い旋律「ドミソミドレファレド」+FM CH1/2/3の高いドミソ
    再登録せず、同じ新譜面をPLAY SSGで全9音完奏します。最後も全音が消えます。

今回はミュート区間や通信休止はありません。全3回が完奏し、各音は約500msです。
2の旋律が1とは異なり、3では2と同じ旋律を低いSSG音で聞けること、伴奏の持続、左右と音質、終了時の無音を確認してください。

5. 制御とログの期待値
---------------------
登録譜面は次の2種類です。値は既存の5音のインデックス0=ド、1=レ、2=ミ、3=ファ、4=ソです。
  SCALE     [0,1,2,3,4,3,2,1,0]
  ALTERNATE [0,2,4,2,0,1,3,1,0]
両譜面とも既存診断の終了状態照合に合わせて最後はドです。任意長・休符・可変音符長へ拡張する試験ではありません。
upload_scoreは転送前に9音/0～4/最終音0を検査します。CLEAR後にcount=0、進行0、選択声255、音源/ゲート停止を照合し、
APPEND完了後は登録9音とcount=9を読み戻します。CLEARは登録数を0にし、旧データ領域のゼロ消去は要求しません。
新しい9音を書き終えて一致した場合だけPLAYを送ります。演奏後も譜面を読み戻します。
3回目にはCLEAR/APPEND/STARTを再送しません。FM取り込みは全体で1回だけSTARTし、差し替え中も動かしています。
診断署名RCQMT01!と既存の1秒リース、40ms ACK待機は維持します。エラー時の自動再送/再演奏はありません。

  QUEUE: runs=3 completed=3 aborted=0 events=27 pitch_writes=54 partial_cancels=0
  QUEUE RUN 1/2/3: state=4 notes=9、先頭時刻0、約500ms周期
  SIX I2C: jobs=5 writes=24 pending=-1 applied=0
  ACCOMP: run_masks=[57,57,15] applied=0
  QUEUE GATES: commands=0 dac_mutes=0 line_mutes=0 restores=0 gates=0
  GATE NOTES: 3回すべて[3,3,3,3,3,3,3,3,3]
  最終譜面：[0,2,4,2,0,1,3,1,0]
  CLEAR=2、APPEND=18、capture START=1
  lease_expirations=0、deadline misses=0、HOST PASS・SAFE・DONE
KEEP合計をKとすると最終ACKは(69+K)&255です。HOSTが具体値を表示します。
LAST CONTROL STATEは[期待ACK,7,0,0]です。前回までと異なり、今回はcompleted=3、aborted=0です。
QUEUE RUNの既存ログは音程更新時刻を記録し、各回の譜面そのものは履歴保存しません。
再生前のHOST表示/読み戻し照合と、実際に聞こえる旋律の違いを併せて確認してください。
0x29やGATE NOTESはソフトウェアのゲート指示であり、GPIO電圧やアナログ出力の測定値ではありません。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMP/QUEUE GATES/GATE NOTES、SAFE/DONEまで）と、
3回の旋律、伴奏の持続、左右、歪み/予定外の音切れ/気になるクリック音、最後の無音を報告してください。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

6. 検証と制約
-------------
今回追加6項目を含む全283項目のPCテスト、MicroPython WASM 1.28.0での全HOST手順の模擬実行、
mpy-cross 1.29.0で配布36ソースのArm向けコンパイルの結果を同梱します。
実レジスタモデルで27音すべてのFM/SSG音程、伴奏の音程/キー/音量、ゲートと予約時刻、
1poll最大1レジスタ、登録2回とSSGでの再利用、旧譜面読み戻しや転送例外で再演奏しないこと、
不正譜面の無転送拒否、時刻周回、無音import、古い署名/ACK待機の拒否を検証します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
ターゲット、GPIO、I/O v1.1、音声変換、PIO/DMA/I2S、音量、リースと処理期限/予約遅延上限は変更しません。
実機での音質/可聴時刻は未確認です。固定9音/500ms/3回の診断であり、複数旋律/長時間キュー、楽曲BIN、USB-MIDI、24時間運転は含みません。
