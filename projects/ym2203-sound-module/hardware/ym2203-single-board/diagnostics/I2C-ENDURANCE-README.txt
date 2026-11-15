YM2203C Rev C - 3分間のFM+SSG / I2C通信耐久診断 v1
2026-11-11

目的と実機確認済みの範囲
------------------------
段階起動FM/I2C v1.3は、実機で9区間すべての発音・両ミュート・最終自動消音が正常でした。
左右正常、歪み/音切れなし、HOST PASS・SAFE/DONEまで確認済みです。
連続2478ブロック、ピーク4064、最大変換1118us、期限超過0、最大I2C poll=7502us。
実行確認カウンター111、期限消音1回、受信407/送信744、stale flush 0。
HOST書き込み1445-起動段階173*6=407、読み取り3492-起動段階458*6=744で、両側の数が一致しました。
40msのHOST待機を使った実機合格です。以前の初回EIOの直接原因まで確定したわけではありません。

今回は同じターゲットと通信を約3分間続け、KEEP命令とACKカウンターの周回を検査します。
新しく追加するのは操作側のrev_c_i2c_endurance_host.pyだけです。
音源は前回と同じFM約440HzとSSG A約220Hzの2音。6音同時の耐久試験ではありません。
ターゲットの音声変換・受信・I2C通信・音量・期限監視やGPIOを変更しません。
この3分間の同時通信耐久試験は実機合格しました。主試験180045ms、KEEP 640回、ACK周回2回、
HOST最大応答確認92ms、左右正常、歪み/音切れなし、最終自動消音とHOST PASS・SAFE/DONEを確認済みです。
16854ブロック、ピーク4064、最大変換1118us、期限超過0、max_poll_us=11796、stale flush 0。
受信2135/送信3048はHOSTから起動段階分を引いた数と一致し、最終ACK175もHOST期待値と一致しました。
次はI2C-CYCLE-README.txtのモード/ミュート切り替え反復診断です。

1. 接続とファイル
-----------------
配線・給電は前回v1.3の合格時と同じです。
  Rev C JHOST 1 GND -> 操作側Pico GND（物理3番など）
  Rev C JHOST 2 SDA -> 操作側GP0（物理1番）
  Rev C JHOST 3 SCL -> 操作側GP1（物理2番）
3.3V、0x42、10kHzのハードウェアI2C0、R1/R2各4.7kΩプルアップを使用します。
電源線同士はつなぎません。配線変更時は両基板を電源OFFにします。
JLINE -> AMS-22 LINE IN、ヘッドホン -> AMS-22。
AMS-22は別バッテリー給電、PCとのUSBは外し、DIRECT MONITOR=ON、LOOPBACK=OFF。
両方の音量を低めにしてください。約3分間、同じ高さの2音が鳴り続けます。

前回のv1.3一式が導入済みなら、host/rev_c_i2c_endurance_host.pyを操作側Picoの最上位へ追加します。
Rev C側のrev_c_i2c_fm_staged_target.py v1.3はそのまま使います。
ZIPには再導入用として、target/の11ファイルとhost/の6ファイルも含みます。
HOST側の構成:
  rev_c_i2c_host_check.py
  rev_c_i2c_ssg_host.py
  rev_c_i2c_fm_host.py
  rev_c_i2c_isolation_host.py
  rev_c_i2c_fm_staged_host.py
  rev_c_i2c_endurance_host.py  今回追加
既存の5ファイルは前回v1.3と同一です。main.py / boot.pyには保存しません。
UF2や基板への変更は不要です。

2. 実行と音の流れ
-----------------
1) 両側を停止してファイルを転送します。
2) 両方のPico USBとJPOWERをすべて外し、5秒待ってJPOWER -> 両方のUSBの順で接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev C側で従来のrev_c_i2c_fm_staged_target.pyを実行します。
   YM2203 Rev C / staged I2C + live FM mixer target v1.3
   PHASE 0 READYが出るまで待ちます。
5) 操作側で新しいrev_c_i2c_endurance_host.pyを実行します。
   YM2203 Rev C / I2C live FM+SSG endurance HOST v1 / OTHER Pico only
6) 以後は自動です。準備を含め約4分です。

前半は既存の6段階の無音通信検査と、連続受信開始前後の通信検査です。
検査が通った後、5秒待って以下を行います。
  A: FM約440Hz + SSG約220Hzを約180秒、連続再生。意図的な音切れ/ミュートは入れません。
  B: STOPで約1秒無音。
  C: 同じ2音をもう一度鳴らし、KEEPを止めて約1秒で自動消音。その後は無音。
  D: STOPとFINISHで終了。HOST PASS・SAFE・DONEを確認します。
開始直後には以前と同様、I2Sバッファによる短い遅延があります。
最後の短い発音と自動消音は意図した動作です。3分の連続再生中の途切れとは分けてください。
背景の小さなサー音も、テスト音の消音判定とは分けます。

3. 進捗とログ
-------------
HOSTだけが30秒ごとに進捗を表示します。Rev C側は連続変換中にはログを出しません。
  ENDURANCE START / 180 seconds / no intentional gaps or mute intervals
  ENDURANCE 1/6 / elapsed_ms=... KEEP=... ack=... wraps=... max_command_ms=...
  ...
  ENDURANCE 6/6 / ...
  ENDURANCE COMPLETE / elapsed_ms=... KEEP=... wraps=... max_command_ms=...
KEEPは3分間の保持命令の累計、wrapsはこの間にACKが255から0へ戻った回数です。
各KEEPはACK・命令・モード3・期限フラグ0を検証します。ACK不一致や期限切れを無視して継続しません。
1回以上のACK周回と6回の進捗を完了条件にします。周回数・KEEP回数はI2C処理時間により変わります。
max_command_msはHOSTで測った命令送信後の応答確認時間で、40msの待ち時間や通信時間を含みます。
音声変換の時間やターゲットのI2C poll時間とは別の数値です。
ACKは8ビットで、周回自体は異常ではありません。Rev Cのcommands=も8ビットの確認カウンターで累計ではありません。

HOST末尾:
  PASS: both sources lease-muted without STOP
  EXPECTED TARGET FINAL ACK: n / FINISH=7 mode=0 lease_flag=0
  HOST PASS: three-minute live FM/SSG + I2C KEEP, ACK wrap and final lease mute verified
  HOST I2C STATS: ...
  HOST SAFE: GP0/GP1=input ...
Rev C末尾:
  LIVE I2C: live_started=1 ... lease_expirations=1 ...
  LAST CONTROL STATE (before reset): ...
  PASS: live sequence sent; max conversion=... us, deadline misses=0
  SAFE ...
  DONE ...
EXPECTED TARGET FINAL ACKとRev Cのcommands= / LAST CONTROL STATE先頭バイトが一致することを確認します。
LAST CONTROL STATEは[ACK,7,0,0]です。FINISH後はI2Cが停止するため、最後のACKはログ同士で比較します。
Rev CのDONEに含まれるall nine sound sectionsは共通ターゲットの案内文です。今回は上記A～Dを報告します。

両側のログ全文と、3分間の左右の連続音、歪み/音切れの有無、1秒の停止と最後の自動消音を報告してください。
失敗した場合はRev C側もCtrl+Cで止め、LIVE I2CからSAFE・例外末尾までの追加ログを保存します。
異常時に発音命令を再送しません。HOST停止時の1秒期限消音も前回と同じです。

4. 検証と制約
-------------
前回の16ファイルは内容を変えず、HOSTの1ファイルだけを追加します。
KEEPの間は最大200ms待ち、応答確認には既存の40ms IDLE間隔を使います。
1秒の通信期限・応答タイムアウト、ターゲットの5分待機上限、ネイティブ音声処理と期限監視は維持します。
3分の計測は最初のBOTH命令のACK後からHOSTのticks_msで行い、最後のKEEPの応答分だけ超える場合があります。
これは組立診断であり、正式な音源APIや性能仕様、24時間運転、USB-MIDIの確認ではありません。
今回のターゲットのメモリ使用量は測定しません。

PCの133項目（今回追加5項目）で、独立した11.25ms I2Cモデルを通した180秒の通信、ACK周回、
最終期限消音、ticks_msの周回をまたぐ計時、異常時に命令を再送しないことを確認します。
MicroPython WASMでは実際のHOSTの全手順を、模擬時計・通信・音源で実行します。
公式MicroPython v1.29.0 mpy-crossで追加HOSTをArm向けにコンパイルします。
これらは実機のPIO/DMA/I2S/I2Cの同時動作、電気的な通信や音質の検証を代替しません。
配布はPythonソースです。ログとvalidation.jsonのSHA-256一覧を同梱します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
