YM2203 Rev C / 常用セット 0.5.0-alpha.3 + 修正版I2C HOST
2026-11-14

現在の実機をそのまま使用できます
  Rev CはC0.5.0-alpha.3、操作側PicoはKEEP/DONE修正版ライブラリです。
  このセットのUF2は、既に実機確認したalpha.3とバイト単位で同一です。再書き込み不要です。
  HOST v1.1も確認済みなら、ライブラリの再転送と追加の受入試験は不要です。
  ファームウェア番号を変更せず、分かれていたUF2・HOST・画面・手順をまとめたセットです。
  package-manifest.jsonに各ファイルと元UF2のSHA-256を記録します。
  firmware-build-manifest.jsonは元のUF2ビルド時点の記録で、更新後HOSTの一覧ではありません。

Ys IIをI2Cで演奏する
  1. 従来の配線・外部5V・LINE→AMS-22を維持し、両方の音量を低めにします。
     電源投入はJPOWER外部5V→各PicoのUSBの順です。I2C/GNDの配線は給電前に行います。
  2. 操作側Picoの/lib/ym2203_revc_stream.pyは、このセットのhost/libと同じ修正版を使用します。
     別のPicoへ導入する場合は転送後Ctrl+Dでモジュールを読み直してください。
  3. 操作側の既存/music/song.binを使用します。123137件、298218ms、CRC32=ae592289。
     楽曲ファイルはこのセットに含めません。既に保存したファイルを消したり置換したりする必要はありません。
  4. Thonnyを操作側Picoへ接続し、PCのhost/main.pyを開いてF5実行します。
     Rev CへMicroPythonコードを転送しません。main.pyとして自動起動させる設定も不要です。
  5. 約5分の演奏後、HOST PASS・DONE、Rev Cの全件実行・fault=0・gates=0を確認できます。
     再演奏はF5で明示的に開始します。終了後・再接続後の自動再演奏はありません。
  FM既定値は100%（fm_gain_eighths=8）です。まずこの値で使用してください。
  Rev CのUSBを外しても、外部5Vと操作側I2Cを維持すればI2C演奏は継続します。
  操作側PicoのUSBはThonny用として接続します。給電だけで演奏を始める機能は今回追加していません。

USB-MIDIで演奏する
  1. I2C演奏を停止してから、従来のMIDI送信ソフトまたはpc/usb-midi-test.htmlを使います。
     同梱画面を使う場合はpcフォルダで python3 -m http.server 8765 --bind 127.0.0.1 を実行し、
     ブラウザーで http://127.0.0.1:8765/usb-midi-test.html を開きます。
     CDCログ画面は同じサーバーの/revc-console.htmlです。従来と同じブラウザーを使用します。
  2. MIDI接続先を選択します。MIDI1～3はFM CH1～3、MIDI4～6はSSG A～Cです。
     各チャンネル1音、固定音色・固定音量です。velocityは発音/消音の判定に使います。
  3. 停止はMIDI全音停止。新しいNote Onを送るまで再発音しません。
     USB切断でMIDIは消音し、接続を戻すだけでは再発音しません。
  I2CとMIDIは先に演奏を始めた側が所有します。I2C中のMIDI要求は予約されず破棄されます。
  MIDI中のI2C BEGINは拒否されます。切替はCDC/I2Cの全音停止後に明示的に行ってください。

停止と終了
  操作側ThonnyのCtrl+C、CDCの全音停止、I2C STOPを使用できます。
  I2C補充が途絶えると1秒リースで消音し、明示的なSTOP/BEGIN/PLAYで再開します。
  正常終了直後の最後のKEEPは、修正版HOSTが件数・CRC等を照合して終了判定します。
  音声faultが発生した場合はログを保存し、再起動してから原因を確認してください。
  電源を切る場合は演奏停止後、Pico USBとI2Cを外してからJPOWERを外します。

実機確認の範囲
  C0.4.0-alpha.2: 操作側MicroPythonからYs II全曲、STOP・リース・再接続・再演奏を受入済み。
  C0.5.0-alpha.3: MIDI単独6声/和音、MIDI/I2C切替、MIDIのUSB喪失時停止、
    USBを抜いたままのI2C191件/13秒完走、再接続後の無音と明示的MIDI復帰を受入済み。
    今回のI2C診断は最大書込み開始遅延4751us、fault=0、クリップ0でした。
  C0.5.0-alpha.3のYs II全曲はモデル検証済みですが、同版での5分間の物理完走ログは未提示です。
  このセットを再度書き込む試験は行っていません。実機確認した同一UF2と同一HOSTを再梱包しています。
  可聴遅延の実測、24時間運転、400kHz I2C、USB/GNDノイズ絶縁の評価は今回の受入に含めません。
  音色編集、Program Change、Pitch Bend、ペダル、SysEx、USBオーディオ、MicroPython REPLは未実装です。
  追加機能は別の変更として扱います。今回の基本機能確認はここで一区切りとします。

復帰・保存
  過去のUF2/ZIPは上書きせず保持してください。初めて導入する場合だけUSB-MIDI-README.txtの更新手順を参照します。
  詳しい経緯はverification/の実機受入記録とREADME-ja.mdにあります。
