YM2203C Rev C - 外部I2CによるFM3音+SSG3音診断 v1
2026-11-12

直前の実機結果
--------------
エンベロープv1.1は全6区間が実機合格です。持続音、キーオフ、再発音、2回の減衰を確認しました。
左右正常、歪み/音切れ/気になるクリック音なし、最後の自動消音とHOST PASS・SAFE・DONEも確認。
2243ブロック、ピーク992、最大変換1115us、期限超過0、max_poll_us=3022、max_idle_poll_us=462。
ENVELOPEはupdates=3 writes=24 max_write_us=2667 pending=-1 step=8、最終ACK104が一致しました。
期限消音1回、stale flush 0、受信403=HOST全体1441-起動1038、送信824=3572-2748も整合しています。

次は外部I2CからFM3チャンネルとSSG3チャンネルを個別に制御し、和音と6音同時発音を確認します。
音程・音量は以前に実機合格したローカル6音診断と同じです。
  FM CH1/CH2/CH3 = C4/E4/G4、1キャリア、各TL64
  SSG A/B/C = C3/E3/G3、各音量7、ノイズ/エンベロープなし
任意音色、自由な譜面、音源の予約演奏は追加しません。外部I2C6音制御は実機で15区間すべて合格しました。左右正常、音質正常、独立ミュートと最終自動消音も確認。
3825ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4698、max_idle_poll_us=434。
SIX I2C jobs=15 writes=38 max_write_us=4402 pending=-1 applied=0 prime_left=0。
最終ACK163が一致。期限消音1回、stale flush 0、受信621=1659-1038、送信1270=4018-2748も整合。
HOST PASS・SAFE・DONEを確認しました。配布済みZIPは変更しません。

1. 接続とファイル
-----------------
前回合格した配線・給電のままで行います。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V I2C、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップを維持します。
電源線同士はつなぎません。配線変更は両側電源OFF、試験中は両側を給電します。
JLINE -> AMS-22 LINE IN、ヘッドホン -> AMS-22、両方の音量を低めから調整します。
AMS-22は別バッテリー、PC USBなし、DIRECT MONITOR ON、LOOPBACK OFFです。

既存のファイルを残し、各Picoの最上位へ次を保存します。
  Rev C: target/rev_c_six_voice_check.py   以前のローカル6音診断の共通ヘルパー
         target/rev_c_i2c_six_target.py    今回追加・実行するファイル
  HOST:  host/rev_c_i2c_six_host.py        今回追加・実行するファイル
共通ヘルパーが保存済みなら同じ内容で置き換えて構いません。既存の制御ヘルパーは変更していません。
未保存の場合はZIPのtarget/全13ファイルをRev C、host/全6ファイルをHOSTへ保存してください。
今回使わないenvelope/timbre/combined/pitchファイルはZIPに含めませんが、Pico内には残せます。
main.py / boot.pyには保存しません。UF2更新は不要です。

2. 実行
-------
1) 両側を停止して上の3ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cでrev_c_i2c_six_target.pyを実行します。
   YM2203 Rev C / staged I2C six-voice target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_six_host.pyを実行します。
   YM2203 Rev C / I2C six-voice HOST v1 / OTHER Pico only
6) 6段階の無音検査、専用シグネチャ・START/KEEP確認後、5秒待って発音します。
準備を含め約2分が目安です。

3. 15区間の聞こえ方
------------------
各区間は約2秒で、最後の区間15は約1秒の発音後に自動消音します。
   1 FM CH1だけ    ド C4
   2 FM CH2だけ    ミ E4
   3 FM CH3だけ    ソ G4
   4 FM3音        高いドミソの和音
   5 SSG Aだけ     低いド C3
   6 SSG Bだけ     低いミ E3
   7 SSG Cだけ     低いソ G3
   8 SSG3音       低いドミソの和音
   9 6音同時      高いFM和音+低いSSG和音
  10 DAC MUTE     低いSSG和音だけ残る
  11 RESTORE      6音に戻る
  12 LINE MUTE    両方の和音が消える（内部の発音は継続）
  13 RESTORE      6音に戻る
  14 STOP         全音源/出力を停止、2秒無音
  15 LEASE        6音を短く鳴らし、KEEPなしで約1秒後に自動消音

単独FMは以前の単音FM診断より小さめです。音源別のバランスや6音時の歪みも確認してください。
音程はレジスタの量子化により理想値からわずかにずれます。
チャンネルの組み合わせを変えるときは一度出力を閉じ、分割設定と出力の準備後に開きます。
この短い無音や切り替え待ちは意図したものです。各区間の定常部分の音を確認してください。
今回のDAC/LINE MUTEはチャンネル設定を保持し、RESTOREで出力を戻します。

4. 診断用I2Cと分割処理
----------------------
正式APIではありません。起動6段階は従来のRCISO01!、その後の専用シグネチャはRCSIX01!です。
他のターゲットとの組み違いは発音前にHOSTが拒否します。
転送形式は従来どおり [0x20, 命令1byte]です。
  0 STOP、6 KEEP、7 FINISH、8 START
  3 出力復帰、4 DAC MUTE、5 LINE MUTE
  0x40..0x7F: 6bitの発音マスクを選択（命令 - 0x40 がマスク）
  bit0=FM CH1、bit1=FM CH2、bit2=FM CH3、bit3=SSG A、bit4=SSG B、bit5=SSG C
例: 0x41=FM CH1、0x47=FM3音、0x78=SSG3音、0x7F=6音、0x40=全音源OFF。
マスク選択完了時は出力を通常の有効状態へ戻します。音量/音程/音色の任意値は受け付けません。

0x10から6バイトの状態を読みます。
  [8bit ACK,最後の命令,モード,期限フラグ,完了済み発音マスク,処理中フラグ]
モードは0=停止、1=通常出力、4=DAC MUTE、5=LINE MUTEです。
命令3の出力復帰は、状態モード1になります。命令1/2の単独FM/SSG選択は今回使いません。

マスク変更ではまずDAC/LINEを閉じ、変わるチャンネルだけを1poll最大1レジスタずつ更新します。
FMはキー、SSGは音量を書き、SSG音量は読み戻します。設定音程は受信開始前に済ませます。
有効なマスクでは更新後、既存の出力準備値12音声ブロック（約135ms）を消音状態で処理します。
I2Cが非アクティブで、更新/準備が終わったときだけACK/マスク/モードを確定し、出力を開きます。
処理中フラグ1では、ACK/モード/マスクは前の完了状態の記録です。実際の出力は閉じています。
ホストは1命令のACKを待ちます。処理中に次の命令を重ねると例外で停止します。

1秒の通信リースが切れたときは、まずゲートを閉じてモード/マスクを0にし、期限フラグを1にします。
音源のキー/音量を0にする後処理は同じ分割方式で行います。その間は処理中フラグ1です。
完了後に処理中フラグ0となります。期限消音/後処理ではACKを増やさず、発音を再開しません。
期限切れ後のマスクや出力復帰命令は拒否します。明示STOPで期限フラグを解除してから再設定が必要です。

ネイティブFM変換、PIO/DMA、I2S、共通I2C受信、GPIO、音量上限、期限監視は従来どおりです。
40ms ACK待機、1秒ACKタイムアウト、1秒リース、ターゲット5分上限も同じです。
途中書き込み失敗ではACKを確定せず、共通終了処理で消音・停止します。命令は自動再送しません。

5. ログと報告
-------------
正常終了時、キャプチャ停止後に次が表示されます。
  SIX I2C: jobs=15 writes=38 max_write_us=... pending=-1 applied=0 prime_left=0
jobsには初回STOP、マスク変更、最終STOP/FINISH、期限消音の後処理を含みます。
writesは変更したチャンネルのレジスタ書き込み数です。受信開始前の設定は含みません。
max_write_usはFMキーまたはSSG音量の1チャンネル処理時間（SSGは読み戻しを含む）です。

両側のログ全文と、各単独音、両方の和音、6音同時、独立ミュート、左右、
歪み/予定外の音切れ/クリック音、最後の自動消音を報告してください。
HOST PASS・HOST SAFE、Rev CのSAFE・DONE、deadline misses=0、lease_expirations=1を確認します。
EXPECTED TARGET FINAL ACKとRev Cのcommands=を照合します（8bitで、累計ではありません）。
ACK値は各2秒間のKEEP回数によって変わり得ます。
共通DONEのall nine sound sectionsという文言にかかわらず、今回は15区間が確認対象です。

失敗時はHOSTを再実行せず、Rev CもCtrl+Cで止めて、LIVE I2C/SIX I2CからSAFE・例外末尾まで保存します。

6. 検証と制約
-------------
PCの独立11.25ms通信モデルで、全HOST手順、6チャンネルの実際の書き込み、
音源/ゲート状態、1poll最大1書き込み、出力準備、即時期限ミュートと分割停止を確認します。
途中書き込み失敗、異常命令、状態不一致、通信例外の再送なし、時刻周回、例外終了も検査します。
3キャリアの模擬波形を使い、元のネイティブ期限/音量チェックを通す制御ループの試験も行います。
全193項目（今回追加9項目）が合格しました。MicroPython WASM 1.28.0で時計/通信/音源を模擬した
全HOST手順が合格し、mpy-cross 1.29.0で配布19ファイルのArm向けコンパイルも通りました。
検証ログとSHA-256一覧を同梱します。再検証コマンドは以下です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
これらは実機のFM/SSG合成音質、アナログのクリップ、電気的な通信や最悪実行時間を保証しません。
今回の外部I2C6音制御の実機結果は上記のとおり合格です。
自由な音程/音色、予約演奏、固定テンポ、高速I2C、長時間運転、USB-MIDIは今回の対象外です。
