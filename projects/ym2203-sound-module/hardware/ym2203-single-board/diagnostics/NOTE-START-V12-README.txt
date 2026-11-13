YM2203C Rev C - 各音色の先頭Cを分離する修正（組み合わせHOST v1.2）
2026-11-12

結果と今回の変更
----------------
HOST v1.1について、最初の音色のCは他の音と同程度の長さになったと実機報告されました。
2つ目以降は引き続き長く感じられるという報告です。v1.1の新しい全ログは受領していません。

v1.1は音階の境界でキーを保持していました。
前の最後のCと次の最初のCがつながり、その途中に音色設定と応答確認の時間も含まれていました。
v1.2では各音階をSTOPで区切り、1秒待ってから、次のTL/MULTI/Cを無音中に準備します。
各音階の先頭でキーオンし、最初のCの再設定を省く処理を全4回に適用します。
音階の中の9音は、これまでどおりキーを保持して演奏します。
今回は、音階間を意図的に無音で分ける診断です。以前の連続切り替え試験は合格済みです。

1. 更新するファイル
-------------------
前回の一式を残したまま、以下の1ファイルだけをHOST Picoの最上位へ上書きします。
  host/rev_c_i2c_combined_host.py
Rev C側の更新は不要です。既存rev_c_i2c_combined_target.py（v1）をそのまま実行します。
前回の他22ファイル、GPIO、回路、ネイティブFM変換、PIO/DMA、I2S、I2C受信は同一です。
1秒リース、40msのHOST応答待ち、1秒ACKタイムアウト、5分上限、音量・変換期限監視も維持します。
main.py / boot.pyには保存しません。UF2更新は不要です。
ZIPには再導入用としてtarget/全15ファイル、host/全8ファイルを含めます。
今回、以前のFM/SSG音階HOSTはv1.1のままで変更していません。

2. 実行
-------
配線・給電・音量は前回と同じです。
Rev C JHOST1=GND、2=SDA -> HOST GP0、3=SCL -> HOST GP1。
3.3V、0x42、10kHz、既存4.7kΩプルアップを使用し、電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー、PC USBなし、DIRECT MONITOR ONです。

1) 両側を停止し、HOSTのrev_c_i2c_combined_host.pyを上書き保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cで従来のrev_c_i2c_combined_target.pyを実行します（表示はv1）。
5) PHASE 0 READY後、HOSTで更新したrev_c_i2c_combined_host.pyを実行します。
   YM2203 Rev C / I2C combined FM pitch + timbre HOST v1.2 / OTHER Pico only
6) 起動検査後、自動演奏します。準備を含め約2分が目安です。

3. 聞こえ方
-----------
ドレミファソファミレドを、次の4通りの音色で演奏します。
  1回目 TL96/MULTI1 -> 無音
  2回目 TL40/MULTI1 -> 無音
  3回目 TL40/MULTI2 -> 無音
  4回目 TL40/MULTI3 -> 無音
  最後 短いFM C -> 約1秒で自動消音

音階の間は1秒の待機に設定通信時間が加わるため、無音の実時間は1秒より長くなります。
各音階の先頭Cが、その直後のレ・ミと同程度の長さに聞こえるか確認してください。
各音階の中には意図的な無音を入れていません。音色・音程・音量設定は前回と同じです。
通信と状態確認を含む診断であり、厳密な固定テンポの演奏ではありません。
I2S遅延、通信時間、HOSTログ表示などによる細かな差は残り得ます。

4. ログと報告
-------------
  SCALE 1/4 / TL=96 MULTI=1 / prepare while silent
  ... NOTE 1/9 / C4 ... NOTE 9/9 / C4
  SCALE 1/4 PASS / ack=...
  STOP / 1 second silence
  ... 4回まで繰り返す ...
  HOST PASS: four scales, silent timbre setup, separate C starts and final lease mute

EXPECTED TARGET FINAL ACKとRev Cのcommands=が一致します。通常の期待値は169です。
lease_expirations=1、deadline misses=0、HOST PASS・HOST SAFE、Rev CのSAFE・DONEを確認します。
新しい先頭CごとのキーオンとSTOPを増やしたため、v1.1のACK163から変わります。
Rev Cの共通DONEにall nine sound sectionsと出ても、今回は4音階と最後の短い音が確認対象です。

両側のログ全文と、4つとも先頭Cの長さが改善したか、各音階間の無音、左右、
歪み/予定外の音切れ/クリック音、最後の自動消音を報告してください。
v1.2は実機で全4音色の先頭Cがレ・ミと同程度になったと報告されました。
音階間の無音、左右正常、歪み/音切れ/気になるクリック音なし、最後の自動消音とHOST PASS・SAFE/DONEも確認。
ログ全文は未受領のため、新しい実測カウンターや変換時間は追記しません。配布済みZIPは変更しません。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで止めて末尾ログを保存します。

5. 検証の範囲
-------------
v1.1のままでは、全4回のC開始と音色設定時の無音を求める2つの回帰テストが失敗します。
v1.2では全4回のC/D/Eのコマンド適用時刻、音階間の無音、設定中のゲートOFF、
全36音の順序、KEY ON/OFF、最終期限消音を、独立11.25ms通信モデルで確認します。
FM合成波形やアナログ音声を録音した測定ではありません。
全170項目（今回追加2項目）が合格しました。MicroPython WASM 1.28.0の模擬時計・通信・音源で
全HOST手順が合格し、mpy-cross 1.29.0で配布23ファイルのArm向けコンパイルも通りました。
修正前の失敗ログ、修正後の4回の時刻比較、SHA-256一覧を同梱します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
これらは実機の音質、実際の音符長、PIO/DMA/I2S/I2Cの電気的な検証を代替しません。
予約演奏や固定テンポ、高速I2C、音源値、GPIO、ファームウェアの変更は今回含みません。
