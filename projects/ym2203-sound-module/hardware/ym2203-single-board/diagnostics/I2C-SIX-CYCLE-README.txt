YM2203C Rev C - 6音・独立ミュート切り替え10周診断 v1
2026-11-12

直前の実機結果
--------------
6音+I2C通信の3分耐久は実機合格です。主試験180156ms、KEEP517回、ACK周回2回。
左右正常、歪み/音切れ/気になるクリック音なし、最終自動消音とHOST PASS・SAFE・DONEを確認。
HOST最大ACK確認92ms、追加状態照合までの最大時間160msでした。
16901ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4541、max_idle_poll_us=468。
SIX I2C jobs=7 writes=24 max_write_us=4291 pending=-1 applied=0 prime_left=0。
最終ACK52がHOST期待値および(517+47)&255と一致し、期限消音1回、stale flush 0。
受信2286=HOST全体3324-起動1038、送信5680=8428-起動2748も整合しています。

次は設定を固定したままの耐久から、音源切り替え・独立ミュート・STOPの反復へ進みます。
固定の8区間を各約2秒で10周、全80区間を確認します。最後に6音の短い自動消音を行います。
Rev Cのターゲット、音源値、音量、GPIO、ネイティブ変換は変更しません。
今回の6音切り替え10周診断も実機で全80区間合格しました。
左右正常、独立ミュート/STOP/最終自動消音、HOST PASS・SAFE・DONEを確認し、
歪み/予定外の音切れ/気になるクリック音はありませんでした。
18268ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4568、max_idle_poll_us=475。
SIX I2C jobs=45 writes=192 max_write_us=4300 pending=-1 applied=0 prime_left=0。
主試験640命令、ACK周回2回、最大設定変更ACK確認327ms。
最終ACK173=(640+45)&255、期限消音1回、stale flush 0。
受信2466=3504-1038、送信4874=7622-2748も一致しています。
次はI2C-SIX-RECOVERY-README.txtの通信一時停止・復帰診断です。

1. 配線と追加ファイル
---------------------
配線・給電・音量は前回合格したままです。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー、PC USBなし、DIRECT MONITOR ONです。

前回のファイルを残し、次の1ファイルだけをHOST Picoの最上位へ追加します。
  host/rev_c_i2c_six_cycle_host.py
既存のrev_c_i2c_six_host.pyをimportします。このヘルパーもHOST内に残してください。
Rev Cは従来のrev_c_i2c_six_target.pyをそのまま実行し、更新は不要です。
未保存の場合はZIPのtarget/全13ファイルをRev C、host/全8ファイルをHOSTへ保存します。
前回の20ファイルは変更していません。以前の耐久HOSTもZIPに含みますが、今回は実行しません。
main.py / boot.pyには保存しません。UF2更新は不要です。

2. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cでrev_c_i2c_six_target.pyを実行します。
   YM2203 Rev C / staged I2C six-voice target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_six_cycle_host.pyを実行します。
   YM2203 Rev C / I2C six-voice mode-cycle HOST v1 / OTHER Pico only
6) 従来の起動検査、START/KEEP確認後、5秒待って発音します。
準備を含め約4分が目安です。主試験の時間には切り替え待ちと通信時間も加わります。

3. 音の順序
-----------
次の8区間を各約2秒、10周します。
  1 FM CHORD      高いドミソ C4/E4/G4
  2 SSG CHORD     低いドミソ C3/E3/G3
  3 SIX VOICES    FM+SSGの両和音
  4 DAC MUTE      SSGの低い和音だけ残る
  5 DAC RESTORE   6音に戻る
  6 LINE MUTE     両方の和音が消える（内部発音は継続）
  7 LINE RESTORE  6音に戻る
  8 STOP          全音源とゲートを停止、無音

音源マスクを変更するときは、既存の分割設定と出力準備のため短い無音を挟みます。
LINE MUTE/STOPの無音も意図したものです。各区間の定常部分の聞こえ方を比較してください。
新しい音程/音色/音量設定はなく、以前合格した固定6音のままです。

10周終了後は、同じ6音を短く鳴らし、KEEPを止めて約1秒で自動消音・全音源の停止を確認します。
予定外の音切れ、歪み、気になるクリック音がないかも確認してください。

4. 状態確認とログ
-----------------
各区間の前と後に[ACK,最後の命令,モード,期限フラグ0,発音マスク,処理中0]を照合します。
直前の区間で意図しない期限消音が起きていたら、STOPや次のマスクで状態を消す前に検出して停止します。
通信例外や不一致では命令を再送せず、後続区間にも進みません。
発音中/ミュート中の保持には従来の2秒holdとKEEPを使い、STOP中は2秒待機します。
ACK差を集計し、少なくとも256命令と1回以上のACK周回を確認します。
2秒holdのKEEPは最大10回なので、集計区間中に256回の未観測周回はありません。

HOSTだけが区間名と各周の結果を表示します。
  SIX CYCLE 1/10 SECTION 1/8 / FM CHORD ...
  ...
  SIX CYCLE 1/10 PASS / elapsed_ms=... commands=... ack=... wraps=... max_command_ms=...
  ...
  SIX CYCLES COMPLETE / rounds=10 commands=... wraps=... max_command_ms=...
commandsは主試験中のマスク/ミュート/STOP命令とKEEPの累計、wrapsは主試験中のACK周回数です。
max_command_msは設定変更命令のACK確認時間で、分割更新/出力準備/通信の待ち時間も含みます。
前回のKEEP応答確認92msやRev Cのmax_poll_usと、そのまま比較する値ではありません。

今回の終了時SIX I2C期待値は、前回の耐久とは異なります。
  SIX I2C: jobs=45 writes=192 max_write_us=... pending=-1 applied=0 prime_left=0
マスク変更は1poll最大1レジスタ、出力準備は12ブロック、期限切れはまず即時ミュートして分割停止します。
主試験commandsをNとして、最終ACKは(N+45)&255です。
HOSTのEXPECTED TARGET FINAL ACKとRev Cのcommands=およびLAST CONTROL STATE先頭を照合します。
Rev Cのcommands=は8bitの値で、累計ではありません。最後の状態は[最終ACK,7,0,0]です。

両側のログ全文と、10周とも上の順序で聞こえたこと、左右、独立ミュート、歪み/予定外の音切れ/クリック音、
最後の自動消音を報告してください。
HOST PASS・HOST SAFE、Rev CのSAFE・DONE、deadline misses=0、lease_expirations=1を確認します。
共通DONEのall nine sound sectionsという文言によらず、今回は80区間と最後の短い音を報告します。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで止めてLIVE I2C/SIX I2CからSAFE・例外末尾まで保存します。

5. 検証と制約
-------------
PCの独立11.25ms通信モデルで、全80区間のFMキー/SSG音量/出力ゲート、ACK周回、時刻周回、
45回の分割処理/192レジスタ更新、最後の期限消音、異常時の再送/再発音なしを確認します。
全204項目（今回追加6項目）が合格しました。MicroPython WASM 1.28.0で模擬時計・通信・音源による
全HOST手順が合格し、mpy-cross 1.29.0で配布21ファイルのArm向けコンパイルも通りました。
検証ログとSHA-256一覧を同梱します。再検証コマンドは以下です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
これらは実機の音質、実際のI2C/PIO/DMA/I2Sの時間や最悪停止時間を保証しません。
今回の切り替え反復は上記の実機条件で確認済みです。
1秒リース/ACKタイムアウト、40ms待機、ターゲット5分上限、ネイティブ期限/音量監視を維持します。
メモリ最大使用量や24時間運転は測定しません。予約演奏、固定テンポ、高速I2C、USB-MIDIは今回含みません。
