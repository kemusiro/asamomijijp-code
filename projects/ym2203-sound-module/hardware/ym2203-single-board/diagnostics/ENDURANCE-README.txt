YM2203C single board Rev C - FM+SSG 6音・3分連続運転診断 v1.1
2026-11-11

v1からの修正
------------
v1は、実機でMEMORY BASELINEの表示直後にFM stream deadline missedとなりました。
空きメモリ407344バイトで、SAFEによる停止まで確認されています。メモリ不足ではありません。
3分連続再生は未完了です。演奏中のGC・メモリ計測とUSB出力が短いDMA期限を消費する構成を見直しました。
ホストでも遅いGC/コンソール出力によるv1の期限超過を再現しました。
v1.1は明示的GC・空きメモリ計測・ログ出力をすべて受信停止中へ移します。
演奏中は30秒ごとに時刻とピークを固定6件の領域へ記録し、終了後にまとめて表示します。
自動GCは有効のままです。期限監視、DMA、PIO、音量上限、終了処理は変更していません。
v1.1は2026-11-11に実機で3分間を完走し、左右正常・音切れ/歪みなし・最終消音・SAFE/DONEを確認しました。
16000ブロック、実測180000ms、FMピーク2976、最大変換1119us、期限超過0。
GC後の空きメモリは前後とも406960バイトで差0、停止中の計測時間は20281/20804usでした。
次の無音I2C通信診断はI2C-README.txtを参照してください。

1. 接続・ファイルと実行
----------------------
配線・GPIO・公式Pico 2 MicroPython v1.29.0は前回と同じです。UF2書き直しは不要です。
・JPOWERは現在のモバイルバッテリー、Pico USBはThonnyのPCへ。
・AMS-22は別バッテリーでDC 5V給電し、PCとのUSB接続を外します。
・Rev C JLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
・DIRECT MONITOR=ON、LOOPBACK=OFF。MIC/GUITAR未接続、GAIN最小。
・外部ホストI2Cは未接続。両方のボリュームを低めにします。
給電を入れ直す場合はJPOWER → Pico USB、外す順はPico USB → JPOWERです。

ZIPを展開し、以下7個の.pyをすべてPicoの最上位へ保存・上書きしてください。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_fm_ssg_check.py
  rev_c_six_voice_check.py
  rev_c_endurance_check.py
変更は最後の1ファイルです。残り6ファイルは前回と同一です。
PC上に置くだけではPicoからimportできません。main.py / boot.pyには保存しません。
保存後にThonnyシェルでCtrl+Dを押し、rev_c_endurance_check.pyを開いてF5で実行します。
冒頭は YM2203 Rev C / six-voice endurance check v1.1 です。
v1と表示される場合は古いファイルです。保存先とソフトリセットを確認してください。

2. 音と画面の変化
-----------------
1) 従来のバス検査・無音FM事前検査の後、約5秒待ちます。
2) 受信停止中にMEMORY BASELINEを表示します。
3) ENDURANCE STARTの後、FM3音+SSG3音の和音が約3分間続きます。
   FMはC4/E4/G4、SSGはC3/E3/G3。以前の6音診断と同じ静かな設定です。
4) 演奏中はログが増えません。音が続いていれば、そのまま終了を待ってください。
   途中に意図的なミュート、再発音、音程変更はありません。
5) 約3分後にミュートして音源を止め、ENDURANCE 1/6～6/6をまとめて表示します。
6) 最後にDAC/LINEを有効にした無音確認を約2秒行い、SAFEとDONEで終了します。
全体で約3分10秒です。Ctrl+Cで中断できます。
左右とも同じ和音が保たれ、音切れ、歪み、大きなクリック、不意の音量/音程変化がないか確認します。
終了時と終了後にテスト音が消えるかも確認します。小さな背景のサー音は分けて判定します。

3. ログと報告
-------------
MEMORY BASELINEは受信前のGC後の空きメモリ、scan_usはGCと空きメモリ計測の合計所要時間です。
ENDURANCE n/6は、演奏中に記録した値を終了後に表示しています。
  elapsed_ms: 演奏開始後の実測経過時間。
  blocks: 11.25msブロック数。最後は16000。
  peak: その時点までのFMデジタル最大ピーク。アナログSSGは含みません。
ENDURANCE COMPLETEのnominal_msは180000を期待します。
  baseline_free / final_free: 受信前と受信停止後、それぞれGCした後の空きメモリ。
  delta: final_free - baseline_free。負は空きが減ったことを示します。
  post_scan_us: 受信停止後のGCとメモリ計測の合計所要時間。
メモリ計測は前後の2点だけです。演奏中の一時的な使用量や連続した推移は判断できません。
小さな差はあり得るため、deltaが厳密に0である必要はありません。
空き64KiB未満では診断を中止します。64KiBは診断の復旧余裕で、アプリのメモリ上限ではありません。

期待する末尾:
  REPORTS / recorded during playback; printed after capture stopped
  ENDURANCE 1/6 / ...
  ...
  ENDURANCE 6/6 / elapsed_ms=... blocks=16000 peak=...
  ENDURANCE COMPLETE / blocks=16000 nominal_ms=180000 ...
  SOURCES OFF / DAC and line enabled / should be silent / 2 seconds
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped
  DONE: report continuous L/R chord, no dropouts/distortion, memory reports and final silence.

左右の状態、途中の途切れ/歪み/不意の変化、最後の消音と、ログ全文を報告してください。
ENDURANCE COMPLETEだけでは全診断の完了ではありません。SAFEとDONEまで確認します。

4. 停止と制約
-------------
正常終了・例外・中断時は、確認済み共通処理でLINEミュート、ARM=0、メモリ回収、受信とI2Sの停止を行います。
再試験でエラーが出た場合も全文を保存してください。再実行や他の診断の前にはCtrl+Dを押します。
操作できない場合は音量を下げ、Pico USB → JPOWERの順に外します。
v1.1で取り除いたのは、診断が意図的に挟んでいた重い計測とUSB出力です。
自動GC、割り込み、受信/再生クロック差などによる期限超過まで解消したとはまだ判断しません。
FM TL64、SSGレベル7、PCMゲイン32、上限4096/32768を維持し、GPIO・回路は変更していません。
デジタル検査はFMが対象です。SSGとアナログ音は耳でも確認します。
3分はこの診断の長さで、製品の演奏時間上限ではありません。
24時間運転、温度、最大音量、全音色、USB-MIDI、I2Cスレーブの検証は含みません。

5. PC上での検証
---------------
ホスト79項目（連続運転診断9項目）。実際のStream.checkを使い、50msのGC/USB出力を与えても
受信中に実行しないこと、演奏中の明示的メモリ計測を拒否すること、遅延した音声ブロックは検出することを確認します。
連続性、6件の記録、最終消音、メモリ不足、信号消失、Ctrl+C/MemoryError相当での停止も確認します。
ホストのシーケンス試験は時間を短縮しています。
MicroPython WASM v1.28.0では、時計と音声転送を模擬して全16000ブロックを実行します。
停止中のGCとログ表示、固定件数の記録、最終消音を確認します。
WASMのelapsed_msとscan_usは模擬時計の値です。物理音声や実時間のGC性能は検証しません。
公式MicroPython v1.29.0のmpy-crossで新規ファイルのArm向けコンパイルも確認します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
validation.jsonにSHA-256と検証範囲、各ログに実行結果を記録しています。
コンパイラー、生成mpy、UF2、メーカー資料、他者の音楽データは同梱しません。
