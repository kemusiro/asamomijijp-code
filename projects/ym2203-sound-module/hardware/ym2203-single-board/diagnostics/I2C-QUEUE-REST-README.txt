YM2203C Rev C - 予約旋律の休符と再発音、伴奏の持続 v1
2026-11-13

実機結果（2026-11-13）
----------------------
以下の試験は実機合格しました。3回とも休符では旋律だけが抜け、伴奏が持続し、次の音で再発音、左右正常、
歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行0bytes、2428ブロック、ピーク2976、最大変換1119us、deadline misses=0、max_poll_us=5002、max_idle_poll_us=946。
QUEUE runs=3 completed=3 aborted=0 events=27 pitch_writes=36 partial_cancels=0 max_late_ms=53 max_write_us=4062。
REST QUEUE tones=18 rests=9 rest_key_offs=9 resume_key_ons=9 pair_step=0、SIX I2C jobs=5 writes=42。
期限消音0回、最終ACK110=(59+17+17+17)&255、stale_flushes=0、受信470=1508-1038、送信994=3742-2748も一致しました。
以下の実機未確認の記載は配布時点のものです。残りはI2C-QUEUE-REST-FINAL-README.txtの総合試験1件です。

1. 前回の結果と今回の目的
------------------------
譜面差し替えは実機合格しました。従来音階と新旋律をFMで完奏し、新譜面を再登録せずSSGで完奏、左右正常、
歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
BUS HEAP全6行0bytes、2578ブロック、ピーク2976、最大変換1118us、deadline misses=0。
QUEUE runs=3 completed=3 aborted=0 events=27 pitch_writes=54 partial_cancels=0 max_late_ms=61 max_write_us=4081。
SIX I2C jobs=5 writes=24、期限消音0回、最終ACK114、stale_flushes=0、受信514=1552-1038、送信1086=3834-2748が整合しました。

今回は9個の500ms枠のうち3個を旋律の休符にし、伴奏を保ったまま次の音で旋律が戻ることを確認します。
新しい診断用ターゲット/HOSTを各1ファイル追加し、既存36ソースは維持します。新試験は実機未確認です。
正式な公開API/永続ファイル形式や汎用プレイヤーの仕様は変更しません。

2. 配線と追加ファイル
---------------------
配線・給電・音量は前回合格時のままです。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

次の2ファイルを各Picoの最上位へ追加します。
  Rev C：target/rev_c_i2c_queue_rest_target.py
  HOST ：host/rev_c_i2c_queue_rest_host.py
既存36ファイルを残します。新ターゲットはrev_c_i2c_queue_mute_target.py等もimportします。
未保存ならZIPのtarget/全18ファイルをRev C、host/全20ファイルをHOSTの最上位へ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

3. 実行
-------
1) 両側を停止して新しい2ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cでrev_c_i2c_queue_rest_target.pyを実行します。
   YM2203 Rev C / staged I2C queued melody rest target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_rest_host.pyを実行します。
   YM2203 Rev C / I2C queued melody rest HOST v1 / OTHER Pico only
6) 無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録の後に演奏します。全体は約1分です。

4. 聞こえる音
-------------
旋律の各枠は約500msです。
  ド・ミ・休み・ソ・休み・ミ・レ・休み・ド
  C   E   REST G   REST E   D   REST C

  1 FM CH1の高い旋律+SSG A/B/Cの低いドミソ
    3つの休符では旋律だけが抜け、SSG和音が持続します。
  2 SSG Aの低い旋律+FM CH1/2/3の高いドミソ
    同じ譜面を再登録せず再生します。3つの休符ではSSG旋律だけが抜け、FM和音が持続します。
  3 1と同じFM旋律+SSG和音を、同じ登録譜面の先頭から再演奏します。

休符は全音無音ではありません。伴奏3音は持続し、旋律はソ・ミ・最後のドで再び発音します。
FMのキーオフにはリリースと取り込み/I2S待ち時間があるため、旋律が消える位置は可聴で多少遅れる場合があります。
各回は9枠を完走して全音を停止し、1秒無音になります。今回は出力ミュート/通信中断による中止は行いません。
3回とも同じ旋律の休符と復帰、伴奏の持続、左右、歪み/予定外の音切れ/気になるクリック音、最後の全音無音を確認してください。

5. 診断用の拡張
---------------
新しい署名はRCQRS01!です。旧RCQMT01!のターゲットでは発音前に署名不一致で停止します。
既存の音インデックス0～4に、REST=5を追加します。今回の登録譜面は[0,2,5,4,5,2,1,5,0]です。
0x09をAPPEND_REST命令とし、停止中の登録だけに使います。既存0xA0～A4の音追加、CLEAR、PLAY、KEEP、STOP等は維持します。
先頭/末尾はド(index0)、固定9枠/500ms/3回という診断仕様です。可変長・可変音価や汎用音楽形式の導入ではありません。

休符は旋律声だけキーオフ/音量0にし、音程レジスタは書き換えません。伴奏の音程/キー/音量と出力ゲートは維持します。
次の音は音程2レジスタを書き、別のpollでキーオンしてから進行を更新します。音が続いている通常の音程変更は従来どおり2レジスタです。
初回は音程設定後に既存の準備時間を置いてキーオンし、先頭音が長くならないよう開始時刻を定義します。
全処理は1poll最大1レジスタで、予定時刻は開始+n*500msのままです。許容遅延100ms、1秒リースと音声期限は緩めません。
途中STOP/リース中止では休符後にキーオン待ちの処理も破棄し、残る伴奏も停止します。

0x28の予定マスクは4音編成のままですが、0x14の実適用マスクは休符中に旋律ビットだけが0になります。
  FM旋律：通常57、休符56（SSG3音のみ）
  SSG旋律：通常15、休符7（FM3音のみ）
0x2Aに累積休符枠数、0x2Bに累積有音枠数を置き、HOSTは完走後に照合します。
PITCH_STATUSは休符中も最後の有音音程を保持します。GATE NOTESは出力ゲートの指示なので、休符中も3のままです。
ゲートや適用マスクはソフトウェア状態であり、アナログ出力やピン電圧を測定した値ではありません。

6. ログと期待値
---------------
  QUEUE: runs=3 completed=3 aborted=0 events=27 pitch_writes=36 partial_cancels=0
  QUEUE RUN 1/2/3: state=4 notes=9、約500ms周期
  SIX I2C: jobs=5 writes=42 pending=-1 applied=0
  ACCOMP: run_masks=[57,15,57] applied=0
  QUEUE GATES: commands=0 dac_mutes=0 line_mutes=0 restores=0 gates=0
  GATE NOTES: 各回[3,3,3,3,3,3,3,3,3]
  REST QUEUE: tones=18 rests=9 rest_key_offs=9 resume_key_ons=9 pair_step=0
  REST SLOTSのscore：各回[0,2,5,4,5,2,1,5,0]
  REST SLOTS 1/3のmasks：[57,57,56,57,56,57,57,56,57]
  REST SLOTS 2のmasks：[15,15,7,15,7,15,15,7,15]
  lease_expirations=0、deadline misses=0、HOST PASS・SAFE・DONE

QUEUEのevents/notesは休符も含む時間枠数です。実際の有音旋律は各6音、合計18音です。
休符で音程を書かないためpitch_writesは54から36へ減ります。休符のキーオフ9回と復帰のキーオン9回を加え、SIX I2Cのwritesは24から42へ増えます。
partial_cancelsは途中中止で音程書き込みや再キーオンを待っていた回数も含みます。今回の正常完走では0です。
KEEP合計をKとすると最終ACKは(59+K)&255です。HOSTが具体値を表示します。LAST CONTROL STATEは[期待ACK,7,0,0]です。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMP/QUEUE GATES/GATE NOTES/REST QUEUE/REST SLOTS、SAFE/DONEまで）と、
3回の休符と再発音、伴奏の持続、左右と音質を報告してください。異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

7. 検証と制約
-------------
今回追加9項目を含む全292項目のPCテスト、MicroPython WASM 1.28.0での全HOST手順の模擬実行、
mpy-cross 1.29.0で配布38ソースのArm向けコンパイルの結果を同梱します。
実レジスタモデルで全枠の旋律/伴奏の音程・キー・音量、休符中のマスク/ゲート、1poll最大1レジスタ、予約時刻を確認します。
休符中STOP/リース、再発音の音程書き込み中/キーオン待ちの中止、連続休符、登録境界、遅延時停止、転送例外、時刻周回、
ネイティブ期限監視とSAFE停止、古い署名/ACK待機の拒否も検証します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
GPIO、I/O v1.1、FM変換、PIO/DMA/I2S、音量、リースと処理期限/予約遅延上限は変更しません。
実機の休符の聞こえ方/可聴時刻は未確認です。複数の独立旋律、長時間/可変長キュー、楽曲BIN、USB-MIDI、24時間運転は含みません。
