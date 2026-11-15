YM2203 Rev C C0.5.0-alpha.2 / 通常キーオフ後の和音保持修正

修正
  alpha.1は通常のNote Offで全声が消え、135msの排出後に所有権を解放するときも、
  STOP/panic用の200ms入力破棄を始めていました。合計335msの間、次のNote Onを落としえます。
  MIDI画面のボタン1は単独音のNote Offから300ms後に次の音を送るため、
  単独音や最後の6声和音が発音しない組み合わせがあります。
  実際のCメイン処理と同じイベント間隔のモデルで、修正前の不発音と修正後の発音を確認しました。
  発音処理単体と画面単体の従来試験だけでは、この組み合わせを捉えられていませんでした。

  通常解放後の余分な200ms入力破棄だけを除きます。135msの音声排出は維持します。
  明示的STOP、MIDI panic、USB reset/休止/喪失時の入力破棄・消音は維持します。
  USB記述子・音程表・GPIO・FM受信・PCM変換・I2S・I2C v2パケット形式は変更しません。
  新alpha.2の物理試験はこれからです。今回の修正ZIPにYs II BINは含めません。

更新と再確認
  1. 音量を下げ、MIDI全音停止とCDC全音停止を行います。
     同梱pc/revc-console.htmlを使い、BOOTSELで今回のrevc-c.uf2をRev Cへコピーしてください。
     再接続してSTATUS C=0.5.0-alpha.2、audio_ready=1、fault=0を確認します。
  2. 同梱pc/usb-midi-test.htmlを更新して再読み込みし、MIDI接続先を選び直してください。
     ボタン1を押し、6つの単独音の後、6声和音が持続することを確認します。
     和音を保持したままThonnyやCDC画面へ移動できることも確認してください。
  3. 保持ができたら、MIDI-I2C-HANDOVER-README.txtの手順2（HOSTをF5実行）から続けられます。
     host/midi_handover.py、操作側の/lib/ym2203_revc_stream.pyと/music/recovery.binは変更不要です。
     全曲や音声経路の試験を最初からやり直す必要はありません。

  まだ発音しない場合は、HOSTを開始せず、CDCのSTATUS/MIDI/FAIL行とMIDI画面の表示を保存してください。
  alpha.1の既存配布ZIPと基本動作の実機報告は履歴として保持します。
