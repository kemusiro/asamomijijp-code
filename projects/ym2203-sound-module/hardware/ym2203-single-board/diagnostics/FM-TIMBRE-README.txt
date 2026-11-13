YM2203C single board Rev C - 4オペレーターFM音色診断 v1
2026-11-11

目的
----
FM3音+SSG3音は全10区間が左右正常、独立ミュート、歪み・音切れなし、SAFE/DONEまで
ユーザー実機で確認されました。最大変換1117us、期限超過0、FM単音ピーク992、3音2976。
従来は単純なキャリアでした。今回はFMチャンネル1の4オペレーターによる変調、
発音中のパラメータ変更、エンベロープの減衰と再発音を初めて確認します。
SSGは全区間で停止します。
2026-11-11に6区間すべてが想定どおり、音色変更と2回の減衰・再発音、
左右正常、歪み・音切れなし、SAFE/DONEまでユーザー実機で確認されました。
最大変換1115us、期限超過0、事前検査ピーク4064、空きメモリ410736バイト。
次の3分連続運転診断はENDURANCE-README.txtを参照してください。

1. 接続・準備
-------------
配線、GPIO、公式Pico 2 MicroPython v1.29.0は前回のままです。UF2の書き直しは不要です。
・JPOWERは現在のモバイルバッテリー、Pico USBはThonnyを使用するPCへ接続。
・AMS-22は別のモバイルバッテリーからDC 5V給電し、PCとのUSB接続を外します。
・Rev CのJLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
・DIRECT MONITOR=ON、LOOPBACK=OFF。MIC/GUITARは未接続、GAINは最小。
・外部ホストI2Cは未接続のままです。
両方のボリュームを低い位置から始め、同じ音量設定で比較してください。
入れ直す場合の給電順はJPOWER → Pico USB、外す順はPico USB → JPOWERです。

2. ファイルと実行
-----------------
ZIPを展開し、次の6ファイルをすべてPicoの最上位へ保存・上書きしてください。
PC上に置くだけでは、Pico上でのimportができません。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_fm_ssg_check.py
  rev_c_fm_timbre_check.py
新規ファイルは最後の1つです。残り5ファイルは前回と同一です。
main.py / boot.pyには保存しません。
保存後、ThonnyのシェルでCtrl+Dを押してから、rev_c_fm_timbre_check.pyを開きF5で実行します。

冒頭: YM2203 Rev C / four-operator FM timbre check v1
バス検査と無音FM事前検査は従来の単純な音色で行い、約5秒待って比較を始めます。
事前検査はTL48（前回までと同じピーク約4064）。比較中のキャリアはTL64に抑えます。
全体は初期検査と待ち時間を含めて約30秒です。

3. 六つの区間
-------------
1 PURE            約440Hzのほぼ正弦波。2秒。比較用の基準音です。
2 FOUR OPERATORS  4オペレーターを直列につないだFM音色。2秒。
                  1と音色が違って聞こえることを確認します。
3 LIVE MODULATION 発音したまま、変調側3オペレーターのTLを96→64→40→24に変更。
                  各約1秒。TLが小さいほど変調が強くなります。
                  強さごとの音色の違いを確認します。音の大きさは一定とは限りません。
4 LIVE MULTIPLE   変調側の周波数倍率を1→2→3へ変更。各約1秒。
                  キャリアは倍率1のまま。発音を止めずに音色が変わるかを確認します。
5 ENVELOPE        減衰する音を2秒→キーオフ1秒→同じ音を再発音2秒→キーオフ1秒。
                  各発音の立ち上がり後に音が小さくなり、2回目で再び立ち上がるかを確認します。
                  サステインがあるため、2秒の発音中に完全な無音になる必要はありません。
6 SOURCES OFF     DAC/LINEは有効のまま2秒。テスト音が消えていることを確認します。

1→2と4→5には、約1秒のミュートと短い設定待ちがあります。
3と4の各変更は音源のキーを押したままで行います。
2～4では基本周波数は約440Hzですが、変調によって知覚上の高さや音量も変わる場合があります。
小さな背景のサー音はテスト音の消音判定と分けます。左右へ同じモノラル音を出します。

4. 結果の報告
-------------
・1と2の音色の違い、3と4の各設定で音色が変わるか。
・5で2回とも減衰し、2回目が再び立ち上がるか。
・6と終了後にテスト音が消え、左右とも正常か。
・歪み、音切れ、大きなクリック、AMS-22の赤いクリップ表示がないか。
・Thonnyのログ全文。max conversion、deadline misses、SAFE、DONEを含めます。

正常な末尾:
  TIMBRE: all six sections sent.
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped
  DONE: report timbre changes, live parameter response, two decays, L/R and distortion.

Ctrl+Cで中断できます。例外や中断時も、確認済み共通処理でまずLINEミュートとARM=0、
次にメモリ回収・受信停止・I2S停止を行います。正常終了時も同様にYMをリセットします。
エラー時はログ全文を保存し、再実行の前に確認します。
操作できない場合は音量を下げ、Pico USB → JPOWERの順に外してください。
再実行・他の診断の前にはCtrl+Dでソフトリセットします。

5. 設定と検証範囲
-----------------
・4MHz/標準分周、チャンネル1だけ、BLOCK4/FNUM1038（約440Hz）。FM2/3とSSGは停止。
・純音: アルゴリズム7、4番目のオペレーターをTL64、残り3つをTL127。
・直列音: アルゴリズム0、キャリアOP4はTL64、変調側3つはTL40、フィードバック0。
・いずれも4オペレーター全体をキーオン。純音では不要な3つをTL127で抑えます。
・通常はAR31/DR0/SR0/SL0/RR15、減衰音は全4つをAR31/DR12/SR0/SL8/RR15。
・DT0、通常のエンベロープ、キャリアMULTI1。SSG-EG、特殊モード、タイマーは変更しません。
・音色全体の変更はLINE/DACミュート・受信停止中に行います。
・発音中の変更は各3レジスタのTLまたはMULTIだけです。次の変換時も期限超過を監視します。
・新しいレジスタ書き込みは上記の限定値だけを許可します。FMレジスタは読み戻せません。
・受信PIO、DMA、Viper変換、GC、終了処理は前回確認済みの5補助ファイルと同一です。
・PCMゲイン32、ピーク上限4096/32768を維持。実際の音質と音色の差は実機で確認します。
・ホスト70項目（今回6項目）でレジスタ設定、キーを保持した変更、減衰設定と再発音、
  過大レベル設定の拒否、不正受信データとMemoryError時の停止を検証しました。
・MicroPython WASM v1.28.0で音色・パラメータ設定を検証。
  実機と同じ公式v1.29.0のmpy-crossでArm向けコンパイルを検証しました。
・ホストモデルはFMの倍音やエンベロープをエミュレーションしません。
  WASMは物理GPIO/PIO/DMAとArm Viperの実行を検証しません。
・USB-MIDI、I2Cスレーブ、長時間運転、最大音量の評価は含みません。

PC上での検証:
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
ZIPのvalidation.jsonにSHA-256と検証範囲、各テキストログに検証結果を記録しています。
コンパイラー、生成mpy、UF2、メーカー資料、他者の音楽データは同梱しません。

一次資料
--------
Yamaha YM2203のレジスタ定義（TL、MULTI、AR/DR/SR/SL/RR、接続方式）:
https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf
https://docs.micropython.org/en/v1.29.0/library/rp2.DMA.html
https://docs.micropython.org/en/v1.29.0/library/machine.I2S.html
