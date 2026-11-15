YM2203C Rev C - 6音同時発音＋外部I2C通信の3分耐久診断 v1
2026-11-12

確認済みの結果
--------------
直前の外部I2C6音診断は、15区間すべて実機合格です。
FM/SSGの各単独音・各和音・6音同時発音、DAC MUTEでSSGだけ残ること、LINE MUTEで全消音を確認。
左右正常、歪み/予定外の音切れ/気になるクリック音なし、最後の自動消音とHOST PASS・SAFE・DONEも確認。
3825ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4698、max_idle_poll_us=434。
SIX I2Cはjobs=15 writes=38 max_write_us=4402 pending=-1 applied=0 prime_left=0でした。
最終ACK163がHOST期待値と一致。期限消音1回、stale flush 0、受信621=HOST全体1659-起動1038、
送信1270=4018-起動2748も整合しています。

次は同じ6音を3分間鳴らしたまま、I2C KEEPと状態読み取りを繰り返します。
発音中に音程・音色・音量・マスクを変更しません。Rev C側は前回のソースをそのまま使います。
3分耐久は実機合格しました。主試験180156ms、KEEP517回、ACK周回2回、最大ACK確認92ms、状態照合まで160ms。
左右正常、歪み/音切れ/気になるクリック音なし、最終自動消音とHOST PASS・SAFE/DONEを確認。
16901ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4541、max_idle_poll_us=468。
SIX I2C jobs=7 writes=24 max_write_us=4291 pending=-1 applied=0 prime_left=0。
最終ACK52が一致し、期限消音1回、stale flush 0、受信2286=3324-1038、送信5680=8428-2748も整合。
配布済みZIPは変更しません。

1. 接続とファイル
-----------------
配線・給電・音量は前回合格したままです。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V I2C、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップ、電源線同士はつながない構成です。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー、PC USBなし、DIRECT MONITOR ONです。

前回の一式を残し、次の1ファイルだけをHOST Picoの最上位へ追加します。
  host/rev_c_i2c_six_endurance_host.py
既存のrev_c_i2c_six_host.pyもimportして使うため、HOST内に残してください。
Rev C側は更新不要で、既存のrev_c_i2c_six_target.pyを実行します。
未保存の場合はZIPのtarget/全13ファイルをRev C、host/全7ファイルをHOSTへ保存してください。
前回の19ファイルは変更していません。GPIO・ネイティブ変換・音源値・期限監視も同じです。
main.py / boot.pyには保存せず、UF2更新もしません。

2. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cで従来のrev_c_i2c_six_target.pyを実行します。
   YM2203 Rev C / staged I2C six-voice target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_six_endurance_host.pyを実行します。
   YM2203 Rev C / I2C six-voice endurance HOST v1 / OTHER Pico only
6) 従来の起動検査後、5秒待って6音が鳴り、3分間の主試験を行います。
準備を含め約4分が目安です。以前の15区間HOSTを実行する試験ではありません。

3. 聞こえる音
-------------
FM CH1/CH2/CH3のC4/E4/G4と、SSG A/B/CのC3/E3/G3、計6音の和音を連続で鳴らします。
主試験の3分間には、意図した無音・音色変更・ミュートを入れません。
音が途切れないこと、歪み・気になるクリック音がないこと、左右が正常なことを確認してください。

主試験終了後はSTOPで1秒無音にし、その後、同じ6音を短く鳴らします。
KEEPを止め、約1秒で全音の自動消音と分割停止の完了を確認して終了します。
最初の出力準備と最後のSTOP/自動消音の無音は計画されたものです。

4. 通信と途中経過
-----------------
主試験中は200ms以下の待機と、既存のKEEP/ACK処理を繰り返します。
各KEEP後に[ACK,最後の命令,モード1,期限フラグ0,発音マスク63,処理中0]を照合します。
ACKと6バイト状態を読み終える通信時間も、3分の主試験時間に含みます。
不一致や通信例外では音を再開せず、命令を自動再送しません。
HOSTが停止してもRev Cの1秒リースがゲートを閉じ、分割処理で全音源を停止します。

30秒ごとにHOSTだけが経過を表示します。Rev C側は受信中のUSBログ出力やメモリ走査を増やしません。
  SIX ENDURANCE 1/6 / elapsed_ms=... KEEP=... ack=... wraps=... max_command_ms=... max_check_ms=...
  ...
  SIX ENDURANCE 6/6 ...
  SIX ENDURANCE COMPLETE / elapsed_ms=... KEEP=... wraps=... max_command_ms=... max_check_ms=...
KEEPは主試験中の命令数、wrapsはACKが255から0へ周回した回数です。
少なくとも256回のKEEPと1回以上のACK周回を確認します。
max_command_msはKEEPの書き込みからACK確認まで、max_check_msは追加の6バイト状態照合までの時間です。
両方とも200msの待機を含まず、Rev Cのmax_poll_us・音声変換時間とは別の値です。
最後の通信・照合で180000msを少し超えることがあります。

5. 期待する終了ログと報告
-------------------------
今回のRev C側SIX I2Cの期待値は、前回15区間とは異なります。
  SIX I2C: jobs=7 writes=24 max_write_us=... pending=-1 applied=0 prime_left=0
主試験中は同じマスクを保つため、チャンネル書き込みは増えません。
初回発音・STOP・短い再発音・期限消音の分割処理などで、合計24レジスタを更新します。
最終ACKは、主試験KEEP数をNとして (N+47)&255 です。
HOSTのEXPECTED TARGET FINAL ACKと、Rev Cのcommands=およびLAST CONTROL STATE先頭を照合します。
Rev Cのcommands=は8bitの値で、累計ではありません。最後の状態は[最終ACK,7,0,0]です。

両側のログ全文と、3分間の連続音、左右、歪み/予定外の音切れ/クリック音、
主試験後の停止、最後の短い和音と自動消音を報告してください。
HOST PASS・HOST SAFE、Rev CのSAFE・DONE、deadline misses=0、lease_expirations=1を確認します。
Rev Cの共通DONEにall nine sound sectionsと出ても、今回は3分間の連続音と最後の短い音を報告します。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで停止し、LIVE I2C/SIX I2CからSAFE・例外末尾まで保存します。

6. 検証と制約
-------------
独立11.25ms通信モデルで、主試験180秒、全6音のキー/音量/ゲート維持、状態照合、
ACK周回、時刻周回、最後の期限消音を検査します。通信例外や状態破損時に再送/再発音しないことも確認します。
全198項目（今回追加5項目）が合格しました。MicroPython WASM 1.28.0で模擬時計・通信・音源を使った
全HOST手順が合格し、mpy-cross 1.29.0で配布20ファイルのArm向けコンパイルも通りました。
検証ログとSHA-256一覧を同梱します。再検証コマンドは以下です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
今回はHOST追加だけで、前回までのターゲット/ヘルパー/ネイティブ処理に変更はありません。
これらは実機の音質・I2C/PIO/DMA/I2Sの実タイミングや長時間安定性の代替検証ではありません。
今回の3分耐久の実機結果は上記のとおり合格です。
メモリの最大使用量、24時間運転、音色/音程変更の反復、予約演奏、高速I2C、USB-MIDIは今回測定しません。
1秒ACKタイムアウト、1秒リース、40ms ACK待ち、ターゲット5分上限は維持します。
