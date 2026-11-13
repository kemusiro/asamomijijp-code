YM2203C Rev C - 最初のCの余分な延長を修正（HOST v1.1）
2026-11-12

この文書はHOST v1.1の記録です。現行の組み合わせHOST v1.2の更新・実行手順はNOTE-START-V12-README.txtです。

確認した原因
------------
組み合わせ診断v1は音程/音色/左右/音質/ミュート/通信の実機検証に合格しました。
4109ブロック、ピーク992、最大変換1119us、期限超過0、max_poll_us=7332、max_idle_poll_us=381。
期限消音1回、stale flush 0、最終ACK165も一致しました。
受信722=HOST全体1760-起動1038、送信2058=4806-起動2748も整合しています。
一方、最初のCが他の音より長いという聴感上の課題が報告されました。

コードと独立11.25ms通信モデルで以下を確認しました。
- 組み合わせHOST v1はCを鳴らした後、TL/MULTIの設定・状態確認と同じCの再設定を行っていました。
- 以前の音程HOST v1も、Cの発音開始後に同じCの再設定・状態確認を行っていました。
- その応答待ちと状態読み取り時間が、最初のCに余分に加算されていました。
1回目のCと次のDの長さを比べる回帰テストは両方とも修正前に失敗し、修正後は合格します。
これはHOSTの順序に関する修正です。音源ICやネイティブ音声変換の変更はありません。

修正内容
--------
組み合わせHOST v1.1は、最初のTL/MULTI/CをSTOP中に準備します。
先頭音のループでFMをキーオンし、Cを再設定しません。
音程HOST v1.1も、STOP中に選択したCをそのまま先頭音として鳴らし、重複設定しません。
両方とも、先頭音の発音後の応答確認・保持を他の音と同じ構成に揃えます。
後続の音色変更、音程変更、200ms待機+KEEPを2回行う処理は従来と同じです。
40ms待ち、1秒リース、ACK確認、期限監視、GPIO、ターゲット、音量は維持します。

重要な区別
----------
組み合わせ演奏の、前の音階の最後のド -> 次の音階の最初のドは、意図的にキーを保持します。
この境界は2音分のCがつながり、さらに発音中の音色設定時間が含まれるため、長く聞こえます。
今回修正するのは演奏開始時のCへの不要な処理加算です。音階境界のつながりは維持します。
等間隔の予約演奏ではなく、通信・確認時間を含む診断です。厳密な音符長は保証しません。
小さな変動やI2S遅延は残り得ます。モデルの時間は実機の音符長を測定した値ではありません。

1. ファイルの更新
-----------------
前回の組み合わせ一式が両Picoへ保存済みなら、今回の主確認は以下1ファイルだけを更新します。
  HOST: host/rev_c_i2c_combined_host.py
Rev C側は更新不要で、前回合格したrev_c_i2c_combined_target.pyをそのまま使います。

以前のFM/SSG各2回の音階診断も修正する場合は、以下もHOSTへ上書き保存します。
  HOST: host/rev_c_i2c_pitch_host.py
その診断には既存のrev_c_i2c_pitch_target.pyを使います。今回の主確認と同時実行しません。

ファイルは各Picoの最上位へ保存します。main.py / boot.pyには保存しません。
UF2の更新は不要です。importキャッシュを残さないよう両側を初期化してください。
ZIPには再導入用のtarget/全15ファイルとhost/全8ファイルを含めます。
過去のZIPは変更していません。既存のターゲットとヘルパーのソースは同一です。

2. 主確認（組み合わせ演奏）の実行
--------------------------------
配線・給電・音量は前回合格したままです。
  Rev C JHOST1 GND -> HOST GND
  Rev C JHOST2 SDA -> HOST GP0
  Rev C JHOST3 SCL -> HOST GP1
3.3V、0x42、10kHz、既存4.7kΩプルアップ、電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー、PC USBなし、DIRECT MONITOR ON。

1) 両側を停止し、HOSTのrev_c_i2c_combined_host.pyを上書き保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev C側で従来のrev_c_i2c_combined_target.pyを実行します（ターゲットの表示はv1のまま）。
5) PHASE 0 READY後、HOST側でrev_c_i2c_combined_host.pyを実行します。
   YM2203 Rev C / I2C combined FM pitch + timbre HOST v1.1 / OTHER Pico only
6) 4回の音階、最後の1秒無音、短いFM音の自動消音まで進みます。準備を含め約2分です。

音色は従来どおり TL96/MULTI1、TL40/MULTI1、TL40/MULTI2、TL40/MULTI3です。
演奏開始のCと、その直後のレ・ミの長さを重点的に比較してください。
2回目以降の先頭Cは、前の最後のCとつながる点に注意してください。
ターゲット末尾のcommands=がHOSTのEXPECTED TARGET FINAL ACKと一致します。
通常は修正前165から修正後163へ減ります（不要な重複命令を減らしたため）。
lease_expirations=1、deadline misses=0、HOST PASS・SAFE・DONEを確認します。

3. 任意の追加確認（FM/SSGの音階）
--------------------------------
主確認と別に両側を初期化して行います。
Rev Cでrev_c_i2c_pitch_target.pyを実行し、PHASE 0 READY後にHOSTでrev_c_i2c_pitch_host.pyを実行します。
  YM2203 Rev C / I2C FM + SSG pitch HOST v1.1 / OTHER Pico only
FM2回とSSG2回をそれぞれ1秒無音で分けて演奏します。
この診断では各回の先頭Cを比較できます。各先頭の重複命令を省き、最終ACKは通常161です。
最後は短いSSG Cの自動消音です。聞こえ方の詳細はI2C-PITCH-README.txtも参照してください。

4. 報告と検証
-------------
両側のログ全文と、演奏開始のCの長さが改善したか、左右、歪み/音切れ/クリック音、
最後の自動消音を報告してください。実機での修正効果はまだ未確認です。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで停止して末尾ログを保存します。

修正前に失敗した回帰テストを含むPCの168項目（今回追加4項目）が合格しました。
MicroPython WASM 1.28.0で全HOST手順を実行し、mpy-cross 1.29.0で配布23ファイルのArmコンパイルも合格しました。
修正前の失敗ログ、修正後のモデル時刻比較、検証ログ、SHA-256一覧を同梱します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
PCモデルはコマンドがターゲットで適用された時刻を比較します。音声波形を録音した測定ではありません。
実音の長さやUSB出力の遅延は実機で確認が必要です。
今回、予約演奏、固定テンポ、I2C高速化、音源値、GPIO、ネイティブ変換は追加/変更していません。

v1.2補足: v1.1で最初のCは改善したと実機報告されました。2つ目以降のつながったCを分離するため、
組み合わせHOST v1.2は全音階の間にSTOP/1秒待機を入れ、音色設定を無音中に済ませます。
期待する最終ACKは169です。ターゲットと音程HOSTは変更しません。詳細はNOTE-START-V12-README.txt。
