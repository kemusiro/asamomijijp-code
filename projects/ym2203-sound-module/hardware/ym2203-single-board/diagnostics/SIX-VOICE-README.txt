YM2203C single board Rev C - FM3チャンネル・6音同時発音診断 v1
2026-11-11

目的と前提
----------
前回のFM+SSGミキサー診断は、全9区間が左右正常、DAC/LINEミュートの独立性、
歪み・音切れなし、SAFE/DONEまで実機で確認されています。
FMチャンネル2/3と、FM3音+SSG3音の同時発音を確認する診断です。
2026-11-11に全10区間が左右とも表どおり、独立ミュート、歪み・音切れなし、
SAFE/DONEまでユーザー実機で確認されました。
各FM単音ピーク992、3音合成2976、最大変換1117µs、期限超過0、空きメモリ409280バイト。
次の音色診断はFM-TIMBRE-README.txtを参照してください。
受信PIO、DMA、Viper変換、メモリ回収、終了処理は前回確認済みのモジュールをそのまま使います。

1. 接続
-------
前回と同じ配線と給電です。部品・GPIOを変更しません。
・JPOWERは今のモバイルバッテリー、Pico USBはThonnyのPC。
・AMS-22は別バッテリーのDC 5V給電、PCとのUSBは外します。
・JLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
・DIRECT MONITOR=ON、LOOPBACK=OFF、MIC/GUITAR未接続、GAIN最小。
・外部ホストI2Cは未接続。
音量は低い位置から始め、全区間を同じ設定で比較してください。
最初のFM単音は意図的に小さくしています。
電源を入れ直す場合はJPOWER → Pico USB、外す場合はPico USB → JPOWERの順です。

2. ファイルと実行
-----------------
ZIPを展開し、以下6ファイルをPicoの最上位へ保存・上書きします。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_fm_ssg_check.py
  rev_c_six_voice_check.py
新しいのは最後の1ファイルで、残り5ファイルは前回と同じ内容です。
main.py / boot.pyにはしません。

保存後、ThonnyのシェルでCtrl+Dを押し、rev_c_six_voice_check.pyを開いてF5で実行します。
冒頭は YM2203 Rev C / FM three-channel + six-voice check v1 です。
以前と同じバス診断・無音の連続FM事前検査の後、約5秒待って比較を始めます。
事前検査は従来と同じFMチャンネル1・TL48で行い、比較時に3チャンネルともTL64へ下げます。

3. 10区間の確認
---------------
各区間は約2秒です。1～4の各区間後と9→10の間には約1秒の無音があります。
レジスタ設定とI2S排出・受信再開のため、その前後にも短い待ちがあります。

1  FM CH1 ONLY     チャンネル1だけ、ド（C4、約262Hz）。
2  FM CH2 ONLY     チャンネル2だけ、ミ（E4、約330Hz）。
3  FM CH3 ONLY     チャンネル3だけ、ソ（G4、約392Hz）。
4  THREE FM        FM3音のド・ミ・ソの和音。
5  SIX VOICES      上のFM和音と、1オクターブ低いSSGのド・ミ・ソ。計6音。
6  DAC MUTE        高いFM和音が消え、低いSSG和音だけが残る。
7  DAC RESTORE     6音に戻る。
8  LINE MUTE       全6音のテスト音が消える。
9  LINE RESTORE    6音に戻る。
10 ALL SOURCES OFF DAC/LINEは有効のまま、全音源を止める。テスト音は消える。

FM各単音と3音の和音ではdigital peakも表示します。これはFMデータのピークで、
アナログで合成されるSSGの振幅は含みません。
全体は初期検査と5秒待ちを含めておよそ35秒です。

4. 報告する内容
---------------
・1、2、3がそれぞれ聞こえ、ド→ミ→ソと高くなるか。
・4でFMの和音、5で高い和音+低い和音になるか。
・6で低い和音だけが残り、8で全テスト音が消えるか。
・7と9で6音が戻り、10と終了後にテスト音が消えるか。
・全区間で左右正常か、歪み・音切れ・大きなクリックがないか。
・音量差、AMS-22の赤い入力クリップ表示があるか。
・Thonnyのログ全文。digital peak、max conversion、deadline misses、SAFE/DONEを含めます。
背景の小さなサー音は、テスト音の消音判定とは分けてください。

期待する末尾:
  SIX VOICE: all ten sections sent.
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped
  DONE: report FM CH1/2/3, both chords, independent mutes, L/R and distortion.

5. 停止とエラー
---------------
Ctrl+Cで中断できます。終了・例外時は確認済みの共通処理でLINEミュート、ARM=0、
メモリ回収、受信停止、I2S停止を行います。YMリセットでFM3チャンネルとSSGも止まります。
例外が出た場合は全文を保存し、再実行の前に確認します。
操作できない場合は音量を下げ、Pico USB → JPOWERの順に外します。
再実行や別の診断の前もCtrl+Dでソフトリセットしてください。
No clear FM signal on channel ... は、その単独チャンネルの信号変化が小さいことを示します。
level exceeded はデジタル音量上限を超えたため中止したことを示します。
いずれもログだけで音源ICの故障とは判断しません。

6. 設定と範囲
-------------
・各FMチャンネルはアルゴリズム7、スロット1だけをキーオンする単純なキャリアです。
・各キャリアのTLは64。前回の48から16段（約12dB）減衰し、3音合成の余裕を取ります。
  他の3スロットはTL127かつキーオフ。フルスケールや複雑な4オペレーター音色ではありません。
・FMの4MHz/標準分周を維持し、各チャンネルはBLOCK4・FNUM617/778/925。
・SSGはperiod478/379/319、約130.75/164.91/195.92Hz、各固定レベル7。
・SSGノイズ・エンベロープ、FM特殊チャンネルモード、プリスケーラー、GPIOは変更しません。
・追加レジスタ書き込みは、この静かな3キャリアに必要な値だけの許可リストです。
・FM設定とSSG設定はLINEミュート・受信停止中に行います。
・DAC/LINEミュート中もFM3音の受信と変換は続きます。
・FMデジタルのピーク上限4096/32768は維持します。実際のアナログ合成音のクリップは
  ピーク値だけでは判定できないため、耳とAMS-22の表示で確認します。
・今回の合格は単純な6音構成に対するものです。最大音量、複雑な音色、USB-MIDI、
  I2Cスレーブ、長時間運転は別途検証します。

7. PC上の検証
-------------
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs

計64項目（今回の6音診断5項目）。各FMキーの独立性、単音/3音/6音とミュート状態、
静かな音色設定、チャンネル2の信号欠落、合成の過大レベル検出、書き込み範囲制限を確認。
公式MicroPython v1.29.0のmpy-crossで新規プログラムをArm向けにコンパイル。
MicroPython WASMでも3キャリア・キーオン/オフ・SSG低音和音のレジスタ設定を確認。
WASMやホストのモデル検証は、実機のアナログ音質・DMAタイミングを代替しません。
validation.jsonはSHA-256と検証範囲、各テキストログは検証結果です。
コンパイラー、生成mpy、UF2、メーカー資料、他者の音楽データは同梱しません。

一次資料
--------
https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf
https://docs.micropython.org/en/v1.29.0/library/rp2.DMA.html
https://docs.micropython.org/en/v1.29.0/library/machine.I2S.html
