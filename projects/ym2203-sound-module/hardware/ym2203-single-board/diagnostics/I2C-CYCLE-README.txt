YM2203C Rev C - FM/SSG・独立ミュート切り替え反復診断 v1
2026-11-11

目的と確認済みの範囲
--------------------
直前の3分間FM+SSG/I2C通信耐久試験は、実機で左右正常、歪み/音切れなし、
最終自動消音、HOST PASS・SAFE/DONEまで合格しました。
主試験180045ms、KEEP 640回、ACK周回2回、HOSTの最大応答確認92ms。
連続受信16854ブロック、ピーク4064、最大変換1118us、期限超過0、max_poll_us=11796。
受信2135/送信3048、stale flush 0、最終ACK175はHOSTの期待値と一致しました。
HOST全体の書き込み3173-起動段階1038=2135、読み取り5796-起動段階2748=3048です。

今回は同じ連続FM変換とI2C通信を保ち、発音モード・独立ミュート・STOPを10周切り替えます。
新しく追加するのは操作側のrev_c_i2c_cycle_host.pyだけです。
Rev C側v1.3と、前回までの17ファイルは変更しません。GPIO・回路・音量・期限監視も同じです。
反復試験は実機で全10周・80区間合格しました。左右正常、歪み/予定外の音切れ/気になるクリック音なし。
主試験180388ms、640命令、ACK周回2回、最大モード応答確認91ms。最後の自動消音とHOST PASS・SAFE/DONEも確認。
16780ブロック、最大変換1118us、期限超過0、期限消音1回、stale flush 0。最終ACK173も一致しました。
受信2289=HOST全体3327-起動1038、送信3680=6428-2748も整合しています。

1. 接続とファイル
-----------------
配線・給電は前回合格した構成のままです。
  Rev C JHOST 1 GND -> 操作側Pico GND（物理3番など）
  Rev C JHOST 2 SDA -> 操作側GP0（物理1番）
  Rev C JHOST 3 SCL -> 操作側GP1（物理2番）
3.3V I2C、0x42、10kHzハードウェアI2C0、R1/R2各4.7kΩプルアップを使用します。
電源線同士はつなぎません。配線変更時は両側電源OFF、テスト中は両側に給電します。
JLINE -> AMS-22 LINE IN、ヘッドホン -> AMS-22、両方の音量を低めにしてください。
AMS-22は別バッテリー給電、PC USBは外し、DIRECT MONITOR=ON、LOOPBACK=OFFです。

前回一式がPico内に保存済みなら、host/rev_c_i2c_cycle_host.pyだけを操作側の最上位へ追加します。
今回のスクリプトは、前回のrev_c_i2c_endurance_host.pyもimportして使います。
未保存の場合は、ZIPのhost/の全7ファイルを操作側へ保存してください。
  rev_c_i2c_host_check.py
  rev_c_i2c_ssg_host.py
  rev_c_i2c_fm_host.py
  rev_c_i2c_isolation_host.py
  rev_c_i2c_fm_staged_host.py
  rev_c_i2c_endurance_host.py
  rev_c_i2c_cycle_host.py    今回追加
ZIPには再導入用としてtarget/の11ファイルも含みます。Rev C側の更新は不要です。
main.py / boot.pyには保存しません。UF2の書き直しは不要です。

2. 実行
-------
1) 両側を停止して新しいファイルを転送します。
2) 両方のPico USBとJPOWERをすべて外し、5秒待ってJPOWER -> 両方のUSBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev C側で従来のrev_c_i2c_fm_staged_target.py v1.3を実行し、PHASE 0 READYを待ちます。
5) 操作側でrev_c_i2c_cycle_host.pyを実行します。
   YM2203 Rev C / I2C live FM+SSG mode-cycle HOST v1 / OTHER Pico only
6) 従来の6段階の無音通信検査と、連続受信開始前後の通信検査後、5秒待って発音します。
   以後は自動です。準備を含め約4分が目安です。

3. 音の流れ
-----------
次の8区間を各約2秒、10周します。全80区間です。
  1 FM ONLY       高い約440HzのFMだけ
  2 SSG ONLY      低い約220HzのSSG Aだけ
  3 FM + SSG      両方
  4 DAC MUTE      低いSSGだけ残る
  5 DAC RESTORE   両方へ戻る
  6 LINE MUTE     両方消える（内部の発音と変換は継続）
  7 LINE RESTORE  両方へ戻る
  8 STOP          両音源を停止して無音（変換は継続）
覚え方: 高い音 -> 低い音 -> 両方 -> 低い音 -> 両方 -> 無音 -> 両方 -> 無音。

10周終了後、FM+SSGをもう一度短く鳴らし、KEEPを止めて約1秒で自動消音し、終了します。
LINE MUTEとSTOPの無音区間、最後の短い発音は意図したものです。
I2Sバッファ等による短い切り替え遅延があります。各区間の定常部分の聞こえ方と、
予定にない音切れ、歪み、切り替え時の気になるクリック音があれば報告してください。
背景の小さなサー音は、テスト音の有無とは分けます。

4. ログと報告
-------------
HOSTだけが区間名と各周の結果を表示します。Rev C側は連続変換中には途中ログを出しません。
  CYCLE 1/10 SECTION 1/8 / FM ONLY ...
  ...
  CYCLE 1/10 PASS / elapsed_ms=... commands=... ack=... wraps=... max_mode_command_ms=...
  ...
  CYCLE 10/10 PASS ...
  CYCLES COMPLETE / rounds=10 commands=... wraps=... max_mode_command_ms=...
commandsは反復区間中のモード命令とKEEPの累計です。wrapsは同区間中にACKが255から0へ戻った回数です。
各周で8回のモード命令を送り、発音/ミュート中は従来の2秒holdがKEEPを送ります。
STOP中はKEEPを送りません。ACKの1回以上の周回を検査します。
max_mode_command_msはモード変更命令の応答確認時間で、40ms待ちや通信時間を含みます。
前回のKEEP応答時間やRev Cのmax_poll_us・音声変換時間とは別の値です。

新しいモードを送る前と各区間後にも、ACK・最後の命令・モード・期限フラグを読み戻します。
意図しない期限消音や状態不一致を検出した場合、発音を再開せず例外で停止します。
通信異常時に同じモード命令を自動再送しません。
HOSTの8bit ACK確認は従来のRemote、2秒holdとKEEPも従来の処理を使います。
hold前後のACK差を集計します。2秒のholdのKEEPは最大10回なので、この間の未観測の256回周回はありません。

末尾でHOST PASS、HOST SAFE、Rev CのSAFE・DONEを確認します。
  EXPECTED TARGET FINAL ACK: n / FINISH=7 mode=0 lease_flag=0
このnとRev Cのcommands=およびLAST CONTROL STATE先頭バイトが一致します。
Rev Cのcommands=は8bitカウンターで、累計ではありません。LAST CONTROL STATEは[ACK,7,0,0]です。
lease_expirationsは、最後の意図的な1回だけが期待値です。
Rev CのDONEに含まれるall nine sound sectionsは共通ターゲットの案内です。今回は80区間と最後の自動消音を報告します。

両側のログ全文と、10周とも上の順序で聞こえたか、左右、独立ミュート、歪み/予定外の音切れ、
クリック音、最後の自動消音を報告してください。
失敗時はRev C側もCtrl+Cで止め、LIVE I2CからSAFE・例外末尾までの追加ログも保存します。
再試験は両側を初期化して行い、HOSTだけを途中から再開しません。

5. 検証と制約
-------------
追加はHOSTの1ファイルだけです。前回までのターゲットと6個のHOSTファイルは同一です。
40msのHOST待機、1秒のリースと応答タイムアウト、ターゲットの5分上限、ネイティブ処理と期限監視を維持します。
モード切り替えの反復を検査しますが、I2C高速化、任意レジスタ、音色/音程編集、6音同時発音、
24時間運転、USB-MIDIや正式APIを検査するものではありません。メモリ使用量も今回測定しません。

PCの139項目（今回追加6項目）で、独立した11.25ms周期モデルを通した80区間と全状態、
ACK周回、意図的な最終期限消音、ticks_msの周回、意図しない期限消音後に再発音しないこと、
各種例外時に命令を再送せず後続区間へ進まないことを検査します。
MicroPython WASMでは実際の全HOST手順を、模擬時計・通信・音源で実行します。
公式MicroPython v1.29.0 mpy-crossで追加HOSTをArm向けにコンパイルします。
これらは実機の音、PIO/DMA/I2S/I2Cの動作や電気的な通信の検証を代替しません。
反復試験の実機合格は上記のとおりです。配布済みZIPと当時のvalidation.jsonは変更しません。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
