Rev C / MicroPython HOSTプレーヤー v1

できること
  /music直下のWYM1 BINを番号で選択し、単曲再生・単曲リピート・一覧順の連続再生ができます。
  alpha.3で待機中の音声fault5が報告されました。今回はI2S-CLOCK-FIX-README.txtに従って
  Rev Cを修正版C0.5.0-alpha.4へ更新します。操作側プレーヤー処理とI2C形式は変更しません。
  再生処理は実機受入済みのRevCStream.play_file()を変更せず使用します。
  alpha.4で10分待機後の診断/全曲再生、リピートとCtrl+C消音/メニュー復帰をユーザー実機で確認済みです。
  リピートのモード/回数と、a/lそれぞれの個別実施までは報告されていません。
  イースI「First Step Towards Wars」の1曲全長も同じalpha.4で実機確認済みです。
  DONE、期待する5024件・CRC32=be705192の一致、fault=0/gates=0、FM100%の良好なバランスと左右正常をユーザーが確認。
  今回の生ログは未提示。受入記録: verification/c05-alpha4-ys1-first-step-hardware-acceptance.json
  イースIII「The Boy’s Got Wings（翼を持った少年）」の1曲全長も同じalpha.4で実機確認済みです。
  DONE、期待する43172件・CRC32=568fcf61の一致、fault=0/gates=0、FM100%の良好なバランスと左右正常・歪み/音切れなしをユーザーが確認。
  今回の生ログは未提示。受入記録: verification/c05-alpha4-ys3-boys-got-wings-hardware-acceptance.json

導入（操作側Pico/Pico2だけ）
  1. 従来どおりの外部5V、I2C、GND、JLINE→AMS-22を維持し、両音量を低めにします。
     操作側GP0=SDA、GP1=SCL、100kHz、3.3V信号です。配線変更はありません。
  2. Thonnyを操作側Picoへ接続します。Rev CへMicroPythonコードを書き込みません。
     配布物の次のファイルを操作側へ保存します。
       host/lib/ym2203_revc_stream.py → /lib/ym2203_revc_stream.py
       host/lib/ym2203_revc_player.py → /lib/ym2203_revc_player.py
     streamライブラリは前回のKEEP/DONE修正版と同じ内容です。
  3. 既存の/music/song.binをそのまま使えます。楽曲ファイルは配布物に含めません。
     他の曲も4MHz YM2203用WYM1 BINとして/music直下へ保存してください。
     既存/music/recovery.binは13秒の自作診断曲です。導入確認にも使えます。
     未配置の場合だけ、同梱host/music/recovery.binを/music/recovery.binへコピーします。
  4. 操作側PicoをCtrl+Dでソフトリセットします。
  5. PC上のhost/player.pyをThonnyで開き、操作側Picoを選んでF5実行します。
     Picoのmain.pyへ保存する必要はありません。起動しただけでは演奏しません。

メニュー（Thonnyシェルへ入力してEnter）
  例: recovery.binとsong.binがある場合、次のように表示されます。
      1: recovery.bin / 0:13 / 191 events
      2: song.bin / 4:58 / 123137 events
      HOST>

  2       2番の曲を1回再生してメニューへ戻る
  r 2     2番の曲を繰り返す（再生中のCtrl+Cで停止してメニューへ戻る）
  a       一覧の先頭から全曲を1回ずつ再生してメニューへ戻る
  l       全曲を一覧順に繰り返す（Ctrl+Cまで継続）
  u       ファイルを追加・削除した後、一覧を読み直す
  q       プレーヤーを終了してHOSTのGP0/GP1を入力に戻す

  番号は現在表示された一覧を使ってください。名前順・最大64 BINファイル、サブフォルダは対象外です。
  ヘッダー、4MHzクロック、件数、ファイル長が不正なものはSKIPとして表示し、選択対象から外します。
  曲を追加すると番号が変わることがあるため、uで更新した後の一覧を確認します。
  曲一覧はヘッダーと長さだけを読みます。CRCと全イベントの検証は実際の再生時に行います。

停止と曲間
  再生中はThonnyシェルのCtrl+Cで消音してメニューへ戻ります。qはメニューで入力します。
  再生中の文字コマンドや次曲予約は扱いません。停止してから別の番号を選んでください。
  Ctrl+Cをメニューでもう一度押すと終了します。
  正常終了後は1秒待機し、次曲の検証・準備時間が加わってから演奏が始まります。
  リピートは毎回ファイルを検証・再送し、BEGINからファイルの先頭へ戻して演奏します。
  表示するPLAYは検証・準備開始、DONEは全イベント/CRCを照合した正常完了です。
  連続・リピートも各曲のDONEを確認してから進みます。全曲をRAMへ保持しません。
  再生中に進捗ログや入力ポーリングを増やさず、既存のI2C補充と1秒リースを維持します。
  メニューの表示・選曲待ち・qだけではSTOPやPLAYを送らず、MIDIの制御権を奪いません。
  明示的に曲を再生すると既存のplay_fileがSTOPしてからI2C演奏を開始します。

異常時
  通信・CRC・ファイル異常では停止してプログラムを終了し、次曲へ進んだり自動再試行したりしません。
  STOPを送れない通信障害ではRev Cの1秒リースが消音の最終手段です。
  異常ログを保存し、原因を確認してからF5で再起動してください。
  以前のhost/main.py（Ys II単曲再生）はそのまま利用できます。

最小の実機確認
  まず一覧でrecovery.binを選び、FM音階→SSG音階→和音の正常終了を確認してください。
  次にr 番号で同じ診断曲が先頭から繰り返され、Ctrl+Cで消音してメニューへ戻ることを確認します。
  複数曲がある場合はaの順次再生、lの一覧リピートも試せます。
  曲名/順序、終了後・Ctrl+C後の無音、左右、歪みや音切れの有無とHOSTログを教えてください。
  既に受入済みのYs II全曲試験を一式やり直す必要はありません。

開発者向け（プロジェクト直下）
  REVC_TEST_SONG=local-test-data/ym2203/ysii/song.bin python3 -m unittest discover -s firmware-c/tests
  python3 firmware-c/tools/verify_host_micropython.py --micropython /path/to/micropython --player
  python3 firmware-c/tools/build_host_player.py --output outputs/revc-host-player-v1.zip
  自動試験は実際のCストリーム処理とPython/MicroPythonを使いますが、I2C電気特性や可聴音の実測ではありません。
