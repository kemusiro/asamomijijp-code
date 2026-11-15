YM2203C Rev C - 予約再生中のDAC/ラインミュートと解除 v1
2026-11-13

実機結果（2026-11-13）
----------------------
以下の試験は実機合格しました。DACミュートではSSG和音だけ、ラインミュートでは全消音、解除後は旋律の途中から継続、
最後の自動消音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行0bytes、2164ブロック、ピーク2976、最大変換1117us、deadline misses=0。
max_poll_us=4941、max_idle_poll_us=872、SIX I2C jobs=6 writes=24、lease_expirations=1。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=70 max_write_us=4065。
QUEUE GATES commands=4 dac_mutes=1 line_mutes=1 restores=2 gates=0。
GATE NOTES 1=[3,3,3,2,2,2,3,3,3]、2=[3,3,3,1,1,1,3,3,3]、3=[3,3,255,255,255,255,255,255,255]。
最終ACK99=(73+13+13)&255、stale_flushes=0、受信448=1486-1038、送信909=3657-2748も一致。
以下の実機未確認の記載は配布時点のものです。次はI2C-QUEUE-MUTE-STOP-README.txtのミュート中STOPです。

1. 直前の結果と今回の目的
------------------------
伴奏付きSTOP/再開始は実機合格しました。FM/SSGとも全4音停止と4秒無音、同じ譜面をFMで先頭のドから全9音、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
BUS HEAP全6行0bytes、2309ブロック、ピーク2976、最大変換1119us、deadline misses=0。
QUEUE runs=3 completed=1 aborted=2 events=15 pitch_writes=30 partial_cancels=0 max_late_ms=44 max_write_us=4051。
SIX I2C jobs=5 writes=24、ACCOMP run_masks=[57,57,15] applied=0、期限消音0回、最終ACK82。
受信373=1411-1038、送信828=3576-2748も整合しています。

今回はSTOPと異なり、出力だけをミュートし、旋律の予約時刻と伴奏のキーを保ちます。
解除で先頭へ戻らず、その時点の音符から聞こえることを確認します。新試験は実機未確認です。
診断専用署名と状態を追加し、正式な公開APIや永続データ形式は変更しません。

2. 配線と追加ファイル
---------------------
前回合格した配線/給電/音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

次の2ファイルを、それぞれのPicoの最上位へ追加してください。
  Rev C：target/rev_c_i2c_queue_mute_target.py
  HOST ：host/rev_c_i2c_queue_mute_host.py
前回の全31ソースはそのまま残します。新ターゲットも旧rev_c_i2c_queue_accomp_target.py等をimportします。
未保存ならZIPのtarget/全17ファイルをRev C、host/全16ファイルをHOSTの最上位へ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

3. 実行
-------
1) 両側を停止して新しい2ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cでrev_c_i2c_queue_mute_target.pyを実行します。
   YM2203 Rev C / staged I2C queued gate mute target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_mute_host.pyを実行します。
   YM2203 Rev C / I2C queued gate mute HOST v1 / OTHER Pico only
6) 無音検査6段階、BUS HEAP6行、START/KEEPと譜面登録の後に演奏します。全体は約1分です。

4. 聞こえる音
-------------
  1 FM CH1の高い旋律+SSG A/B/Cの低いドミソ
    最初の数音は両方聞こえます。DAC MUTEでFM旋律が消え、SSG和音だけが持続します。
    約1～2秒後にRESTOREでFM旋律が後半の音から戻り、終端で全音が停止します。
  2 SSG Aの低い旋律+FM CH1/2/3の高いドミソ
    最初の数音は両方聞こえます。LINE MUTEで全音が消えます。
    約1～2秒後にRESTOREで旋律の後半と伴奏が戻り、終端で全音が停止します。
  3 SSG旋律+FM和音を再開始し、KEEPなしで約1秒後に全音を自動消音。その後も無音が続きます。

譜面は各9音/500msですが、1/2でミュートされた音符は聞こえません。全9音を可聴で確認する試験ではありません。
解除で先頭のドへ戻らず途中から続くこと、DAC MUTE中もSSG和音が残ること、LINE MUTE中は全音が消えること、
左右、歪み/予定外の音切れ/気になるクリック音を確認します。ミュート/終了に伴う音の停止は意図したものです。
HOSTの観測で3音以上進んだらミュート、6音以上進んだら解除します。I2C観測とFM経路の遅延により、
切り替え位置や解除直後に聞こえる音は多少変わります。厳密な可聴同期を保証する試験ではありません。

5. 診断仕様とログ
-----------------
今回の署名はRCQMT01!です。旧RCQAC01!ターゲットを誤って実行した場合は、発音前に署名不一致で停止します。
0x04 DAC_MUTE、0x05 LINE_MUTE、0x03 BOTH（RESTORE）を予約のPLAYING中だけ受け付けます。
この署名ではmode=1は予約再生中を表し、出力ミュートでも1を保ちます。既存診断のmode=4/5とは異なります。
ミュート命令はキー/音量/音程レジスタを書かず、予約の開始時刻・進行・発音マスクも変更しません。
命令は1秒の通信リースを更新しますが、予約で自動実行された音符はリースを更新しません。

0x29はソフトウェアが指示したゲート状態です。実際のアナログ出力やGPIO電圧を測定した値ではありません。
  bit0：DAC_ALLOW指示、bit1：LINE_ALLOW指示
  3=両方許可、2=DACのみミュート、1=ラインのみミュート、0=停止
出力ピンのPin.value()読み出しには依存しません。準備/終了/STOP/リース中止は既存ターゲットの処理を使用します。
GATE NOTESは各音程イベント時の指示状態で、未実行の音符は255です。

期待値:
  QUEUE: runs=3 completed=2 aborted=1 events=18+P pitch_writes=2*(18+P) partial_cancels=0
  QUEUE RUN 1/2: state=4 notes=9、時刻は開始+n*500ms、過剰遅延なし
  QUEUE RUN 3: state=5 notes=P（通常は最初の数音）、以降は未実行
  SIX I2C: jobs=6 writes=24 pending=-1 applied=0
  ACCOMP: run_masks=[57,15,15] applied=0
  QUEUE GATES: commands=4 dac_mutes=1 line_mutes=1 restores=2 gates=0
  GATE NOTES 1: 3で始まり、2を2音以上含み、3で終わる全9音
  GATE NOTES 2: 3で始まり、1を2音以上含み、3で終わる全9音
  GATE NOTES 3: 実行済みは3、残りは255
  lease_expirations=1、deadline misses=0、HOST PASS・SAFE・DONE
前半2回のKEEP合計をKとすると、最終ACKは(73+K)&255です。HOSTが具体値を表示します。
LAST CONTROL STATEは[期待ACK,7,0,0]です。今回は2回の完奏と最後の短い自動消音です。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMP/QUEUE GATES/GATE NOTES、SAFE/DONEまで）と、
各ミュートの聞こえ方、解除後に途中から続くこと、最後の全音消音、左右と音質を報告してください。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

6. 検証と制約
-------------
今回追加7項目を含む全265項目のPCテスト、MicroPython WASM 1.28.0による全HOST手順の模擬実行、
mpy-cross 1.29.0による配布33ソースのArm向けコンパイルの結果を同梱します。
レジスタモデルでミュート中のキー/音量/音程の維持、進行時刻、ゲート指示と出力レベルの一致、
1poll最大1レジスタ、ミュート中のSTOP/リース中止、非再生中の拒否、破損状態や転送例外、時刻周回、
ネイティブ期限監視と安全停止を検証します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
既存31ソース、GPIO割り当て、I/O v1.1、FM変換、PIO/DMA/I2S、ゲイン、1秒リース、100ms予約遅延上限、処理期限は維持します。
実機での音質/可聴時刻は未確認です。固定9音/500ms/3回の診断であり、複数の独立旋律や長時間キュー、
楽曲BIN、USB-MIDI、24時間運転の検証は含みません。
