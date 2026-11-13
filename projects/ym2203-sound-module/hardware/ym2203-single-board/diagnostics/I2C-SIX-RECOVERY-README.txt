YM2203C Rev C - HOST通信一時停止・復帰3回診断 v1
2026-11-12

直前の実機結果
--------------
6音切り替え10周・80区間が合格しました。左右正常、独立ミュート/STOP/最終自動消音、
HOST PASS・SAFE・DONEを確認し、歪み/予定外の音切れ/気になるクリック音はありませんでした。
18268ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4568、max_idle_poll_us=475。
SIX I2C jobs=45 writes=192 max_write_us=4300 pending=-1 applied=0 prime_left=0。
主試験640命令、ACK周回2回、最大設定変更ACK確認327ms、最終ACK173=(640+45)&255。
期限消音1回、stale flush 0、受信2466=3504-1038、送信4874=7622-2748が一致しました。

次はHOSTの通信を止めても自動消音され、その後、同じRev Cへ通信復帰できることを確認します。
プログラムがHOST GP0/1を一時的に入力へ戻し、1800ms待ってハードウェアI2C0へ再設定します。
その間の音の消え方と、明示的な復帰操作後の再発音を3回繰り返します。
ケーブルや電源は接続したままで実行します。物理的な抜き差しや転送途中の切断試験ではありません。
Rev C側のターゲットは変更しません。通信復帰診断も実機で3回すべて合格しました。
左右正常、歪み/予定外の音切れ/気になるクリック音なし、HOST PASS・SAFE・DONEを確認しました。
2118ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4577、max_idle_poll_us=470。
SIX I2C jobs=13 writes=48 max_write_us=4408 pending=-1 applied=0 prime_left=0、期限消音3回、stale flush 0。
復帰時ACK51/61/71、最終ACK83が一致し、受信350=1388-1038、送信792=3540-2748も整合しています。
次はI2C-VOICE-PITCH-README.txtの6チャンネル独立音程制御診断です。

1. 配線・ファイル
-----------------
前回合格した配線/給電/音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、ハードウェアI2C0の10kHz、既存4.7kΩプルアップを使います。
電源線同士はつなぎません。試験中の手動操作は不要です。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22は別バッテリー/PC USBなし、DIRECT MONITOR ON。

前回のファイルを残し、次の1ファイルをHOST Picoの最上位へ追加します。
  host/rev_c_i2c_six_recovery_host.py
rev_c_i2c_six_host.py等の既存ヘルパーも残してください。
Rev C側は従来のrev_c_i2c_six_target.pyです。更新は不要です。
ファイルが未保存の場合は、ZIPのtarget/全13ファイルをRev Cへ、host/全9ファイルをHOSTへ保存します。
既存21ソースは前回配布とバイト単位で同一です。
main.py / boot.pyには保存しません。UF2更新は不要です。

2. 実行
-------
1) 両側を停止し、新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cでrev_c_i2c_six_target.pyを実行します。
   YM2203 Rev C / staged I2C six-voice target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_six_recovery_host.pyを実行します。
   YM2203 Rev C / I2C six-voice recovery HOST v1 / OTHER Pico only
6) 起動検査とSTART/KEEP確認の後、5秒待って発音します。準備を含め1～2分が目安です。

3. 聞こえる音と自動処理
-----------------------
固定6音（FMのC4/E4/G4とSSGのC3/E3/G3）が左右から聞こえます。
最初はKEEP付きで約2秒保持し、その後、次の処理を3回行います。
  HOST PINS RELEASED：HOSTの通信端子を入力へ戻す。KEEPも停止します。
  約1秒後：Rev Cが自動消音します。全6音の停止処理も行います。
  REBIND：1800msの無通信後、HOSTを同じI2C0/GP0/1へ戻します。
  ATTACH PASS：同じRev Cの署名、直前のACK、期限フラグ1、マスク0、処理中0を確認します。
  STOP acknowledged：明示的STOPで期限フラグを解除します。この時点でも無音です。
  resume six voices：6音の発音を明示的に指示し、約2秒の正常再生を確認します。
以上の自動消音と復帰を3回行い、最後はSTOPで消音して終了します。

音は「6音 -> 自動消音 -> 6音 -> 自動消音 -> 6音 -> 自動消音 -> 6音 -> 最後のSTOP」です。
発音の保持後も、通信停止から期限まで約1秒鳴り続けるので、最初の3回は約3秒の音になります。
自動消音の無音時間には、状態読み取りと発音準備の待ち時間も含まれます。
3回の意図した無音以外の音切れ、歪み、気になるクリック音がないか確認してください。
この試験ではDAC/LINEの独立ミュート区間を追加せず、前回合格した音量のまま使います。

4. 状態照合・終了ログ
---------------------
通信停止の直前にも6バイトの状態を読み、既に期限切れや不一致があれば停止します。
復帰時の確認前には音源命令を送りません。ACKが変化した場合やRev Cがリセットされた場合は、
別セッションとして検出して停止し、自動的な再送/再発音は行いません。
Rev Cは起動したままです。復帰時にSTARTを再送せず、STOPと発音マスクで操作します。
HOSTの統計値はI2C再設定前後で累計します。

  RECOVERY 1/3 / HOST PINS RELEASED / no I2C for 1800 ms
  RECOVERY 1/3 / REBIND / expect silence until explicit restart
  RECOVERY 1/3 / ATTACH PASS / ack=... lease=1 mask=0 busy=0
  RECOVERY 1/3 / STOP acknowledged / lease cleared; resume six voices
  RECOVERY 1/3 PASS / six voices restored
  ... 2/3、3/3 ...
  FINAL STOP / all sources off / 1 second silence
  EXPECTED TARGET FINAL ACK: ... / FINISH=7 mode=0 lease_flag=0
  HOST PASS: three HOST pin releases ...

Rev C側の今回の期待値は以下です。
  SIX I2C: jobs=13 writes=48 max_write_us=... pending=-1 applied=0 prime_left=0
  lease_expirations=3
  deadline misses=0
LAST CONTROL STATEは[HOST期待の最終ACK,7,0,0]です。
3回の自動消音は意図したものです。最終消音はSTOPで、4回目の期限切れは起こしません。
起動検査/START後/発音保持を含めたKEEP総数をKとすると最終ACKは(K+11)&255です。
KEEP以外はSTOP/START/発音マスク/FINISHを計11命令送ります。KEEP回数は実時間によって変わります。
共通DONEのall nine sound sectionsという文言によらず、今回は上記の3回の復帰を確認します。

両側のログ全文と、3回の自動消音/復帰、最後のSTOP、左右、歪み/予定外の音切れ/クリック音を報告してください。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで停止し、LIVE I2C/SIX I2CからSAFE・例外末尾まで保存します。
HOSTの異常終了時にも従来のfinallyでGP0/1を入力へ戻し、Rev Cは残っているリースで自動消音します。

5. 検証と制約
-------------
全210項目（今回追加6項目）のPCテストが合格しました。独立11.25ms通信モデルで、
通信停止中にI2C転送を行わないこと、3回の期限消音/全音源停止、同じACKへの接続、STOPでの解除、
4回の6音発音、13件の分割処理/48回の書き込み、時刻周回、異常時に再送/再発音しないことを確認しました。
MicroPython WASM 1.28.0の模擬時計/通信/音源で全HOST手順を確認し、
mpy-cross 1.29.0で配布22ファイルのArm向けコンパイルを確認しました。
検証ログとSHA-256一覧を同梱します。再検証コマンドは以下です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
これらは実機での端子切り替え、音質やI2C/PIO/DMA/I2Sの最悪応答時間を保証しません。
ソフトウェアから完了済み転送の境界でHOST端子を切り替える試験です。
物理的な抜き差し、電源断、SDA/SCLの短絡/固着、転送途中の切断、実際の別HOSTへの交換は検証しません。
GPIO割り当て/ネイティブ変換/音量、40ms待機、1秒リースとACK期限、ターゲット5分上限は維持します。
予約演奏、固定テンポ、高速I2C、USB-MIDI、24時間運転は今回含みません。
