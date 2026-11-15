YM2203C Rev C - I2C初期化の段階切り分け診断 v1
2026-11-11

目的と分かっていること
----------------------
SSG用v1.2は、電源再投入を案内した後の再試験で発音し、HOST PASS・SAFE/DONEまで完走しました。
命令108、期限消音1回、受信390/送信700が両側で一致し、stale flush 0でした。
その後FM/I2C用v1.1へ戻した試験では、再び最初のポインター書き込みがEIOとなりました。
BEFORE LIVE=[804,66,1,1,0,3,3,3]で、HOSTは識別情報やSTARTまで到達していません。
今回の停止時統計はまだ未報告です。以前の同症状では受信0/送信0でした。
この再現経過からFM版で追加した初期化の影響を調べますが、原因はまだ確定していません。
EIOをアドレスNACKや基板故障と断定しません。

この段階診断v1は、実機で全6段階PASS、HOST PASS・SAFE/DONEまで完走しました。
各段階の受信173/送信458、保護書き込み無視1、stale flush 0。
FM事前検査のピーク4064、56ブロック、最大変換1111us、期限超過0。
I2C CONFIGは全段階[804,66,1,1,0,6,16,90,90]、GP20/21 FUNCSEL=3、入力ビット3でした。
次はI2C-FM-STAGED-README.txtの段階起動FM/I2C診断へ進みます。以前のEIO原因は未確定です。

新しい試験は無音のまま、音声関連の初期化を累積して各段階の通信を検査します。
GPIO割り当て・基板・共通I2C通信処理・ネイティブ音声変換コードは変更していません。
LINE_ALLOWとDAC_ALLOWは全区間0で、出力を許可しません。
段階4ではYM内部でFMキーオンしますが、PCMを出力する際もDACとLINEはミュートしたままです。
合格しても発音や同時変換中の通信性能を確認したことにはなりません。

1. 接続と保存先
---------------
配線・給電はSSG診断で成功した構成のままです。
  Rev C JHOST 1 GND -> 操作側Pico GND（物理3番など）
  Rev C JHOST 2 SDA -> 操作側GP0（物理1番）
  Rev C JHOST 3 SCL -> 操作側GP1（物理2番）
  JHOST 4はGND。3本配線の場合は未接続でよい。
3.3V I2C、Rev C R1/R2各4.7kΩプルアップ、操作側ハードウェアI2C0・10kHz。
JHOSTに電源端子はありません。操作側の3V3/VBUS/VSYSはつなぎません。
配線変更時は両基板の電源を切ります。テスト中は両基板へ給電します。
AMS-22は従来の接続のまま、両方の音量を低めにしてください。

ZIPのtarget/からRev C側Picoの最上位へ、次の6ファイルすべてを保存します。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_i2c_target_check.py
  rev_c_i2c_isolation_target.py
ZIPのhost/から操作側Picoの最上位へ、次の2ファイルを保存します。
  rev_c_i2c_host_check.py
  rev_c_i2c_isolation_host.py
新しい実行ファイルだけでなく依存ファイルも転送してください。
main.py / boot.pyには保存しません。UF2の書き直しは不要です。

2. 実行
-------
1) 現在の両側をCtrl+Cで停止し、ファイルを転送します。
2) 両側を停止した状態で、両方のPico USBとRev C JPOWERをすべて外し、5秒待ちます。
3) JPOWER -> 両方のPico USBの順で接続し、Thonnyを各Picoのポートへ再接続します。
4) Rev C側でrev_c_i2c_isolation_target.pyを実行します。
   YM2203 Rev C / silent I2C initialization isolation target v1
   バス検査後、I2C CONFIGとGPIO配列、次の行が出るまで待ちます。
   PHASE 0 READY / BUS ONLY / address=0x42
5) 操作側でrev_c_i2c_isolation_host.pyを実行します。
   YM2203 Rev C / silent I2C initialization isolation HOST v1 / OTHER Pico only
6) 以後は自動で段階0～5へ進みます。全体は数十秒が目安です。
   HOSTは各段階で32回の識別情報読み取り、4種類の32バイトRAM書き込み/読み戻し、
   識別情報の書き込み保護を検査し、成功後にだけ次へ進む命令を1回送ります。
   初回の書き込みはFM診断で失敗したものと同じ、STOPなしの1バイトポインター設定です。
   STOP区切りの読み取りと繰り返しSTARTの読み取りの両方を検査します。
   段階間は3秒待ちます。通信を自動リトライせず、失敗した転送の例外を表示します。

3. 段階
-------
初期化は累積します。各段階の資源追加後にI2Cを設定・有効化してからREADYを表示します。
段階間のI2Cは意図的に停止します。連続FM受信中にI2Cを処理する試験ではありません。

0 BUS ONLY              YMバスの無音読み書き検査後。FM設定・PIO・I2Sは未初期化。
1 FM REGISTERS          固定音程/音色のFMレジスタを設定。FMはキーオフ、PIO/I2Sは未初期化。
2 FM RX ALLOCATED       実績のあるFM受信PIO SM0とDMA/バッファを確保。受信は未開始。
3 I2S RUNNING           GP10/11/12の48kHz・16bitステレオI2Sを起動。無音データを送信。
4 FM PREFLIGHT STOPPED  無音FM事前検査（キーオフ4、オン12、オフ40の56ブロック）後、受信停止。
5 I2S CLOSED            YMをリセットし、I2Sを終了。GP10/11/12をLowに戻す。FM受信の資源は保持。

段階4では出力ミュートのまま、以前と同じ変換と音量/期限監視を使います。
段階5はYMリセットとI2S停止の両方を行うので、この段階だけで個々の影響を分離できません。
先行段階の通信が失敗した場合は、その時点でHOSTが止まり、後続段階へは進みません。
進めなくなった段階を手掛かりとして、次に限定した比較を行います。

4. ログと報告
-------------
Rev C側は段階ごとに次を表示します。
  PHASE n SETUP / ...
  I2C CONFIG: [...]
  GPIO0..29 FUNCSEL: [...]
  SDA/SCL INPUT BITS: ...
  PHASE n READY / ...
  PHASE n END / received=... sent=... ignored=... stale_flushes=...
I2C CONFIGの順序:
  CON, SAR, ENABLE, ENABLE_STATUS, SLV_DATA_NACK_ONLY, STATUS, RAW_INTR_STAT,
  GP20のPAD制御値, GP21のPAD制御値。
先頭5値は[804,66,1,1,0]、GPIO配列の20/21番目のFUNCSELは3が期待値です。
他のGPIOも表示し、同じI2C入力が別ピンへ割り当てられていないか比較するための情報にします。
読み取りによる観測だけで、GPIOやPAD設定を検査のために書き換えません。
PAD値は入力有効(bit6)、出力無効(bit7)、隔離(bit8)などを含む値です。比較用に生値を表示します。
INPUT BITSはbit0=SDA、bit1=SCLで、アイドル時は通常3。通信中の観測値は変わります。
レジスタ観測だけで実際の配線・波形・ACKまで確認できるわけではありません。

全段階が通った場合:
  HOST: PHASE 0 PASS ～ PHASE 5 PASS、HOST PASS、HOST SAFE
  Rev C: PHASE 0 END ～ PHASE 5 END、SAFE、DONE
全区間でテスト音が出ないことと、両方のログ全文を報告してください。

途中でEIOなどが出た場合:
1) HOSTのエラー末尾まで保存します。
2) Rev C側もCtrl+Cで停止し、LAST PHASE、FAIL、SAFEと例外末尾まで保存します。
3) 両方のログ全文を送ってください。最後に成功したPHASEと失敗したPHASEが重要です。
HOSTの失敗したPHASEに対してRev CがまだREADYを出していなかった場合も、その順序を報告してください。
資源初期化が3秒の待ち時間を超えた可能性があるため、即座にその資源を原因とは断定しません。
Rev Cは各段階で最大5分待ちます。HOSTだけの再実行ではなく、再試験は両側を初期化して行います。

5. 検証と制約
-------------
PCのモデル試験では実際のHOSTのRAM検査と段階制御、実際のターゲットの資源追加順を組み合わせます。
全段階で出力を許可しないこと、各段階の中断/MemoryError/OSError時の解放、
事前変換異常時の受信停止、設定不一致、HOSTが最初の失敗をリトライしないことも確認します。
MicroPython WASMでは実際のHOSTとWindow処理を実行し、段階移行・I/Oと資源の追加は模擬します。
公式MicroPython v1.29.0 mpy-crossで新しい2ファイルをArm向けにコンパイルします。
PC/WASMでの合格は、実機のI2C/PIO/DMA/I2S並行動作、電気的特性や実際の無音の保証ではありません。
上記の段階診断の実機結果は取得済みですが、連続FM変換中のI2C通信は本診断では確認しません。

診断用署名RCISO01!、0x42。0x00から10バイトが署名8バイト+段階番号+番号の反転値。
0x20～3FはRAM。0x7Eへ0xA5で次段階、最後の段階で0x7Fへ0xA5で終了します。
古い音声テストとは署名が違うため、組み合わせが異なるHOSTは検査で停止します。
このプロトコルは組立診断専用で、公開音源APIではありません。

同梱ログ: host-tests.txt、micropython-compatibility.txt、compiler-validation.txt、native-core-validation.txt。
validation.jsonに検証結果とファイルのSHA-256を記録します。配布はPythonソースです。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs

一次資料（読み取り専用のGPIO/PAD観測アドレス）:
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/addressmap.h
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/io_bank0.h
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/pads_bank0.h
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_structs/include/hardware/structs/io_bank0.h
