YM2203 Rev C / C SDK USB-MIDI 0.5.0-alpha.3

今回の版
  受入済み0.4.0-alpha.2のI2C v2に、USB-MIDI1.0受信とCDCの複合デバイスを追加。
  GPIO、基板、FM受信・PCM変換・I2S、FM100%の既定値は維持しています。
  I2C v2の署名・100kHz・ホストライブラリ・Ys II BINは変更していません。
  0.4.0-alpha.2は全曲とSTOP/通信休止/再開が実機合格済み。元のZIPを復帰用に保持してください。
  2026-11-14、0.5.0-alpha.1のUSB-MIDI認識、FM/SSG音階、6声同時発音、全音停止、
  左右正常、歪み/音切れなしをユーザー実機で確認しました。OS名・CDC生ログは未提示です。
  ただし後の切替確認で和音保持に問題があり、通常Note Off後の入力破棄をalpha.2で修正しました。
  追加ログでaudio_ready=0 fault=16を確認し、DMA停止・再初期化をalpha.3で修正しました。
  alpha.3の単独6音と和音保持はユーザー実機で再確認済み（audio_ready=1/fault=0、生ログ未提示）。
  MIDI/I2C切替もHOSTログとRev C末尾で実機受入済み（I2C191/191、fault=0/gates=0、MIDI owned=0）。
  物理USB切断・復帰もMIDI/I2C双方でユーザー実機受入済み。修正版HOST v1.1とRev Cログを照合しました。
  現在のUF2と修正版ライブラリを維持し、常用時はDAILY-USE-README.txtを参照してください。
  曲入りBIN/ZIPは手元での試験専用。公開用Gitには含めません。

更新
  1. 音量を下げ、操作側Picoのプログラムを停止し、USB操作画面で全音停止します。
  2. ZIPのpc/revc-console.htmlを新しい版へ更新して再読み込みします。
     「BOOTSELへ移る」で再起動し、このZIPのrevc-c.uf2をRev Cへコピーしてください。
     BOOTSELボタンを使う方法でも構いません。配線と外部5Vは従来どおりです。
  3. USBが再認識されたらCDCへ接続し、次を確認してください。
       STATUS C=0.5.0-alpha.3 audio_ready=1 fault=0 ... gates=0 fm_gain_eighths=8
       MIDI protocol=1 owned=0 ... mask=0 gate=0
     CDC製品名は「YM2203 Rev C C MIDI」、MIDIは「YM2203 Rev C MIDI」です。
     OSによりポート名の表示は異なります。認識直後は無音で、自動演奏しません。
     C版のCDCはログ/操作用で、MicroPython REPLではありません。
     Thonnyは操作側Picoへ接続します。Rev CのCDCは同梱の操作画面を使用します。

PC確認画面
  ZIPのpcフォルダで次を実行してください。
       python3 -m http.server 8765 --bind 127.0.0.1
  Windowsでpython3がない場合は同じ引数をpy -m http.serverへ渡します。
  ログ/操作: http://127.0.0.1:8765/revc-console.html
  MIDI演奏:  http://127.0.0.1:8765/usb-midi-test.html
  MIDI画面は「MIDI接続先を読み込む」→Rev CのMIDI出力先を明示的に選択します。
  MIDI許可はsysex:falseで要求し、CDN/外部通信は使いません。
  Web MIDI非対応環境ではその旨を表示します。対応ブラウザーまたはMIDIソフトを使用します。

最初の実機確認（2026-11-14実機合格。以下は実施手順を保存）
  1. FM CH1（MIDI1）で音階、次にSSG A（MIDI4）で音階を再生します。
     どちらも左右で「ドレミファソファミレド」が聞こえることを確認します。
  2. 「1. 6声を順に確認して和音を保持」を押します。
     FM3声、SSG3声が順に鳴り、最後に6声が同時に鳴ります。
     最後の和音は別画面へ移動しても継続し、全音停止または2分で停止します。
  3. 「MIDI全音停止」で消音することを確認します。
     CDCの状態取得でfault=0、gates=0を確認してください。
  4. 認識名、FM/SSG音階、6声、全音停止、左右、歪み/予定外の音切れの有無とCDCログを送ってください。
  基本確認は完了しています。次の制御権切替ではこの基本確認を繰り返す必要はありません。

I2Cとの切替確認（2026-11-14実機受入済み。実施手順を保存）
  操作側の/lib/ym2203_revc_stream.pyと/music/song.binは既存のものを使用できます。
  ZIPのhost/music/recovery.binを操作側/music/recovery.binへ保存してください。
  a. MIDI画面のボタン1で6声の和音を保持。
  b. 操作側Thonnyでhost/midi_handover.pyをPCから開きF5実行。
     状態取得だけではMIDIを止めず、BEGINはSTATE(4)で拒否され、2秒間和音を維持します。
     次にI2C STOPでMIDIを停止し、3秒の無音後、13秒のI2C音階・和音を再生します。
  c. HOSTの「I2C PLAY」が出たら5秒以内にMIDI画面のボタン2を押します。
     約5秒のMIDI発音要求が送られますが、I2Cが所有中なのでMIDIは鳴らないのが正常です。
     I2CのFM/SSG音階と和音が完走し、3秒無音、HOST PASS/DONEになることを確認します。
  d. HOSTのDONE後にMIDI画面のボタン3を押すと、新しいNote Onで6声が再開します。
     MIDI全音停止で消音。CDCのMIDI rejectedが増え、fault=0であることを確認します。
  HOSTはレジスタ件数・CRCを検査し、音の混入や消音は耳とCDCログで確認します。
  I2C v2はMIDIの所有ビットを公開しないため、BEGINの拒否とCDCのowned=1を併せて確認します。

MIDI仕様（従来のMicroPython版と同じ割り当て）
  MIDI1=FM CH1 / MIDI2=FM CH2 / MIDI3=FM CH3
  MIDI4=SSG A / MIDI5=SSG B / MIDI6=SSG C
  各チャンネル1音、最新ノート優先。古いNote Offでは現在の音を止めません。
  Note On、Note Off、Note On velocity0、CC123（当該声の停止）、
  CC120とSystem Reset（MIDI全体の即時消音）に対応します。
  velocity1～127は固定音量。FMは正弦波系の固定音色・全4OPキーオン、SSGは矩形波・音量7。
  FMノート0～116、SSGノート11～127。範囲外は当該声を停止します。
  MIDI7～16とcable1以上、SysEx、Program Change、Pitch Bend、ペダルは未対応です。
  MIDI送信とUSBオーディオもありません。音は従来どおりJLINE→AMS-22から取り込みます。
  音色編集やI2Cからの直接MIDI発音APIはこの版にはありません。

制御権と停止
  I2CのPREFILL/RUNNING中とUSB内蔵再生中のMIDI Note Onは破棄し、後から再演奏しません。
  MIDIが所有中のI2C BEGINとUSB play/test/capture/bus変更は拒否します。
  I2Cの状態取得/PINGは可能で、I2C STOPとCDC STOPは全体停止として優先します。
  MIDIのCC120/ResetはMIDIにだけ作用し、I2Cの演奏を止めません。
  MIDI全声OFFと書込み完了後、135msの排出を経てゲートを閉じ、制御権を解放します。
  全体STOP/panic直後の200msは残存USB MIDIを破棄します。再発音は300ms以上待ってください。
  MIDI演奏にはI2Cの1秒KEEPは不要です。USBバス接続中はNote Offまで保持します。
  USB reset/切断/休止、またはSOF進行停止250msでMIDIを消音し、再接続だけでは再発音しません。
  CDCポートを閉じるだけではMIDIを止めません。ただし操作画面の「接続を閉じる」と
  ページ終了は明示的なSTOPを送るため、演奏も停止します。
  MIDIアプリだけを終了してNote Offが来ない場合は、MIDI全音停止またはCDC/I2C STOPで止めます。
  I2C所有中のUSB reset/切断はI2C演奏を止めず、I2Cのリースで監視します。

実装・検証
  TinyUSBの標準MIDIクラス、固定64バイト受信FIFO、最大4イベント/メインループ。
  YMは最大1レジスタ/ループでBUSYを監視し、BUSY中のレジスタと値を固定します。
  初期音色は88書込み、6.75msの無音排出後にキーオンします。音声蓄積は従来の4.5msです。
  実際の可聴遅延は未測定。高密度なMIDI連打は各声の最新状態を優先します。
  MIDIバス書込みの100ms超過/失敗は出力を閉じ、音声fault17で停止します。
  公式TinyUSBヘッダーによるUSB記述子検査、実際のmain.cを用いた切替/USB喪失試験、
  発音処理・音程表・BUSY・I2C全曲のモデル試験を実施しています。
  OSでの列挙・RP2350の実効時間・ライン音声は実機受入で確認します。

一次資料（ビルドではtoolchain-lock.jsonのコミットを固定）
  https://www.usb.org/sites/default/files/midi10.pdf
  https://github.com/hathach/tinyusb/tree/86ad6e56c1700e85f1c5678607a762cfe3aa2f47/src/class/midi
  https://github.com/hathach/tinyusb/blob/86ad6e56c1700e85f1c5678607a762cfe3aa2f47/src/device/usbd.h
