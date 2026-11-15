YM2203C single board Rev C - 連続FM受信・PCM変換・音階診断 v1.1
2026-11-11

目的
----
確認済みの短時間のFM取得・復号・DAC再生から、連続処理へ進む段階です。
YM2203Cが実際に出すFMデータを受信しながら48kHzのPCMへ変換し、DACから再生します。
録音済み1周期のループやソフトウェアで生成した代わりの正弦波は使いません。
v1の実機では無音事前検査（peak=4064）が成功し、C4/D4の途中でMemoryErrorになりました。
SAFE表示はなかったため、初版を再実行せず、音量を最小にしてCtrl+DでPicoをリセットします。
リセットに応答しない場合はPico USB → JPOWERの順に外します。
v1.1では頻繁な大整数のビット演算とGC停止を修正し、メモリ不足時の終了処理を補強しました。
PIO・DMA・変換式・GPIO・演奏内容は同じです。v1.1はユーザー実機で音階2回の左右発音、
音切れ・歪みなし、SAFE/DONEまで確認済みです。
ログはpeak=4064、free=419040、max conversion=1123 us、deadline misses=0でした。
次段階はFM-SSG-README.txtの混合出力診断です。

接続と事前準備
--------------
・公式Pico 2 MicroPython v1.29.0 Arm版を引き続き使います。UF2の入れ替えは不要です。
・JPOWERは現在のモバイルバッテリー、Pico USBはThonnyを使うPCへ接続します。
・AMS-22は別のモバイルバッテリーからDC 5Vへ給電し、PCとのUSBは外します。
・JLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
・DIRECT MONITOR=ON、LOOPBACK=OFF、MIC/GUITAR未接続、GAIN最小。
・外部ホストI2Cは未接続。Rev CとAMS-22の音量は低くしておきます。
・部品、配線、GPIOは変更しません。
・電源を入れ直す場合はJPOWER → Pico USB、外す場合はPico USB → JPOWERの順です。

ファイルを準備する
------------------
ZIPを展開し、同梱4ファイルをThonnyでPicoの最上位へ保存・上書きします。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
前の3つは確認済みの補助モジュールです。main.py / boot.pyにはしません。
PCに置いたままではPicoでimportできない場合があります。

実行
----
1) 保存後、ThonnyのシェルでCtrl+Dを押してソフトリセットします。
2) rev_c_fm_live.pyを開き、F5で手動実行します。
3) 以前と同じ無音バス診断に続き、新しい連続受信処理を両音声ゲートOFFで試します。
   内部でキーオフ → キーオン → キーオフを行い、信号変化と消音を検査します。
   失敗時は音声ゲートを上げずに終了します。
4) PASS: new serial receiver and live conversion preflight; peak=... が表示されたら、
   約5秒後に次の音階を演奏します。音量を低い位置から少しずつ調節してください。

   ド レ ミ ファ ソ ファ ミ レ ド  → 約1秒の無音
   ド レ ミ ファ ソ ファ ミ レ ド  → 無音、終了

各音は約0.55秒、ドはC4（約262Hz）、ソはG4（約392Hz）です。
音源のキーを押したまま周波数レジスタを変更するので、音と音の間に明示的な休符はありません。
今回の音階部分は約11秒の有限診断です。製品の演奏時間上限を設けるものではありません。
I2Sのキューによってログの音程変更表示から音が変わるまで約0.1秒弱の遅れがあります。

ログ例
------
  YM2203 Rev C / live FM scale v1.1
  ...STATUSと6行のPASS reg=...
  PASS: new serial receiver and live conversion preflight; peak=... free=...
  C D E F G F E D C, twice. Sound starts in about 5 seconds.
  LIVE 1/2 / C4
  LIVE 1/2 / D4
  ...G4、F4、E4、D4、C4...
  LIVE 2/2 / C4
  ...
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped
  DONE: report both scales on L/R, pitch changes, gaps, and any clicks/dropouts.

確認・報告
----------
・左右両方から音階が2回聞こえるか。
・ド→レ→ミ→ファ→ソ→ファ→ミ→レ→ドと音程が変わるか。
・音が途中で途切れたり、チリチリ・クリック・歪みが増えたりしないか。
・2回の音階の間と終了後にテスト音が消えるか。
・Thonnyのログ全文。特にmax conversionとdeadline misses、例外があればその全文。
PASS/DONEは命令の処理結果です。実際の音質・左右出力は聴いて確認します。
既知の小さなサー音は今回のテスト音や途切れとは分けて評価してください。

停止・エラー
------------
Ctrl+Cで中断できます。終了・例外・中断時はLINEをミュートし、ARM=0で音源をリセットして
から受信DMA/PIOとI2Sを停止します。
音声許可とARMのCメソッドを事前に保持し、例外時はメモリ確保や表示より先に呼び出します。
続いて予備の4KiBを解放してGCを有効化・回収し、通常の終了処理を行います。
診断中はGCを有効に保ち、終了後に診断前の有効／無効状態へ戻します。
ログ全文を保存し、エラー時は繰り返し実行する前に確認してください。
操作に応答しない場合は、音量を下げてPico USB → JPOWERの順に外します。
別の診断を実行する前、再実行の前もCtrl+Dを押します。

deadline missed: バッファの処理期限を超えました。RAM内のアドレスリングを併用し、
DMAが同じバッファを再使用しても、その受信用メモリ範囲の外へ書かない構成です。
データを失ったまま再生を続けず、消音・停止します。
receive FIFO stalled / DMA bus error / ownership lost: 連続データの正当性を失うため中止します。
invalid exponent or level exceeded: 復号データの形式または音量に異常があり中止します。
これらはICの故障を確定するメッセージではありません。実機の処理時間・新しい受信PIOを
評価するための診断です。

仕組みと範囲
------------
・既に承認されたGP16/17/18の入力を、PIO0 SM0で読みます。出力へ変更しません。
・新しい受信PIOはSHの立ち下がりに同期し、24回のCLK立ち上がりでSDを取り込みます。
  下位側の11無効ビットを捨て、有効な13ビットを復号します。
・受信625フレーム（約11.25ms）を交互のDMAバッファに格納し、540フレームのPCMへ変換。
  4MHz/72 = 約55.556kHz → 48kHzの比125:108を使う線形補間です。
・各受信バッファは4KiB境界に配置し、DMAの4KiBアドレスリングを設定します。
  通常の625ワード分を処理したら、そのチャンネルの書き込み先と転送数を戻します。
・変換はMicroPythonのViperを使用します。ポインターへのアクセス長は入力625ワード、
  出力540フレームの固定範囲です。C/C++ファームウェアへの変更は行いません。
・前回のYM形式と同じ復号に固定ゲイン32を適用します。TL48の実測ピーク127は約4064になります。
  出力ピークは4096/32768に制限し、制限が発生した場合も正常な診断としては扱わず停止します。
・I2Sは48kHz、16bitステレオ。左DACへ送り、主基板のアナログ回路で左右へ複製します。
・受信は1 SM、I2Sは別の空きSMを使います。両者を同時に動かすことも今回の実機検証対象です。
・自動GCを有効に保ち、受信停止中にも明示的に回収します。正常なDMAステータスの検査には
  大整数マスクを使わず右シフトを使います。GCによる処理の一時停止も期限チェックの対象です。
・FMチャンネル1、アルゴリズム7の1キャリア、SSG消音を維持。GPIO・汎用I/O・プリスケーラーは変更しません。
・同時FM3音、FM+SSG、複雑な音色、USB-MIDI、I2Cスレーブ、24時間運転は未検証です。
・独立した音源クロックとI2Sクロックの長時間ドリフトを補償する仕組みは今回含めません。
  長時間化の前に、実測した余裕とキューの増減を評価する必要があります。

PC上の検証
----------
ホストテストは現在59項目。連続FMは12項目、混合出力診断は5項目です。
受信PIOの理想波形シミュレーション、補間・境界・音量制限、DMAリングのアドレス境界、
ピンポンバッファの待機と再設定、タイマー折り返し、音階、処理遅延・不正データ・Ctrl+C時の消音を確認。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_live_memory.mjs

メモリ回帰検証では256KiBのMicroPython WASMヒープで、初版の大整数マスクとGC停止による
MemoryErrorを再現します。修正後の右シフト検査5万回と、GCを有効にした実際のStream.check
5万回の完了・回収後のメモリ量を確認します。メモリ不足を注入した際にも消音とSAFE表示まで
完了することをホスト側で検証します。

公式MicroPython v1.29.0のmpy-crossでArm向けViperをコンパイルし、同版のPIOアセンブラーで
受信命令列を検証しています。WASMではViperデコレーターを外した同じ計算を確認します。
WASMやホストテストでArmのネイティブ命令・実機DMAの性能を測ったものではありません。
配布はPythonソースです。検証用mpy-cross・生成mpy・メーカー資料・UF2は同梱しません。
validation.jsonにSHA-256と検証範囲、各テキストログに検証結果を記録しています。

一次資料
--------
https://docs.micropython.org/en/v1.29.0/reference/speed_python.html
https://docs.micropython.org/en/v1.29.0/library/rp2.DMA.html
https://docs.micropython.org/en/v1.29.0/library/rp2.StateMachine.html
https://docs.micropython.org/en/v1.29.0/library/machine.I2S.html
https://raw.githubusercontent.com/micropython/micropython/v1.29.0/ports/rp2/rp2_dma.c
https://raw.githubusercontent.com/micropython/micropython/v1.29.0/ports/rp2/machine_i2s.c
https://www.quarter-dev.info/archives/yamaha/YM3014B.pdf
