YM2203C Rev C - FM/SSG各チャンネルの独立音程制御診断 v1
2026-11-12

直前の実機結果
--------------
HOST通信一時停止・復帰は3回とも合格しました。自動消音と明示的な再発音、左右正常、
歪み/予定外の音切れ/気になるクリック音なし、HOST PASS・SAFE・DONEを確認しました。
2118ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4577、max_idle_poll_us=470。
SIX I2C jobs=13 writes=48 max_write_us=4408 pending=-1 applied=0 prime_left=0。
期限消音3回、stale flush 0、復帰時ACK51/61/71、最終ACK83が一致しました。
受信350=1388-1038、送信792=3540-2748も一致しています。

次は各チャンネルの音程だけを変え、ほかのチャンネルの和音を保持できることを確認します。
FM1/2/3の各旋律をSSGの和音と、SSG A/B/Cの各旋律をFMの和音と組み合わせます。
以前確認した音色・音量のまま、ドレミファソファミレドを6区間で演奏します。
独立音程制御診断も実機で6区間合格しました。各旋律の変化と伴奏の持続、左右正常、音質正常、
HOST PASS・SAFE・DONEを確認しています。
6713ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4913、max_idle_poll_us=531。
SIX I2C jobs=17 writes=60 max_write_us=4400 pending=-1 applied=0 prime_left=0。
VOICE PITCH updates=90 writes=180 max_write_us=4561 cancelled=0 pending=-1 step=2。
最終ACK201、期限消音1回、stale flush 0、受信855=1893-1038、送信3096=5844-2748も整合しています。
次はI2C-DYNAMIC-PITCH-ENDURANCE-README.txtの全6音連続音程変更3分耐久診断です。

1. 配線・追加ファイル
---------------------
配線・給電・音量は前回合格したままです。
  Rev C JHOST1 GND -> HOST Pico GND
  Rev C JHOST2 SDA -> HOST GP0（物理1番）
  Rev C JHOST3 SCL -> HOST GP1（物理2番）
3.3V、0x42、10kHzハードウェアI2C0、既存4.7kΩプルアップです。電源線同士はつなぎません。
JLINE -> AMS-22 LINE IN、両音量低め、AMS-22別バッテリー、PC USBなし、DIRECT MONITOR ON。

前回のファイルを残し、次の2ファイルをそれぞれのPicoの最上位へ追加します。
  Rev C：target/rev_c_i2c_voice_pitch_target.py
  HOST ：host/rev_c_i2c_voice_pitch_host.py
今回は新しいターゲットも実行します。従来のrev_c_i2c_six_target.pyはヘルパーとして残します。
ファイルが未保存の場合はZIPのtarget/全14ファイルをRev C、host/全10ファイルをHOSTへ保存します。
既存22ソースは変更していません。以前の診断エントリーは今回は実行しません。
main.py / boot.pyには保存しません。UF2更新は不要です。

2. 実行
-------
1) 両側を停止し、新しい2ファイルを保存します。
2) 両Pico USBとJPOWERを外して5秒待ち、JPOWER -> 両USBの順に接続します。
3) 各ThonnyをそれぞれのPicoへ再接続します。
4) Rev Cでrev_c_i2c_voice_pitch_target.pyを実行します。
   YM2203 Rev C / staged I2C per-voice pitch target v1
5) PHASE 0 READY後、HOSTでrev_c_i2c_voice_pitch_host.pyを実行します。
   YM2203 Rev C / I2C per-voice pitch HOST v1 / OTHER Pico only
6) 従来の起動検査、START/KEEP確認の後、5秒待機と無音での音程設定を経て発音します。
準備を含め約2分が目安です。

3. 音の順序
-----------
各区間で「ドレミファソファミレド」を1回演奏します。
  1 FM CH1が高い旋律 C4 D4 E4 F4 G4 F4 E4 D4 C4、SSG A/B/Cが低いドミソを持続
  2 FM CH2が同じ高い旋律、SSG A/B/Cが低いドミソを持続
  3 FM CH3が同じ高い旋律、SSG A/B/Cが低いドミソを持続
  4 SSG Aが低い旋律 C3 D3 E3 F3 G3 F3 E3 D3 C3、FM CH1/2/3が高いドミソを持続
  5 SSG Bが同じ低い旋律、FM CH1/2/3が高いドミソを持続
  6 SSG Cが同じ低い旋律、FM CH1/2/3が高いドミソを持続

各区間は旋律1音+反対側の和音3音の計4音です。残り2音は停止します。
各区間内ではキーや音量・出力ゲートを変えず、旋律チャンネルの音程だけを動かします。
6種類の音色を切り替える試験ではなく、同じ音色のチャンネルを切り替える試験です。
FM側がSSG側の約1オクターブ上です。左右とも同じ音が聞こえます。

各区間の後はSTOPで1秒の無音を挟み、さらに無音のまま全音程を準備してから次を始めます。
先頭のドは無音中に用意し、発音開始後に同じドの設定を重ねて送ることはしません。
一音ごとにACKと状態を照合する診断なので、一定テンポを保証する予約演奏ではありません。
1音ごとに450msの待ちに加え、通信・状態照合の時間がかかります。
伴奏が途中で変化しないこと、旋律の音程変化、左右、歪み/予定外の音切れ/クリック音を確認してください。

全6区間の後は元のFM/SSGのドミソに戻し、短い6音の和音を鳴らしてKEEPを止めます。
約1秒で自動消音・全音源停止を確認して終了します。

4. 処理と診断用通信
-------------------
新しい診断用署名はRCPOL01!です。旧ターゲットとは区別し、組み合わせ違いは発音前に検出します。
これは実機検証用の限定コマンドで、正式API/楽曲フォーマットの変更ではありません。
従来のSTOP/START/KEEP/ミュート/発音マスクに加え、0x80～0x9Dを使用します。
  command = 0x80 + voice*5 + note
  voice = 0/1/2: FM1/2/3、3/4/5: SSG A/B/C
  note = 0/1/2/3/4: ド/レ/ミ/ファ/ソ
  FMはC4～G4、SSGはC3～G3です。音量・音色・キー・ノイズ設定は変更しません。
FMは従来の音階診断のプリセット値を使い、SSG周期は478/426/379/358/319です。

2個の音程レジスタを1poll最大1個で更新し、両方が完了してからACKを返します。
FMはA4+ch、A0+chの順、SSGは周期の上位、下位の順です。
全SSGプリセットの上位は1で共通です。SSG書き込みには従来の読み戻し検査を使います。
任意レジスタ値は受け付けず、固定の5音だけを指定できます。
処理途中に期限切れになったら未完了の音程命令を取り消し、即時ミュートと分割停止を優先します。
未完了の音程に成功ACKは返しません。通信異常時の自動再送/再発音も行いません。

0x10から12バイトの状態を照合します。
  ACK、最後の命令、モード、期限フラグ、発音マスク、処理中、FM1/2/3/SSG A/B/Cの音程インデックス
初期と終了時の音程インデックスは[0,2,4,0,2,4]です。
旋律以外のチャンネルのインデックスも毎回照合します。
今回のソース制御は従来の分割キー/音量変更と12ブロックの無音準備をそのまま使います。
連続取り込み中のRev Cには追加の進捗出力やメモリ走査を行いません。

5. 終了ログと報告
-----------------
各区間でSECTION n/6、NOTE n/9、SECTION n/6 PASSと表示します。
最終期待値は次のとおりです。
  SIX I2C: jobs=17 writes=60 ... pending=-1 applied=0 prime_left=0
  VOICE PITCH: updates=90 writes=180 ... cancelled=0 pending=-1 step=2
  lease_expirations=1
  deadline misses=0
  LAST CONTROL STATE (before reset): b'\xc9\x07\x00\x00'
  EXPECTED TARGET FINAL ACK: 201 / FINISH=7 mode=0 lease_flag=0
音程90命令、KEEP94命令（起動32+START後8+54音で各1）、その他17命令、計201のACKです。
終了時のVOICE PITCHとSIX I2Cのwritesは、それぞれ音程とキー/音量の書き込み回数です。
共通DONEのall nine sound sectionsという文言によらず、今回は6区間と最後の短い6音を報告します。

両側のログ全文と、6区間の旋律/持続和音、左右、音質、最後の自動消音を報告してください。
HOST PASS・HOST SAFE、Rev CのSAFE・DONE、上記の期待値を確認します。
失敗時はHOSTを再実行せず、Rev CもCtrl+Cで停止し、LIVE I2C/SIX I2C/VOICE PITCHからSAFE・例外末尾まで保存します。

6. 検証と制約
-------------
PCの全218項目（今回追加8項目）が合格しました。独立11.25ms通信モデルで全54音の制御、
伴奏のキー/音量/音程/ゲートを保持したままの更新、1poll1レジスタ、2回完了後のACK、
期限切れ時の未完了音程の取消と消音、不正入力/識別子/状態不一致/転送失敗を確認しました。
実際のバス操作のモデルとネイティブ期限監視も使い、人工的なI2C処理4000us+1レジスタ4000usの
負荷で分割処理が完了し、過剰負荷/例外では安全停止することを確認しました。
この人工値は実測値ではなく、実機の最悪時間を保証するものではありません。
MicroPython WASM 1.28.0の模擬時計/通信/音源で全HOST手順を確認し、
mpy-cross 1.29.0で配布24ファイルのArm向けコンパイルを確認しました。
検証ログとSHA-256一覧を同梱します。再検証コマンドは以下です。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
上記の実機条件で音質と動作を確認しました。最悪応答時間の保証ではありません。音程レジスタ2個の転送は同時ではありません。
GPIO割り当て/ネイティブ変換/音量、40ms待機、1秒リースとACK期限、ターゲット5分上限は維持します。
固定テンポ/予約演奏/自由な音域/楽曲BIN/高速I2C/USB-MIDI/24時間運転は今回含みません。
