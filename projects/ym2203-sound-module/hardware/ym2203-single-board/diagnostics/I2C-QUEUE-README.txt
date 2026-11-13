YM2203C Rev C - I2C登録による短い予約演奏診断 v1
2026-11-12

直前の実機結果
--------------
連続音程変更3分耐久v1.1は実機合格しました。BUS HEAP全6行0bytes、左右正常、音質正常、
最終自動消音とHOST PASS・SAFE・DONEを確認しています。
181123ms/100グループ/600音程変更/700命令、ACK周回2回、最大状態照合226ms。
17240ブロック、ピーク2976、最大変換1119us、期限超過0、max_poll_us=4542、max_idle_poll_us=514。
SIX I2C jobs=7 writes=24 max_write_us=4075 pending=-1 applied=0 prime_left=0。
VOICE PITCH updates=612 writes=1224 max_write_us=4206 cancelled=0 pending=-1 step=2。
最終ACK247、期限消音1回、stale flush 0、受信3168=4206-1038、送信13156=15904-2748が一致しました。

次は、音符を先にI2Cで登録し、Rev C側の時刻で切り替える短い予約演奏です。
最初の検証として9音・500ms間隔・単音に限定します。FM単独、SSG単独の順に演奏します。
再生中はHOSTが音符を送らず、間隔を変えながらKEEPと状態確認だけを行います。
最後にKEEPを止め、通信期限で予約演奏全体が中止され、その後も発音が再開しないことを確認します。
今回の予約演奏は実機で合格しました。FM/SSG各9音の一定間隔、左右正常、音質正常、最終中止と無音継続を確認。
BUS HEAP全6行0bytes、2128ブロック、ピーク992、最大変換1117us、期限超過0、max_poll_us=4954、max_idle_poll_us=638。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=58 max_write_us=4116。
FMキーオフ4556ms/終了4700ms、SSG4557msで終了。最後のSSGは2音で中止し、以降の予約音なし。
SIX I2C jobs=6 writes=6、最終ACK102、期限消音1回、stale flush 0、受信416=1454-1038、送信890=3638-2748も整合。
次はI2C-QUEUE-STOP-README.txtです。診断用の限定仕様で、正式な予約API/楽曲BIN形式の変更ではありません。

1. 配線とファイル
-----------------
配線・給電・音量は前回合格したままです。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ON。

次の2ファイルをそれぞれのPicoの最上位に追加します。
  Rev C：target/rev_c_i2c_queue_target.py
  HOST ：host/rev_c_i2c_queue_host.py
前回の全25ヘルパーはそのまま残します。今回もI/O v1.1と無音ヒープ検査を使います。
未保存の場合はZIPのtarget/全15ファイルをRev C、host/全12ファイルをHOSTへ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

2. 実行
-------
1) 両側を停止して、新しい2ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cでrev_c_i2c_queue_target.pyを実行します。
   YM2203 Rev C / staged I2C nine-note queue target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_queue_host.pyを実行します。
   YM2203 Rev C / I2C nine-note queue HOST v1 / OTHER Pico only
6) 従来の無音検査6段階、BUS HEAP6行、START/KEEPの後に演奏します。全体は約1分が目安です。

3. 聞こえる音
-------------
  1 FM CH1のみで「ドレミファソファミレド」（C4～G4）、1回
  2 SSG Aのみで「ドレミファソファミレド」（C3～G3）、1回
  3 SSG Aを再度開始し、KEEPを送らず、開始命令から約1秒で自動消音
1と2は各音500msを基準に合計約4.5秒です。再生後は自動的に音源を停止し、無音になります。
HOSTもSTOPを確認し、1秒の無音を挟んで次へ進みます。
最後の3は通常は最初の数音だけです。消音後に待機して、後続の予約音が鳴らないことも確認します。
左右は同じ音です。音程、リズム、左右、歪み/予定外の音切れ/クリック音、自動終了と最後の中止を確認してください。

先頭音は、音源を止めたまま音程を設定し、無音のI2S準備を済ませてからキーオンします。
これにより先頭のドだけを先に鳴らして準備時間を足すことを避けます。
FMの末尾はキーオフ後135ms待ち、既存I2S出力を流してからゲートを閉じます。
FM出力には既存の取り込み/I2Sキューの遅延があるため、ログの時刻は可聴信号の到達時刻ではありません。

4. 診断用の予約方式
-------------------
署名はRCQUE01!です。旧ターゲットとの組み合わせ違いは発音前に検出します。
0x20へ送る1バイト命令を使います。
  0x00 STOP     予約中なら中止、音源を停止。期限フラグを解除
  0x06 KEEP     HOSTの通信期限を更新。予約中も受け付ける
  0x07 FINISH   予約を中止して診断を終了
  0x08 START    従来の連続FM取り込みを開始
  0xA0～0xA4    ド/レ/ミ/ファ/ソを1音ずつ末尾へ登録
  0xA5 CLEAR    停止中に登録を空にする
  0xA6 PLAY FM  9音をFM CH1で1回再生
  0xA7 PLAY SSG 9音をSSG Aで1回再生
HOSTはCLEAR後に9音を登録し、0x30～0x38の読み戻しで譜面を照合します。
容量超過、9音未満での開始、再生中の追記/再開始、未START、期限切れのままの開始は拒否します。
診断は最大3回の再生で、時刻記録用RAMを開始前に確保します。実用の可変長キューは後続の設計対象です。

再生中は各音の時刻を開始時刻+n*500msで決めます。前の処理時間を次の基準時刻へ加算しません。
従来どおり1回の音声処理につき最大1レジスタを更新し、2回の書き込みで音程が確定します。
処理の粒度は約11.25msで、I2Cサービス中はGPIO書き込みを待ちます。
予定から100msを超えて遅れた場合は演奏を止め、後続をまとめて追いかけて発音しません。
従来のFM期限監視・音量監視はそのままです。この100msはFMの処理期限を延ばすものではありません。
再生中の音符進行はACKを増やさず、リースも更新しません。リースを更新するのはHOSTからのKEEPだけです。
途中のSTOP/通信期限切れでは予約を取り消し、出力を閉じ、分割処理でチップの発音も停止します。
通信が戻っても、自動で残りの予約を再開しません。

0x10～0x1Bの従来12バイトに、次の4バイトを追加します。
  0x1C 登録数、0x1D 予約状態、0x1E 発音済み音数、0x1F 選択voice（FM=0、SSG=3、未選択=255）
予約状態は0=登録待ち、1=無音準備、2=再生、3=FM出力待ち、4=正常終了、5=中止です。
再生中のHOSTは短い状態読み出しと40msのアイドル時間を挟み、音程処理の機会を確保します。
16バイト全体の照合は停止中/終了後に行います。

5. 終了ログと報告
-----------------
Rev Cは取り込み停止後に時刻を表示します。
  QUEUE: runs=3 completed=2 aborted=1 events=... pitch_writes=... partial_cancels=0 max_late_ms=... max_write_us=...
  QUEUE RUN 1: voice=0 state=4 notes=9 times_ms=[0,...] note_off_ms=... end_ms=...
  QUEUE RUN 2: voice=3 state=4 notes=9 times_ms=[0,...] note_off_ms=... end_ms=...
  QUEUE RUN 3: voice=3 state=5 notes=... times_ms=[0,...,-1,...] note_off_ms=-1 end_ms=...
times_msはキーオンを0とした音源レジスタの処理完了時刻で、目標は0/500/1000/.../4000msです。
最初の2回は各9音が完了し、予定からの遅れは0～100ms以内であることを確認します。
note_off_msは約4500ms、FMのend_msはそこから135ms以上後、SSGのend_msはキーオフ直後です。
3回目は中止のため、未実行スロットを-1で残します。

HOSTのEXPECTED QUEUEとEXPECTED TARGET FINAL ACKに、実際の終了期待値を表示します。
  runs=3 completed=2 aborted=1
  events=18+最後に鳴った音数P、pitch_writes=2*(18+P)
  partial_cancels=0（この実行手順での期待値）
  SIX I2C: jobs=6 writes=6 pending=-1 applied=0
  lease_expirations=1、deadline misses=0
最初の2回のKEEP合計をKとすると最終ACKは(69+K)&255です。
最終LAST CONTROL STATEは[最終ACK,7,0,0]で、予約状態5は最後の意図した中止を示します。
共通DONEのall nine sound sectionsという文言によらず、今回は2回の音階と短い中止テストです。

両側のログ全文（BUS HEAPとQUEUE RUNの時刻も含む）と、FM/SSGの音階・リズム・左右・音質、
正常終了と最後の自動消音、その後の無音継続を報告してください。
異常時は再実行せず、Rev CもCtrl+Cで止めてSAFEと例外末尾まで保存します。

6. 検証と制約
-------------
全238項目（今回追加9項目）のPCテストが合格しました。独立11.25ms通信モデルで、
譜面登録/読み戻し、HOSTからの再生中の音符送信なし、2回の9音と時刻、キー/音量の分離、
STOP/リースによる予約中止、未完了音程の取消、遅延時の停止、容量/3回制限、状態不一致/転送異常を確認しました。
ネイティブ期限監視と実GPIO操作のモデルも使い、通常の分割処理と過負荷/例外時の安全停止を確認しました。
MicroPython WASM 1.28.0でも全HOST手順を模擬実行し、mpy-cross 1.29.0で配布27ファイルをArm向けにコンパイルしました。
検証ログとSHA-256一覧を同梱します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
GPIO/音量/音色/PIO/DMA/I2S/既存ヘルパー25ファイル/1秒リース/40ms ACK待機/5分上限は変更しません。
上記条件で予約演奏の音質とレジスタ時刻を確認済みです。ログは可聴音の時刻を直接測定していません。
サンプル単位の同期、任意時刻/音域、複数チャンネルの予約、長い曲、可変長キュー、楽曲BIN、USB-MIDIは後続の対象です。
