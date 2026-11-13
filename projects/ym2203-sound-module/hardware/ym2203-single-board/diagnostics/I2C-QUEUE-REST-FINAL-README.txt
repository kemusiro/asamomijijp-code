YM2203C Rev C - 組立・I2C実現性確認の最終総合試験 v1
2026-11-13

1. 残り件数と終了条件
--------------------
実施前の計画では、今回を含め残り1件と定めた。現在は合格済みで残り0件。
COMMISSIONING-CHECKPOINT.txtに対象と終了条件を固定した。
この試験が実機で合格したら、この段階の追加診断を終了し、常用ファームウェアの設計・実装へ進む。
USB-MIDIや汎用楽曲再生、長時間運転などの検証は、実装後の別工程で計画する。

前回の休符試験は実機合格。有音18枠/休符9枠、伴奏の持続と再発音、左右正常、歪み/予定外の音切れなしを確認した。
BUS HEAP全6行0bytes、2428ブロック、ピーク2976、最大変換1119us、deadline misses=0。
QUEUE runs=3 completed=3 aborted=0 events=27 pitch_writes=36 partial_cancels=0 max_late_ms=53 max_write_us=4062。
SIX I2C jobs=5 writes=42、期限消音0回、最終ACK110、stale_flushes=0、受信470=1508-1038、送信994=3742-2748も整合した。
2026-11-13 実機結果：合格（以下の手順は実施時の記録）。
ユーザーが休符中STOP後4秒無音、先頭からの再演奏、通信休止による自動消音を確認。
左右正常、歪み/予定外の音切れなし。HOST PASS・SAFE・DONE、deadline misses=0。
QUEUE runs=3 completed=1 aborted=2 events=17 pitch_writes=22 partial_cancels=0。
REST tones=11 rests=6 rest_key_offs=6 resume_key_ons=4、SIX jobs=6 writes=32。
lease_expirations=1、2526blocks、最大変換1118us、ACK88、受信390/送信898も整合した。
この段階の診断は終了。../firmware/README.txtの常用ファームウェア実装へ移行する。
過去に配布済みのZIPとそのvalidation.jsonは当時の記録として変更しない。

2. 配線と追加ファイル
---------------------
配線・給電・音量は前回合格時のまま。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、Rev Cの4.7kΩプルアップ。電源線同士はつながない。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

HOST Picoの最上位へ次の1ファイルを追加する。
  host/rev_c_i2c_queue_rest_final_host.py
既存38ソースを残す。rev_c_i2c_queue_rest_host.pyとその依存ファイルもimportする。
未保存ならZIPのtarget/全18ファイルをRev C、host/全21ファイルをHOSTの最上位へ保存する。
ターゲットは前回と同じ。main.py / boot.pyへの保存やUF2更新は不要。

3. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存する。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続する。
3) 各ThonnyをそれぞれのPicoへ接続する。
4) Rev Cで前回と同じrev_c_i2c_queue_rest_target.pyを実行する。
   YM2203 Rev C / staged I2C queued melody rest target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_rest_final_host.pyを実行する。
   YM2203 Rev C / I2C rest STOP-replay-lease final HOST v1 / OTHER Pico only
6) 既存の無音検査6段階、BUS HEAP6行、START/KEEPと登録の後に演奏する。全体は約1分。

4. 聞こえる音と確認内容
-----------------------
登録譜面は前回と同じ「ド・ミ・休・ソ・休・ミ・レ・休・ド」。
  1 FM旋律+SSG低音和音を開始し、最初の休符でSTOPする。
    ド・ミの後に旋律が休み、STOPで残っていたSSG伴奏も消え、4秒間全音無音になる。
  2 同じ登録譜面をPLAYだけで先頭からFM旋律+SSG和音として完奏する。
    有音6枠と休符3枠、伴奏の持続、全音停止と1秒無音を確認する。再登録/RESTORE/START再送はない。
  3 SSG旋律+FM高音和音を開始し、最初の休符でHOST通信を1.8秒間休止する。
    配線を抜く操作は不要。通信期限が切れるまでは演奏が進み、途中のソが聞こえる場合がある。
    リース中止で旋律と伴奏がすべて消え、その後4秒間全音無音が続く。
    読み出し再開と最後のSTOPによる期限フラグ解除だけでは演奏が再開しない。

FMのリリースや取り込み/I2S経路の遅延があるため、可聴の切り替え時刻には多少の差がある。
左右、歪み/予定外の音切れ/気になるクリック音、最後の無音も確認する。

5. ログの期待値
---------------
  QUEUE: runs=3 completed=1 aborted=2
  QUEUE RUN 1: voice=0 state=5 notes=3（最初の休符で中止）
  QUEUE RUN 2: voice=0 state=4 notes=9（全枠完走）
  QUEUE RUN 3: voice=3 state=5 notes=P（通常4～5、残りは未実行）
  ACCOMP: run_masks=[57,57,15] applied=0
  SIX I2C: jobs=6 writes=HOST表示の期待値（通常32）pending=-1 applied=0
  lease_expirations=1、deadline misses=0、HOST PASS・SAFE・DONE

総eventsは3+9+P。有音枠数T、休符数R、休符後の再キーオン数KはHOSTが登録譜面と実行済み進行から計算する。
  events=T+R、pitch_writesは2*T～2*T+4、partial_cancelsは0～2
  REST QUEUE: tones=T rests=R rest_key_offs=R resume_key_ons=K pair_step=0
  SIX I2C writes=24+2*K
通常はT=11、R=5または6、K=4となる。進行位置はI2Cとリースのタイミングに依存するので、HOSTの具体的な期待値と照合する。
pitch_writesの上積みは中止時に未完了だった音程2レジスタ/再キーオン待ちの書き込みによるもの。
QUEUEのnotes/eventsには休符も含む。GATE NOTESは指示状態で、実行済みは休符中も3、未実行は255。
2回目のREST SLOTSは全9枠[0,2,5,4,5,2,1,5,0]、マスク[57,57,56,57,56,57,57,56,57]となる。
KEEP合計をNとすると最終ACKは(59+N)&255。LAST CONTROL STATEは[HOST期待ACK,7,0,0]。
ゲート/マスク/各カウンタはソフトウェア状態であり、アナログ出力やピン電圧の測定値ではない。

停止直後と4秒後に状態、6音程、登録譜面、進行位置、ゲート0、累積休符/有音数を読み戻す。
3回目の通信休止区間はKEEP/STOP/読み出しを一切送らない。断線やバス固定を模擬する試験ではない。
最初の休符を見逃した場合や状態不一致は再演奏せず失敗として終了し、既存リースが停止の後段となる。

両側のログ全文（BUS HEAP/QUEUE RUN/ACCOMP/QUEUE GATES/GATE NOTES/REST QUEUE/REST SLOTS、SAFE/DONEまで）と、
休符中STOP後4秒無音、先頭からの全9枠再演奏、通信休止後の全音自動消音と4秒無音、左右と音質を報告する。
異常時は再試行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存する。

6. 検証と残る別工程
-------------------
今回追加6項目を含む全298項目のPCテスト、MicroPython WASM 1.28.0での全HOST手順の模擬実行、
mpy-cross 1.29.0で配布39ソースのArm向けコンパイルの結果を同梱する。
休符中STOPの実キー/音量/マスク、4秒間の追加音源書き込みなし、1.8秒間のHOST転送なし、
同譜面の再演奏、リース中止と累積数照合、1poll最大1レジスタ、破損状態/転送例外時の非再試行と停止、時刻周回を検証する。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
本診断では既存38ソース、休符ターゲット、GPIO、音声変換、音量、各期限は変更しなかった。実機結果は上記のとおり合格。
この試験合格後は初期実現性確認を閉じる。常用ファームウェア、正式API、汎用楽曲再生、USB-MIDI、長時間運転は別工程で扱う。
