YM2203C Rev C - 全6音の連続音程変更・3分耐久診断 v1
2026-11-12

直前の実機結果
--------------
各チャンネルの旋律+反対音源の持続和音は、6区間とも実機合格しました。
左右正常、歪み/予定外の音切れ/気になるクリック音なし、最終自動消音とHOST PASS・SAFE・DONEを確認。
6713ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4913、max_idle_poll_us=531。
SIX I2C jobs=17 writes=60 max_write_us=4400 pending=-1 applied=0 prime_left=0。
VOICE PITCH updates=90 writes=180 max_write_us=4561 cancelled=0 pending=-1 step=2。
最終ACK201、期限消音1回、stale flush 0、受信855=1893-1038、送信3096=5844-2748が一致しています。

次は全6音を同時に鳴らしながら、各チャンネルの音程を更新し続ける3分耐久です。
固定和音の耐久と異なり、音程レジスタの継続書き込み、ACK/状態照合、連続FM変換を同時に行います。
予約演奏の実装に進む前に、音程変更が続く場合にも消音/歪み/期限超過が起きないかを確認します。
v1は実機で途中停止しました。9415ブロック、max_poll_us=18321、1音程レジスタの最大処理17985usで
FMの期限監視が停止させています。HOST EIOはその後に発生しました。
VOICE PITCH updates=331 writes=663 pending=135 step=1、最後のACK172/命令0x80、期限消音0回。
GPIO I/Oの一時オブジェクト生成を減らし、発音前の実機ヒープ検査を加えたv1.1で再試験します。
最新の手順はI2C-DYNAMIC-PITCH-ENDURANCE-V11-README.txtです。以下は旧v1の手順を記録として残します。

1. 配線・追加ファイル
---------------------
前回合格した配線/給電/音量を維持します。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー、PC USBなし、DIRECT MONITOR ON。

前回のファイルを残し、次の1ファイルだけをHOST Picoの最上位へ追加します。
  host/rev_c_i2c_voice_pitch_endurance_host.py
既存のrev_c_i2c_voice_pitch_host.py等をimportします。これらもHOSTに残してください。
Rev Cは今回合格したrev_c_i2c_voice_pitch_target.pyをそのまま実行します。
未保存の場合はZIPのtarget/全14ファイルをRev C、host/全11ファイルをHOSTへ保存します。
既存24ソースは変更していません。main.py / boot.pyへの保存やUF2更新は不要です。

2. 実行
-------
1) 両側を停止して新しいHOSTファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cでrev_c_i2c_voice_pitch_target.pyを実行します。
   YM2203 Rev C / staged I2C per-voice pitch target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_voice_pitch_endurance_host.pyを実行します。
   YM2203 Rev C / I2C dynamic six-voice endurance HOST v1 / OTHER Pico only
6) 起動検査とSTART/KEEP確認、無音の音程設定の後、5秒待って発音します。
準備を含め約4分が目安です。

3. 聞こえる音
-------------
最初はFM C4/E4/G4とSSG C3/E3/G3の6音和音です。
以降、ド〜ソの範囲を往復するパターンを使い、FM1→FM2→FM3→SSG A→SSG B→SSG Cの順に音程を変えます。
6回の音程変更とKEEP1回を1グループとして、3分間繰り返します。
同じ音程を確認のため再設定する場合もあります。
チャンネルごとに旋律の開始位置をずらすため、和音が少しずつ組み替わる音になります。
全6音を保持し、主試験中にキーオフ/音量変更/ミュート/STOPは行いません。
左右とも同じ音が聞こえます。歪み/予定外の音切れ/気になるクリック音がないか確認してください。

チャンネルは順に変更されます。一斉切り替えや固定テンポの楽曲再生ではありません。
1命令ごとにACKと全6チャンネルの状態を照合し、各グループの後に100ms待機します。
グループの途中では終了せず、開始から3分を超えたところで最後のグループを完了して停止します。
3分後はSTOPで1秒の無音、無音で元の音程に復元、短い6音和音の自動消音、FINISHの順です。

4. ログと期待値
---------------
30秒ごとにHOSTだけが進捗を表示します。Rev Cは取り込み停止後にまとめて表示します。
  DYNAMIC PITCH START / 180 seconds ...
  DYNAMIC PITCH 1/6 / elapsed_ms=... groups=... updates=... KEEP=... commands=... ack=... wraps=... max_check_ms=...
  ...
  DYNAMIC PITCH 6/6 / ...
  DYNAMIC PITCH COMPLETE / elapsed_ms=... groups=... updates=... KEEP=... commands=... wraps=... max_check_ms=...
groupsは主試験の完了グループ数G、updatesは6G、KEEPはG、commandsは7Gです。
wrapsは主試験中の8bit ACKの周回数です。少なくとも256命令と1回のACK周回を確認します。
max_check_msは1命令のACK確認と12バイト状態照合までの最大時間です。
Rev Cのmax_poll_usやmax_write_usとは計測範囲が異なります。

今回のRev Cの期待値は次のとおりです。
  SIX I2C: jobs=7 writes=24 ... pending=-1 applied=0 prime_left=0
  VOICE PITCH: updates=6G+12 writes=12G+24 ... cancelled=0 pending=-1 step=2
  lease_expirations=1
  deadline misses=0
音程更新回数は実際の通信速度によって変わります。HOSTが具体的な期待値を計算して表示します。
  EXPECTED VOICE PITCH: updates=... writes=... cancelled=0 pending=-1 step=2
  EXPECTED TARGET FINAL ACK: ... / FINISH=7 mode=0 lease_flag=0
最終ACKは(7G+59)&255、LAST CONTROL STATEは[最終ACK,7,0,0]です。
静かな初期設定と終了前の復元で各6命令、主試験中に6G命令の音程設定を行います。
SIX I2Cのwritesはキー/音量、VOICE PITCHのwritesは音程レジスタの回数です。
初期と終了時の音程インデックスは[0,2,4,0,2,4]です。

グループの前後にも状態を確認し、予期しない期限切れを次のSTOPで消してしまうことを防ぎます。
異常があれば自動再送や後続処理を行わず停止します。HOST異常時には従来の1秒リースで自動消音します。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで停止し、LIVE I2C/SIX I2C/VOICE PITCHからSAFE・例外末尾まで保存します。
共通DONEのall nine sound sectionsという文言によらず、今回は3分間の音程変更と最終自動消音を確認します。

両側のログ全文と、3分間の音程変化、左右、歪み/予定外の音切れ/クリック音、STOPと最終自動消音を報告してください。
HOST PASS・HOST SAFE、Rev CのSAFE・DONE、上記期待値を確認します。

5. 検証と制約
-------------
全224項目（今回追加6項目）のPCテストが合格しました。独立11.25ms通信モデルで、3分間の音程更新、
全FMキー/SSG音量/出力ゲートの保持、全チャンネルの状態照合、ACK周回、時刻周回、
異常転送の再送なし、状態破損/想定外の通信停止の検出と期限消音を確認しました。
MicroPython WASM 1.28.0で模擬時計/通信/音源による全HOST手順を確認し、
mpy-cross 1.29.0で配布25ファイルのArm向けコンパイルを確認しました。
長時間のWASM検証は履歴を蓄積せず逐次照合します。実機用HOSTもカウンターのみで履歴を保持しません。
検証ログとSHA-256一覧を同梱します。再検証コマンドは以下です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
これらは実機の音質やI2C/PIO/DMA/I2Sの最悪応答時間を保証しません。新耐久診断の実機結果は未確認です。
GPIO割り当て/ネイティブ変換/音量/音色、40ms待機、1秒リースとACK期限、ターゲット5分上限は維持します。
連続取り込み中のRev Cでメモリ走査や進捗出力は行いません。メモリ最大使用量や24時間運転は測定しません。
予約演奏、固定テンポ、高速I2C、USB-MIDI、楽曲BINの実機再生は今回含みません。
