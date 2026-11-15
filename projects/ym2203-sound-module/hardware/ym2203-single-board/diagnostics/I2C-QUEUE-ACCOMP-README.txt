YM2203C Rev C - 予約旋律+持続和音の4音再生診断 v1
2026-11-12

実機結果（2026-11-12）
----------------------
以下の伴奏付き予約診断は実機合格しました。FM/SSGの旋律と持続和音、最後の全音自動消音、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しました。
クリック音の有無は今回の報告では明示されていません。
BUS HEAP全6行bytes=0、2162ブロック、ピーク2976、最大変換1119us、deadline misses=0。
max_poll_us=4753、max_idle_poll_us=716、SIX I2C jobs=6 writes=24、lease_expirations=1。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=62 max_write_us=4113。
ACCOMP run_masks=[57,15,15] applied=0、最終ACK99=(69+15+15)&255、stale_flushes=0。
受信429=1467-1038、送信894=3642-2748も一致。以下の実機未確認の記載は配布時点のものです。
次はI2C-QUEUE-ACCOMP-STOP-README.txtの、伴奏付き途中STOPと同じ譜面の再開始です。

直前の実機結果
--------------
予約途中STOPと再開始は実機合格しました。FM/SSGの途中停止と4秒無音、FM先頭から全9音、
左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認しています。
BUS HEAP全6行0bytes、2244ブロック、ピーク992、最大変換1116us、期限超過0、max_poll_us=4763、max_idle_poll_us=676。
QUEUE runs=3 completed=1 aborted=2 events=15 pitch_writes=30 partial_cancels=0 max_late_ms=58 max_write_us=4123。
SIX I2C jobs=5 writes=6、最終ACK84、期限消音0回、stale flush 0、受信354=1392-1038、送信807=3555-2748も整合。

次は、予約で進む旋律1音に、反対側の音源の持続和音3音を重ねる試験です。
旋律は「ドレミファソファミレド」を500ms周期で進め、伴奏は同じドミソを保持します。
固定9音・3回の診断仕様です。正式な多チャンネル予約APIの変更ではありません。新試験は実機未確認です。

1. 配線と追加ファイル
---------------------
前回合格した配線/給電/音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

次の2ファイルを各Picoの最上位へ追加します。
  Rev C：target/rev_c_i2c_queue_accomp_target.py
  HOST ：host/rev_c_i2c_queue_accomp_host.py
前回の28ソースはすべてそのまま残します。rev_c_i2c_queue_target.py/host.py等もimportに使います。
未保存ならZIPのtarget/全16ファイルをRev C、host/全14ファイルをHOSTへ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

2. 実行
-------
1) 両側を停止して新しい2ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cでrev_c_i2c_queue_accomp_target.pyを実行します。
   YM2203 Rev C / staged I2C accompanied queue target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_accomp_host.pyを実行します。
   YM2203 Rev C / I2C accompanied queue HOST v1 / OTHER Pico only
6) 従来の無音検査6段階、BUS HEAP6行、START/KEEP、譜面登録の後、演奏します。全体は約1分です。

3. 聞こえる音
-------------
  1 FM CH1の高い旋律「ドレミファソファミレド」（C4～G4）+ SSG A/B/Cの低いドミソ（C3/E3/G3）
  2 SSG Aの低い旋律「ドレミファソファミレド」（C3～G3）+ FM CH1/2/3の高いドミソ（C4/E4/G4）
  3 2と同じ組み合わせを再開始し、KEEPを送らず約1秒で旋律/伴奏の全4音を自動消音
1と2は各9音を完奏して自動停止します。その後HOSTのSTOPと1秒無音を挟みます。
3は最初の数音で中止し、その後も無音が続くことを確認します。
左右は同じ音です。旋律だけが音程を変え、伴奏3音は持続することを確認してください。
歪み/予定外の音切れ/気になるクリック音、正常終了と最後の全音消音も確認します。

従来の音色・音量を使います（FMキャリアTL64、SSG固定レベル7）。
伴奏は出力をミュートした準備中に設定し、既存の12ブロックのI2S準備後に旋律をキーオンします。
FM経路には取り込み/I2S待ち時間があるため、旋律/伴奏の可聴開始をサンプル単位で同期する試験ではありません。
終端は旋律から順に全音源をキーオフし、最後のFM出力を流す135msの待ち時間の後にゲートを閉じます。

4. 制御方式
-----------
今回の診断用署名はRCQAC01!です。旧単音ターゲットと取り違えると発音前に停止します。
命令番号/登録譜面は旧9音キューと同じで、PLAYの意味だけを伴奏付きへ拡張します。
  PLAY FM（0xA6）：FM1旋律+SSG A/B/Cの和音、発音マスク57（0x39）
  PLAY SSG（0xA7）：SSG A旋律+FM1/2/3の和音、発音マスク15（0x0F）
0x28に予定マスクを置き、HOSTは再生開始時に照合します。再生中も短い読み出しで実マスクを確認します。
曲中は旋律の音程だけを更新し、伴奏の音程/キー/音量を変更しません。
登録データ9音は従来どおり読み戻して照合し、再生中の音符送信は行いません。

4音の準備/終了は1回の音声処理につき最大1レジスタずつ行います。
appliedは実際にキーオン/音量設定済みのビットを保持し、準備中/終了途中のSTOP・期限切れでも残りを停止します。
通信期限ではまず出力ゲートを閉じ、全チャンネルの停止を分割実行します。自動的に残りの音を再開しません。
従来の1秒リース、100msの予約遅延監視、FM処理期限、ゲイン、GPIO、PIO/DMA/I2Sは維持します。
準備/終了時の伴奏処理が増えても、旋律の時刻は開始+n*500msを使い、前イベントの遅延を累積しません。

5. ログと期待値
---------------
HOSTは次のように表示します。
  ACCOMP PLAY / FM melody + SSG low chord ...
  PASS: accompanied FM melody; KEEP=... held_mask=57 checks=...
  ACCOMP PLAY / SSG melody + FM high chord ...
  PASS: accompanied SSG melody; KEEP=... held_mask=15 checks=...
  ACCOMP LEASE / SSG melody + FM chord without KEEP ...
  PASS: melody and all three companions lease-muted and stayed stopped

Rev Cの期待値:
  SIX I2C: jobs=6 writes=24 pending=-1 applied=0
  QUEUE: runs=3 completed=2 aborted=1 events=... pitch_writes=... partial_cancels=0 max_late_ms=0～100
  QUEUE RUN 1: voice=0 state=4 notes=9、500ms周期の時刻
  QUEUE RUN 2: voice=3 state=4 notes=9、500ms周期の時刻
  QUEUE RUN 3: voice=3 state=5 notes=P、以降の時刻は-1
  ACCOMP: run_masks=[57,15,15] applied=0 ...
  lease_expirations=1、deadline misses=0
events=18+P、pitch_writes=2*(18+P)です。HOSTのEXPECTED QUEUEが具体値を表示します。
声の準備/停止が増えるため、SIX I2Cのwritesは旧単音試験の6から24になります。
両方の組み合わせにFMが含まれるので、どちらも全音源のキーオフ完了後135ms以上待って終了します。
QUEUE RUNのnote_off_msは旋律のキーオフ時刻、end_msは全音源停止と出力待ちを終えた時刻です。
共通のQUEUE表示にあるvoiceは旋律チャンネルを示します。実際の4音構成はACCOMPのマスクで確認します。
2回の完奏中に送ったKEEP合計をKとすると、最終ACKは(69+K)&255です。
LAST CONTROL STATEは[HOST期待の最終ACK,7,0,0]です。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMPを含む）と、2種類の旋律+持続和音、左右、音質、
正常終了、最後の全音消音と無音継続、HOST PASS・SAFE・DONEを報告してください。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。
共通DONEのall nine sound sectionsという文言によらず、今回は上記3回の再生です。

6. 検証と制約
-------------
全252項目（今回追加8項目）のPCテストが合格しました。独立11.25ms通信モデルで4音のキー/音量/音程/ゲート、
伴奏の保持、1poll最大1レジスタ、2回の9音と時刻、準備中/終了途中のSTOP・期限切れ、全音源の停止を確認しました。
マスク破損/転送例外/過剰遅延/識別子違い、時刻周回、ネイティブ期限監視と例外時の安全停止も検証しています。
MicroPython WASM 1.28.0で全HOST手順を模擬実行し、mpy-cross 1.29.0で配布30ファイルをArm向けにコンパイルしました。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
既存28ソースと音声コアは変更していません。今回の実機の聞こえ方と時刻は未確認です。
独立した複数旋律の登録、厳密な可聴同期、可変長/長時間キュー、楽曲BIN、USB-MIDI、24時間運転は後続の対象です。
