YM2203C Rev C - 連続音程変更3分耐久 再試験 v1.1
2026-11-12

実機結果：v1.1の3分耐久は合格しました。BUS HEAP全6行0bytes、左右正常、音質正常、HOST PASS・SAFE・DONE。
181123ms/100グループ/600音程変更/700命令、ACK周回2回、最大状態照合226ms。
17240ブロック、ピーク2976、最大変換1119us、期限超過0、max_poll_us=4542、max_idle_poll_us=514。
SIX I2C jobs=7 writes=24 max_write_us=4075 pending=-1 applied=0 prime_left=0。
VOICE PITCH updates=612 writes=1224 max_write_us=4206 cancelled=0 pending=-1 step=2。
最終ACK247、期限消音1回、stale flush 0、受信3168=4206-1038、送信13156=15904-2748も整合しています。
この実機結果は旧停止の直接原因がGCだったと確定するものではありません。次はI2C-QUEUE-README.txtです。

1. 今回の停止と修正
-------------------
v1は主試験途中、Rev CのFM処理期限監視により安全停止しました。
  blocks=9415 peak=2976 max_poll_us=18321 commands=172 lease_expirations=0
  SIX I2C jobs=2 writes=6 applied=63
  VOICE PITCH updates=331 writes=663 max_write_us=17985 cancelled=0 pending=135 step=1
最後に完了した命令は0x80（FM1のド）、次の0x87（FM2のミ）の1回目のレジスタ処理後に停止しています。
約18msの処理は1ブロック11.25msを超えています。出力/ARMを落として取り込みとI2Cを停止した後、
HOSTにEIOが出た順序と整合します。配線不良だと判断できるログではありません。

旧GPIOの読み書きではenumerate()がポート処理ごとにイテレーターやタプルを作っていました。
今回、それを既存8ピンへのインデックス付きwhileループに変更しました。
ピンの入出力切り替え順、CS/WR/RDとデータの順序、10us/20usの待ち、GPIO割り当ては維持しています。
MicroPython Unix v1.29.0のGPIOモデルで、GCを無効にした各128組の音程設定を比較しました。
  旧：FM各409600bytes、SSG各737280bytesの未回収ヒープ増分
  新：FM/SSGの全6チャンネルとも増分0bytes
64bit Unixの値であり、Picoのバイト数ではありません。実機の約18msがGCによるものだとはまだ断定できません。
この比較は、GCを誘発し得る不要な確保を減らした証拠です。USB割り込みやBUSY待ちの最大遅延は保証しません。

さらにv1.1では、実機でも発音前にヒープ増分を検査します。
FM取り込み停止中・出力ミュート中だけGCを一時的に無効化し、各チャンネル16組の音程設定を測ります。
1チャンネルの増分が64bytesを超えたらライブ演奏を開始しません。検査後は元の音程へ戻します。
ライブ取り込み中はGCを有効に保ち、メモリ走査/明示的GC/追加の進捗出力は行いません。
期限/ゲインの監視、1秒リース、40ms ACK待機、ターゲット5分上限は緩めていません。

2. 更新ファイルと配線
---------------------
Rev Cの最上位で、次の2ファイルを上書きします。
  target/rev_c_bus_check.py                 GPIO I/O v1.1
  target/rev_c_i2c_voice_pitch_target.py     ターゲット v1.1
HOSTは既存のrev_c_i2c_voice_pitch_endurance_host.pyをそのまま使います。
既存25ソースのうち上記2つだけを変更し、残り23ファイルは前回配布と同一です。
未保存ならZIPのtarget/全14ファイルをRev C、host/全11ファイルをHOSTへ保存します。
main.py / boot.pyへの保存やUF2更新は不要です。

前回の配線・給電・音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、ハードウェアI2C0の10kHz、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー/PC USBなし、DIRECT MONITOR ONです。
プロトコル署名はRCPOL01!のままです。HOSTの更新は不要です。

3. 再試験
---------
1) 両側を停止してRev Cの上記2ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
   インポート済みの古いモジュールを残さないため、給電を入れ直します。
3) 各ThonnyをそれぞれのPicoへ接続します。
4) Rev Cでrev_c_i2c_voice_pitch_target.pyを実行します。
   YM2203 Rev C / staged I2C per-voice pitch target v1.1
5) PHASE 0 READY後、HOSTでrev_c_i2c_voice_pitch_endurance_host.pyを実行します。
   YM2203 Rev C / I2C dynamic six-voice endurance HOST v1 / OTHER Pico only
6) Rev Cの6段階の無音検査の後、次のヒープ検査が加わります。
   BUS HEAP: voice=0 pairs=16 bytes=... limit=64
   ... voice=1～5 ...
   PASS: silent bus heap preflight; GC stays enabled during live capture
   bytesは今回のモデル検証では0でした。実機でも各0～64で通れば継続します。
7) READY、START/KEEP、5秒待機を経て、従来と同じ3分耐久を実行します。
ヒープ検査で止まった場合も再試行を重ねず、その時点のログを送ってください。意図した発音はまだありません。

4. 音と終了時の期待値
---------------------
最初はFM C4/E4/G4とSSG C3/E3/G3、以降ド～ソを往復するパターンで6音の音程を順に変えます。
主試験中は全FMキー/SSG音量/出力ゲートを保持し、意図した無音区間はありません。
チャンネルは順次更新され、固定テンポの楽曲再生ではありません。
約3分の後、STOPで無音、元の音程に復元、短い6音和音の自動消音、FINISHの順です。

HOSTが30秒ごとにDYNAMIC PITCH 1/6～6/6を表示します。
DYNAMIC PITCH COMPLETEのgroupsをGとすると、Rev Cの期待値は以下です。
  SIX I2C: jobs=7 writes=24 ... pending=-1 applied=0 prime_left=0
  VOICE PITCH: updates=6G+12 writes=12G+24 ... cancelled=0 pending=-1 step=2
  lease_expirations=1
  deadline misses=0
  最終ACK=(7G+59)&255
実際の更新数は通信時間に依存します。HOSTのEXPECTED VOICE PITCHとEXPECTED TARGET FINAL ACKが具体値を表示します。
事前のヒープ検査の書き込みはTarget生成前なので、SIX I2C/VOICE PITCHのカウンターには含みません。
LAST CONTROL STATEは[HOST期待の最終ACK,7,0,0]です。

両側のログ全文（今回はBUS HEAPの6行も含む）と、3分間の音程変化、左右、音切れ/歪み/クリック音、
STOPと最終自動消音、HOST PASS・SAFE・DONEを報告してください。
途中停止時は再実行せず、Rev CのLIVE I2C/SIX I2C/VOICE PITCHからSAFE・例外末尾まで保存します。

5. 検証と限界
-------------
PCテスト229項目が合格しました。既存のGPIO方向/パルス順序/読み戻し/期限超過時の安全停止に加え、
静かな有限ヒープ検査、音程復元、GC状態復元、増分過大/例外/旧ヘルパー/取り込み中の検査拒否を確認しました。
MicroPython WASM 1.28.0の模擬音源/時計/通信で3分間の全HOST手順が合格しました。
WASMの事前検査はヒープ値を模擬し、制御手順を確認しています。実際のヒープ増分比較は別のUnix版で行いました。
mpy-cross 1.29.0で配布25ファイルのArm向けコンパイルも確認しました。
検証ログ、ヒープ比較ログ、SHA-256一覧を同梱します。

再検証コマンド（リポジトリのルートから）:
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
Unixヒープ検証用の準備:
  python3 hardware/ym2203-single-board/diagnostics/prepare_bus_heap_probe.py /private/tmp/ym-bus-heap
  MICROPYPATH=/private/tmp/ym-bus-heap "$MICROPYTHON_UNIX" -X heapsize=1M /private/tmp/ym-bus-heap/verify_bus_heap_micropython.py
MICROPYTHON_UNIXはgc、sys、外部import、enumerate等を有効にしたMicroPython Unixの実行ファイルを指定します。
検証ツールは物理Picoへ転送しません。GPIOモデルと抽出した実メソッドを使い、音声/PIO/DMAは動かしません。
GCを無効にするのはこの無音モデル検証と実機の有限事前検査だけです。
v1.1の3分完走は冒頭の条件で確認済みです。最悪GC/割り込み時間、24時間運転、予約演奏/USB-MIDIは保証しません。
