YM2203 Rev C C0.5.0-alpha.3 / USB切断・復帰の確認 v1.1

目的と範囲
  MIDIのUSB喪失時消音と、I2C演奏がRev CのUSBに依存しないことを確認します。
  制御権切替と手順1のMIDI物理USB切断・復帰はユーザー実機で合格済みです。
  手順2もHOST v1.1で実機合格。191件・CRC一致・fault=0/gates=0、終了後と再接続後の無音を確認しました。
  旧ログはKEEP rejected:code4 state3 error0 audio_ok=1。Rev Cの音声異常は示していません。
  この終了競合は旧ライブラリと実際のCストリーム処理で再現し、操作側のみ修正しました。
  明示的MIDI復帰、左右正常・歪み/音切れなしもユーザー確認済みです。以下は実施手順として保存します。
  alpha.3のUF2、既存のMIDI/CDC画面、操作側ライブラリと診断BINをそのまま使います。
  UF2の再書き込みとYs II全曲再試験は不要です。

今回の差し替え（操作側Picoだけ）
  1. Rev CのUSBを戻し、MIDIを停止します。外部5Vは維持します。
  2. Thonnyで操作側Picoへ接続します。この配布物のhost/lib/ym2203_revc_stream.pyを
     操作側Picoの/lib/ym2203_revc_stream.pyへ上書き保存してください。
     PC上のファイルを更新するだけではPico内のライブラリは変わりません。
  3. 操作側PicoをCtrl+Dでソフトリセットし、旧モジュールの読み込みを解除します。
  4. 今回のhost/usb_disconnect_check.pyをPCから開いてF5実行します。
     起動行にHOST v1.1が出ます。実施済みの手順1は繰り返さず、手順2から再確認します。
  /music/recovery.binと既存のYs II BINは変更不要です。Rev CはC0.5.0-alpha.3を維持します。

修正内容
  最後に読んだRUNNING状態からKEEPが届くまでの間に、Rev CがDONEへ移ることがあります。
  KEEPのSTATE拒否を一律に無視せず、play_file内でSEAL済みの同じ曲についてだけ、
  DONE、error=0、音声正常、SEAL/所有状態、受信/実行/総件数、曲長、経過時刻、
  空キュー、CRC、ACK/次シーケンスが一致する場合に正常完了として扱います。
  拒否されたKEEPはシーケンスを消費しないため、操作側も番号を進めません。
  通常のcommand(KEEP)のSTATE拒否、リース失効、CRC不一致、音声異常は従来どおり失敗します。
  Rev Cのプロトコル形式、1秒リース、UF2、GPIOに変更はありません。

準備
  両方の音量を低めにします。他のMIDI送信ソフトは停止します。
  Rev CのJPOWER外部5V、操作側PicoのUSB、AMS-22の電源、LINE、I2C/GNDは維持します。
  抜くのはPCとRev C上のPicoを結ぶUSBだけです。JPOWERの電源専用USB-Cは抜きません。
  Rev CのPicoはJPOWER→+5V→D1→VSYSから引き続き給電されます。
  USB喪失による音声停止と、基板全体の電源断を混同しないでください。
  操作側には既存の/lib/ym2203_revc_stream.pyと/music/recovery.binを使用します。
  recovery.binは191件、13秒、1162バイト、CRC32=e5df0948の自作診断曲です。

1. MIDI保持中のUSB切断
  a. MIDI画面の「3. 復帰確認用に6声を保持」を押し、和音を確認します。
     CDCの状態を保存します（audio_ready=1/fault=0、MIDI owned=1/mask=63）。
  b. 和音が鳴っている間にRev CのPicoのUSBだけを抜きます。
     速やかに全音が消え、そのまま4秒以上無音が続くことを確認します。
     SOF停止の検出期限は250msですが、耳だけでミリ秒の合否判定はしません。
  c. 同じUSBを戻し、4秒以上待ちます。接続だけでは再発音しないことを確認します。
     MIDIとCDCの接続先を選び直し、状態取得でfault=0、gates=0、MIDI owned=0を確認します。
     「3. 復帰確認用に6声を保持」で再発音し、「MIDI全音停止」で消音します。
     配線と外部5Vは変えません。操作画面の再接続にリセットやBOOTSELは使いません。

2. I2C演奏中のUSB切断
  a. MIDIを停止した状態で、Thonnyは操作側Picoへ接続します。
     host/usb_disconnect_check.pyをPCから開きF5実行します。Picoへの保存は不要です。
  b. 最初の3秒無音後、HOSTに「PLAY: unplug ONLY Rev C Pico USB within5 seconds」が出ます。
     5秒以内にRev CのPicoのUSBだけを抜き、HOSTのDONEまで抜いたままにします。
     MIDI画面・CDC画面は操作しません。操作側PicoのUSBと外部5Vは維持します。
  c. FM音階→SSG音階→6声和音の13秒演奏が、USB切断をまたいで途切れず完了することを確認します。
     演奏終了後4秒間無音、HOST PASS・DONE・HOST SAFEを確認します。
     HOSTは191件・CRC・音声正常フラグ・完了後の状態を検査します。
     USBケーブルを抜いた事実と可聴音の継続はHOSTから検知できず、ユーザーの観察が必要です。
  d. Rev CのUSBを戻し、4秒以上待ち、接続だけでは再発音しないことを確認します。
     MIDI/CDCを選び直し、状態を保存します。I2C executed=191/191、error=0、queued=0、
     audio_ready=1/fault=0、gates=0、MIDI owned=0が期待値です。
     最後にボタン3でMIDI再発音→MIDI全音停止を確認し、もう一度状態を保存します。

ログと判定
  I2Cの最終state=4は明示STOP後の正常値です。STATUS側のstateとは別の列挙です。
  今回はI2C通信を休止しないので、FAIL I2C error=8は期待しません。
  CDCがUSB切断を表示するのは正常です。失われたCDCログを埋めるため再試験する必要はありません。
  HOST PASSだけでは物理USB試験の合格を意味しません。以下を合わせて報告してください。
    ・MIDI切断時の消音、切断中/再接続後の無音、新しいNote Onによる復帰。
    ・I2C演奏がUSB切断中も正常完走し、終了後/再接続後に無音だったこと。
    ・左右、歪み/予定外の音切れの有無、HOST全ログ、各再接続後のSTATUS/AUDIO/I2C/MIDI。
  無音にならない場合は両音量を下げ、USBを戻してCDC/I2C STOPで停止し、ログを保存してください。
  faultが発生したらそのログを保存し、同じ試験を繰り返す前に原因を確認します。

開発者向け
  python3 -m unittest discover -s firmware-c/tests
  python3 firmware-c/tools/verify_host_micropython.py --micropython /path/to/micropython --usb-disconnect --keep-done-race
  新HOSTのモデル試験は実際のCストリーム処理で件数/順序/失敗時STOPを確認します。
  main.cの既存モデル試験はUSB喪失時のMIDI停止とI2C継続を確認します。
  これらは物理USB切断やアナログ音声の実測ではありません。
