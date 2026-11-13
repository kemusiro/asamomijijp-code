YM2203C single board Rev C - 連続FM + SSGミキサー診断 v1
2026-11-11

目的と確認済みの状態
--------------------
連続FM診断v1.1はユーザー実機で音階2回の左右発音・音切れと歪みなし・SAFE/DONEまで
確認されました。最大変換1123us、期限超過0、事前検査の空きメモリ419040バイトでした。
今回はその受信・変換処理を使い、FMとSSGのアナログ合成とミュートの独立性を調べます。
混合出力の全9区間はユーザー実機で左右正常、ミュートの独立性、歪み・音切れなし、
SAFE/DONEまで確認済みです。max conversion=1114us、deadline misses=0、free=415712でした。
次段階はSIX-VOICE-README.txtのFM各チャンネルと6音同時発音の診断です。

1. 接続
-------
前回と同じ配線・給電を使用します。GPIO・部品変更はありません。
・JPOWERは今のモバイルバッテリー、Pico USBはThonnyのPCへ。
・AMS-22は別バッテリーのDC 5V給電、PCとのUSBは外します。
・JLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
・DIRECT MONITOR=ON、LOOPBACK=OFF、MIC/GUITAR未接続、GAIN最小。
・外部ホストI2Cは未接続。
最初はRev CとAMS-22の音量を低くします。全区間を同じ音量設定で聴き比べてください。
電源を入れ直す場合はJPOWER → Pico USB、外す場合はPico USB → JPOWERの順です。

2. 保存と実行
-------------
ZIPを展開し、同梱5ファイルすべてをPicoの最上位へ保存・上書きします。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_fm_ssg_check.py
rev_c_fm_live.pyには比較手順を共通の診断実行枠へ渡す引数を追加したため、今回の同梱版を使います。
受信PIO・DMA・Viper変換・期限チェック・メモリ対策と終了処理は変更していません。
main.py / boot.pyにはしません。

保存後にThonnyのシェルでCtrl+Dを押し、rev_c_fm_ssg_check.pyを開いてF5で実行します。
冒頭は YM2203 Rev C / live FM + SSG mixer check v1 です。
無音バス診断と連続FMの無音事前検査が成功すると、約5秒後に比較を始めます。

3. 9区間の聴き比べ
------------------
番号はログの先頭と対応します。各区間は約2秒です。
1  FM ONLY       約440HzのFM音だけ。
2  SSG A ONLY    約220Hzの低いSSG音だけ。
3  FM + SSG A    高いFM音と低いSSG音が同時に聞こえる。
4  DAC MUTE      FMだけが消え、低いSSG音は残る。
5  DAC RESTORE   高いFM音と低いSSG音に戻る。
6  LINE MUTE     両方のテスト音が消える。
7  LINE RESTORE  高いFM音と低いSSG音に戻る。
8  FOUR VOICES   FM約440Hz + SSG A/B/Cのド・ミ・ソ。厚みのある合成音。
9  SOURCES OFF   DAC/LINEは有効だが、両音源を止めたためテスト音は聞こえない。

1→2、2→3、7→8、8→9の間には約1秒のミュートが入ります。
SSG設定を安全に更新するため、その前後にも短い待ち・受信再開があります。
設定変更とSSGレジスタの読み戻しは、LINEミュート・受信停止の状態で行います。
FMが鳴る区間はライブ受信です。DACをミュートしている区間も受信と変換は続けます。
全体は初期検査・5秒待ちを含めておよそ30秒です。

4. 報告内容
-----------
・1と2がそれぞれ単独で聞こえるか、3で高い音と低い音が両方聞こえるか。
・4で低いSSG音が残り、6で両音が消えるか。
・5と7で混合音が戻るか、8で合成音が厚くなるか。
・9と終了後にテスト音が消えるか。
・全区間で左右両方から聞こえるか。
・FMとSSGの音量差、合成時の歪み・音切れ・大きなクリック。
・Thonnyのログ全文。末尾のmax conversion、deadline misses、SAFE/DONEも含めます。

FMとSSGは違う波形・音量段階なので、同じ大きさになるとは限りません。
SSGの倍音による鋭い音色は意図したものです。合成時に新しく生じる歪み・音切れを報告してください。
小さな背景のサー音はテスト音の消音判定と分けます。
デジタルのピーク検査だけではアナログミキサーやAMS-22のクリップを検出できません。
AMS-22の入力クリップ表示が赤くなる場合も報告してください。

期待する末尾:
  MIXER: sequence complete; compare all nine sections and both L/R.
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped
  DONE: report sections 1..9 on L/R, mute independence, balance and distortion.

5. 停止とエラー
---------------
Ctrl+Cで中断できます。異常・メモリ不足・中断時も共通の処理でLINEをミュート、ARM=0、
メモリ回収、受信とI2S停止を行います。YMのリセットでSSGも止まります。
失敗時は全文を保存し、繰り返し実行する前に確認します。
操作できない場合は音量を下げ、Pico USB → JPOWERの順に外してください。
次の診断や再実行の前もCtrl+Dでソフトリセットします。

6. 設定と範囲
-------------
・FMは確認済みと同じ1チャンネル・1キャリア・TL48・固定ゲイン32、約440Hz。
・SSG単音はAのみ、period=284（約220.07Hz）、固定レベル10。前回のSSG診断より上げません。
・SSG三和音はperiod=239/190/159、約261.51/328.95/393.08Hz、各固定レベル7。
・SSGノイズとエンベロープは使いません。汎用I/O・プリスケーラー・GPIOは変更しません。
・共通run()に比較用バスと手順を渡す任意引数を追加しています。引数なしのFM音階診断は同じ動作です。
・SSGのミキサー設定は0x3F（全消音）、0x3E（A音のみ）、0x38（A/B/C音）のみに制限します。
・5秒待ち、プリセット切替など受信停止中にはI2Sへゼロを送り、古いPCMを排出します。
・各区間では135msの受信・変換でI2Sを満たしてからLINEを有効にします。
・FM3チャンネル同時、最大音量、複雑な音色、USB-MIDI、I2Cスレーブ、長時間運転は未検証です。
  この診断の終了を、全機能や最大出力の合格とは扱いません。

7. 検証
-------
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_live_memory.mjs

計59項目（混合診断5項目）。FM/SSG独立発音・両方のミュート・四声・音源OFFの命令状態、
設定中のLINE/受信停止、読み戻し不一致、同時発音中の中断、レベル/ノイズ制限を確認します。
公式MicroPython v1.29.0のmpy-crossでArm向けに同梱の新規・変更プログラムをコンパイル。
MicroPython WASMでもSSGの単音・和音・消音レジスタ設定と既存のメモリ回帰検証を確認。
WASMはArmのネイティブ命令や実機GPIO/DMA・アナログ音質の検証を代替しません。
validation.jsonはSHA-256と検証範囲、各テキストログは検証結果です。
配布はソースのみで、UF2・コンパイラー・生成mpy・他者の音楽データは含みません。

一次資料
--------
https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf
https://docs.micropython.org/en/v1.29.0/library/machine.I2S.html
https://docs.micropython.org/en/v1.29.0/library/rp2.DMA.html
https://zoomcorp.com/manuals/ams-22-ja/
