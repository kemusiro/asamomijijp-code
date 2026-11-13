YM2203C single board Rev C - I2C + live FM/SSG mixer 診断 v1.1
2026-11-11

目的と前提
----------
外部I2CによるSSG発音・消音v1.2は、通常6音と短い7音目を左右で確認し、歪み/音切れなし、
最終消音、HOST PASS・SAFE/DONEまで実機合格しました。命令108、期限消音1回、受信390/送信700が両側で一致。
今回はFMの連続受信・変換・I2S出力を動かしたまま、外部I2CからFM/SSGとミュートを操作します。
同時動作v1の実機試験ではHOSTの最初の1バイト書き込みがEIOで失敗しました。
Rev C停止時は2757ブロック、受信0/送信0、命令0でした。音源の発音命令には到達していません。
このログだけではアドレスNACKや配線、設定、開始順のどれが原因かは確定できません。
v1ではREADY表示時点でI2Cがまだ無効で、FM受信開始後に有効化する順序だったことを修正します。
この順序不備が今回の実機エラーの原因だったと断定するものではありません。
v1.1はI2C有効化後にREADYを表示し、FM受信停止中と開始後に通信を別々に検査します。
I2CとGPIOの設定値も前後で記録します。
v1.1の実機再試験でも、HOST最初の1バイト書き込みがEIOとなりました。
BEFORE LIVEは[804, 66, 1, 1, 0, 3, 3, 3]で、検査した設定とアイドル時の両線Highは期待どおり。
HOSTは識別情報をまだ読み取れておらず、START命令や同時動作には到達していません。
連続受信開始後の処理遅延だけでは、この開始前の失敗を説明できません。
ただし、事前の無音FM検査とI2Sの初期化・動作は既に行われており、その影響は未除外です。
次は既に実機成功したSSG v1.2のZIPを両側へ戻し、同じ配線で再試験します。
Ctrl+C後の追加ログはlive_started=0、blocks=0、受信0/送信0、命令0、max_idle_poll_us=186でした。
同じ配線で既知の成功版SSG v1.2を両側Ctrl+D後に再試験したところ、
こちらもHOST最初の1バイト書き込みでEIOとなり、識別情報読み取り前に停止しました。
現在の障害はFM診断固有とは判断できません。SSG再試験のRev C停止時統計は未報告です。
次はThonnyの接続先ID、両基板の完全な電源再投入、GND/SDA/SCLの導通と待機時電圧を確認します。
ソフトリセットをまたぐ状態や、接続/給電の問題も未除外であり、基板故障と断定しません。
この時点でGPIO、通信方式、期限監視への追加変更は行いません。
その後のSSG v1.2再試験はEIOなしで完走し、ユーザーから発音が報告されました。
命令108、期限消音1回、受信390/送信700が両側で一致し、stale flush 0、HOST PASSとSAFE/DONEを再確認。
接続先確認・完全な電源再投入を案内した後の復旧ですが、復旧の直接原因までは確定していません。
FM/I2C同時動作へ戻る際は、下記の全ファイルを両側へ上書きし、完全な電源再投入後にv1.1を再試験します。
この再試験も最初のポインター書き込みがEIOとなり、STARTには到達しませんでした。
最新再試験の停止時統計は未報告ですが、READY前の設定値は以前と同じでした。
次はI2C-ISOLATION-README.txtの無音段階診断で、FM版で追加した初期化のどの段階から
通信が失敗するか確認します。本診断の通信・音声コードへの追加変更はしていません。
無音段階診断は実機で全6段階PASS、各段階173バイト受信/458バイト送信、stale flush 0でした。
FM事前検査も56ブロック、ピーク4064、最大変換1111us、期限超過0で通りました。
最新の次試験はI2C-FM-STAGED-README.txtの段階起動v1.2です。
成功した起動順を踏襲して最後にSSG無音設定を検査し、同じ連続制御へつなぎます。EIO原因は未確定です。

1. 接続
-------
前回と同じ配線・GPIO・給電です。外部I2Cは接続したままで実行します。
  JHOST 1 GND → 操作側Pico GND（物理3番など）
  JHOST 2 SDA → 操作側GP0（物理1番）
  JHOST 3 SCL → 操作側GP1（物理2番）
  JHOST 4はGNDで、3本配線では未接続でよい。
3.3V信号、R1/R2各4.7kΩプルアップ、操作側はハードウェアI2C0・10kHzです。
電源線同士を接続しません。結線変更時は両方電源OFF、テスト中は両方へ給電します。
Rev Cは従来のJPOWERとPico USB、操作側は自分のUSBで給電します。

JLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
AMS-22は別バッテリーのDC 5V給電とし、PCとのUSB接続を外します。
DIRECT MONITOR=ON、LOOPBACK=OFF、MIC/GUITAR未接続、GAIN最小。
両方のボリュームを低めにします。UF2の書き直しは不要です。

2. ファイルと実行
-----------------
ZIPのtarget/から、Rev C側Picoの最上位へ9ファイルすべてを保存・上書きします。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_fm_ssg_check.py
  rev_c_ssg_check.py
  rev_c_i2c_target_check.py
  rev_c_i2c_ssg_target.py
  rev_c_i2c_fm_target.py
ZIPのhost/から、操作側Picoの最上位へ3ファイルすべてを保存・上書きします。
  rev_c_i2c_host_check.py
  rev_c_i2c_ssg_host.py
  rev_c_i2c_fm_host.py
v1からの変更は両側の末尾の実行ファイル2個です。混在を避けるため、全ファイルを上書きしてください。
新しい署名RCMIX02!を使うため、古いHOSTとの組み合わせでは検査に合格しません。
main.py / boot.pyには保存しません。host用ファイルは必ず操作側で実行します。

前回の2つのThonnyで、それぞれ別のPicoポートに接続します。
今回の再試験では、ファイル転送後に両側を停止し、両方のPico USBとRev C JPOWERをすべて外して5秒待ちます。
JPOWER → 両方のPico USBの順に接続し、Thonnyをそれぞれのポートへ再接続します。
SSG版から共通HOSTファイルも戻す必要があるため、末尾の実行ファイルだけの転送では不十分です。
両方のシェルでCtrl+Dを押し、以下の順で実行します。
1) Rev C側でrev_c_i2c_fm_target.pyを開き、F5。
   冒頭: YM2203 Rev C / I2C + live FM mixer target check v1.1
   バスと無音FM変換の事前検査が成功した後、約5秒待ってREADYを表示します。
   I2C CONFIG BEFORE LIVE: [804, 66, 1, 1, 0, 3, 3, ...]
   READY: I2C enabled, FM capture STOPPED address=0x42 transport=1.1 ...
2) READYを確認してから、操作側でrev_c_i2c_fm_host.pyを開き、F5。
   冒頭: YM2203 Rev C / I2C + live FM mixer HOST check v1.1 / OTHER Pico only
   BUS: I2C(0, freq=..., scl=1, sda=0, timeout=500000)を確認します。
3) FM受信停止中に識別情報、64回の状態読み取り、消音中の32回のKEEP応答を確認します。
   PASS: initial I2C checks while FM capture STOPPED
4) HOSTがSTARTを送り、Rev Cが連続受信を開始し、設定を再確認します。まだ無音です。
   PASS: live capture START acknowledged
5) FM受信中の8回の状態読み取りと8回のKEEP応答を検査します。
   PASS: 8 stable reads + 8 KEEP commands with FM capture running
   ここまで成功してから5秒待って発音します。
受信開始後の通信は音声ブロック間で処理するため、開始前より状態読み取りに時間がかかります。
事前検査は数秒、全体はHOST開始から約30～45秒が目安です。Rev C側は演奏中に進捗ログを出しません。

3. 九つの比較
-------------
各区間は約2秒。1と2の後にはSTOPと約1秒の無音があります。

1 FM ONLY       高い約440HzのFMだけ。
2 SSG ONLY      低い約220HzのSSG Aだけ。
3 FM + SSG      高いFMと低いSSGが重なる。
4 DAC MUTE      FMだけが消え、低いSSGが残る。FMの受信・変換は継続。
5 DAC RESTORE   FMとSSGに戻る。
6 LINE MUTE     両方のテスト音が消える。音源と受信・変換は継続。
7 LINE RESTORE  FMとSSGに戻る。
8 STOP          FMキーオフ、SSG音量0、DAC/LINEミュート。約2秒無音。
9 LEASE         FM+SSGを鳴らしてKEEPを止める。約1秒で両方が消え、その後は無音。

最後はSTOPとFINISHを送り、終了します。左右へ同じモノラル音を出します。
切り替え時には、I2C応答とI2S出力バッファによる短い遅延があります。
各区間の定常部分で、音の種類・消音の独立性・歪み/音切れを比較してください。
高いFMは確認済みの単純なキャリアです。複雑な音色や複数FMチャンネルは今回扱いません。

4. ログと報告
-------------
HOSTの末尾:
  PASS: both sources lease-muted without a STOP command
  HOST PASS: concurrent live FM/I2C commands, independent mutes and lease mute verified.
  HOST I2C STATS: ...
  HOST SAFE: GP0/GP1=input ...
Rev Cの末尾:
  LIVE I2C: live_started=1 blocks=... peak=... max_poll_us=... max_idle_poll_us=... commands=... lease_expirations=1 received=... sent=...
  I2C CONFIG BEFORE LIVE: [804, 66, 1, 1, 0, 3, 3, ...]
  I2C CONFIG AFTER LIVE:  [804, 66, 1, 1, 0, 3, 3, ...]
  LAST CONTROL STATE (before reset): ...
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 live/I2S=stopped
  DONE: report FM/SSG modes, independent mutes, lease mute, L/R and HOST PASS.

max_poll_usはFM受信中のI2C処理呼び出しの最大所要時間で、max_idle_poll_usは開始前の値です。
max conversionは音声変換の最大所要時間です。
blocksは連続変換した11.25msブロック数。待機時間も含むため固定値ではありません。
peakはFMデジタル信号の最大値で、SSGやアナログ合成音は含みません。
命令数と転送数はKEEP回数により変化します。前回の108/390/700との一致は求めません。
live_started=0ならHOSTのSTARTを実行する前で、blocksは0として表示します。
設定配列は順にCON、7bitアドレス、ENABLE、ENABLE_STATUS、SLV_DATA_NACK_ONLY、
SDAのFUNCSEL、SCLのFUNCSEL、両線の入力レベルです。先頭7個の期待値は上記のとおり。
最後の値はbit0=SDA、bit1=SCLで、0～3。通信中の値は変化するため、3を必須条件にしません。
設定が一致しない場合は停止し、異常な値も記録します。GPIOの機能は検査のために書き換えません。
AFTER LIVEは開始後にのみ記録し、受信中のUSB出力を避けるため停止後に表示します。

9区間の聞こえ方、両ミュート、最後の自動消音、左右、歪み/音切れと、両方のログ全文を報告してください。
背景の小さなサー音は、テスト音の消音判定とは分けます。
失敗時はHOSTの最後のエラー行まで保存し、Rev CもCtrl+Cで停止して追加ログを保存してください。
上記3種類のPASSのどこまで進んだか、設定配列BEFORE/AFTERと両方の全文を報告してください。
再実行は両方Ctrl+D → Rev C READY → HOST実行の順です。

5. 処理方式と制約
-----------------
FM受信PIO、2本のDMAリング、625→540フレーム変換、I2S形式、音量上限、期限監視は以前と同一です。
共通runには接続案内の引数だけ追加しています。GCを有効にし、異常時の消音・リセット・停止も維持します。
I2Cの受信と応答は音声1ブロックごとに実行します。ハードウェアのクロックストレッチで応答待ちを扱います。
音声変換中、I2S書き込み中にはPython側のI2C処理を実行できないため、応答に数十msかかる場合があります。
音色やSSG音程は受信停止中に事前設定し、演奏中のレジスタ変更はFMキー操作とSSG Aの音量だけに限定します。
以前のSSG診断の50ms待ちを含む発音設定は、連続変換中には呼びません。
明示的GC、メモリ計測、USB出力も連続変換中に行いません。自動GCは有効のままです。
I2C処理が長すぎる場合も既存の期限監視で失敗・消音停止します。失敗を無視して継続しません。

通信部は前回のtransport=1.1です。GPIOと回路は変更しません。
通信途絶による消音はPythonの処理が動いている範囲で有効で、独立したハードウェア保護ではありません。
例外/中断時はLINE/DACをミュートしARM=0にしてから受信とI2Cを停止します。
操作できない場合は音量を下げ、Pico USB → JPOWERの順に電源を外します。
READY待ちを含む診断時間は最大5分で、製品の演奏時間制限ではありません。
同時動作の検証段階です。実機での最大遅延や音質、長時間動作はまだ確認していません。
正式な音源API、楽曲/予約演奏、任意音色、400kHz、USB-MIDIは含みません。

6. 診断専用プロトコル
---------------------
0x42、署名RCMIX02!。v1や前回のSSG用HOSTとは署名が違い、取り違えると発音前に停止します。
書き込みは[0x20, opcode]の2バイト+STOPで1命令。
  0 STOP / 1 FM / 2 SSG / 3 BOTH / 4 DAC MUTE / 5 LINE MUTE / 6 KEEP / 7 FINISH / 8 START
STARTは無音で連続受信を開始します。開始前の発音モードやSTARTの重複は異常として停止します。
開始後はモード変更で連続受信を再起動しません。STOPや期限消音でも受信は継続します。
0x10から4バイトで[実行確認カウンター, 最後の命令, モード0～5, 期限フラグ0/1]を読みます。
KEEPは有効モードの1秒の通信期限だけ更新し、音源レジスタを書き直しません。
期限超過時は両音源と出力を止め、モード0・期限フラグ1にします。KEEPだけでは再発音しません。
正式な公開音源APIではなく、この組立診断だけの制御です。

7. PC上での検証
---------------
ホスト112項目（FM/I2C同時動作8項目）。音声とI2Cバイトの交互実行、9区間の制御、途絶消音、
連続受信を再起動しないこと、既存の実際の期限監視、通信が50ms遅れた場合の停止、
中断/MemoryError時の消音と受信/I2Cの解放を確認します。
READYでI2C有効かつ受信停止の検査はv1に対して失敗する回帰テストです。
開始後にGPIO設定を壊す模擬試験で、設定不一致の記録と消音停止も確認します。
MicroPython WASM v1.28.0では実際のHOST・制御処理を模擬音源/バス/時計で実行します。
WASMではSTART完了も模擬します。実機のGPIO設定やPIO/DMA/I2S/I2C並列動作、性能は検証しません。
公式MicroPython v1.29.0 mpy-crossで今回変更した2ファイルをArm向けにコンパイルします。
native-core-validation.txtは、受信/変換/期限監視などのASTが以前の実機確認済み版と同一である検証です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
各ログとvalidation.jsonを同梱します。UF2、コンパイラー、生成mpyは同梱しません。

設定値の一次資料（Pico SDK 2.2.0）:
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/addressmap.h
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/io_bank0.h
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_structs/include/hardware/structs/io_bank0.h
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/sio.h
