YM2203 Rev C C0.5.0-alpha.3 / USB-MIDI・I2C制御権切替の総合確認

準備
  USB-MIDI基本確認はalpha.1で合格済みですが、通常Note Off後の入力破棄不具合が判明しました。
  追加の音声起動失敗fault16も修正したalpha.3を使用します。
  2026-11-14、alpha.3で6つの単独音と和音保持、audio_ready=1/fault=0をユーザー実機で確認済み。
  この版を使用中なら、UF2の再書き込みは不要です。配線変更も不要です。
  前回のZIPのpc/usb-midi-test.htmlとpc/revc-console.htmlをそのまま使います。
  操作側Picoは既存の/lib/ym2203_revc_stream.pyと/music/recovery.binを使用します。
  recovery.binは前回の停止・通信復帰試験と同じ191件・13秒・CRC32=e5df0948です。
  未配置の場合だけ、前回ZIPのhost/music/recovery.binを/music/recovery.binへ保存してください。
  Ys IIの/music/song.binは使用しません。全曲再生の再試験は今回不要です。
  操作側GP0/1、Rev C GP20/21、共通GND、100kHz、3.3V信号の結線を維持します。
  両方の音量を低めにし、他のMIDI送信ソフトと操作側の別スクリプトは停止してください。
  Rev CのCDCはログ用画面、Thonnyは操作側Picoへ接続します。

順序（1回にまとめます。音が出始めてから約35秒＋画面操作時間）
  1. MIDI確認画面の「1. 6声を順に確認して和音を保持」を押します。
     各声の後、6声の和音が持続し、画面に「6声の発音要求を送信しました」と出るまで待ちます。
     そのまま2分以内に次へ進みます。この保持モードはThonnyへ切り替えても停止しません。
  2. Thonnyで前回ZIPのhost/midi_handover.pyをPCから開き、操作側Picoを選んでF5実行します。
     Pico内のmain.pyとして保存する必要はありません。
     最初のI2C BEGINはMIDI所有中なのでcode4/STATEで拒否されます。
     HOSTの「PASS: BEGIN rejected ...」が出てからも、和音が約2秒持続することを確認します。
     この拒否は正常です。例外でプログラムが終了するのは異常です。
  3. I2C STOPで和音が消え、3秒間無音になることを確認します。
     次にHOSTに「I2C PLAY: click MIDI page button2 within 5 seconds」が出ます。
     5秒以内にMIDI画面の「2. I2C中へFM・SSG音階を送信」を1回押してください。
     約5秒分のMIDI要求が送られますが、聞こえるのはI2Cの13秒診断だけが正常です。
     I2C診断はFMのドレミファソファミレド→SSGの同じ音階→6声和音の順です。
     MIDIの音が混ざらず、途中でリセットや音切れが起きないことを確認します。
  4. I2Cが191/191件で完了し、3秒間無音になることを確認します。
     拒否されたMIDIが、後から勝手に発音しないことも確認します。
     HOST PASS・DONEが出た後にMIDI画面の「3. 復帰確認用に6声を保持」を押します。
     新しいNote Onで6声が再び鳴ることを確認し、「MIDI全音停止」で消音します。
  5. CDC画面の状態取得でfault=0、gates=0、MIDI owned=0を確認します。
     ボタン2が中断なく最後まで送信すれば、MIDI rejectedは通常18件増えます。
     ボタン2の送信完了までMIDI画面を前面に保ってください。通常モードは画面を離れると停止します。
     rejectedは累積値です。18未満なら全プローブの送信完了は確定せず、実際の値と音を記録します。

ログの読み方
  HOSTは最初のBEGIN拒否、I2C STOP、13秒診断の件数・CRC・DONEを検査します。
  MIDI側の所有状態・拒否数はCDCのMIDI行と、実際に聞こえた音で併せて判断します。
  今回は通信休止の試験ではないため、FAIL I2C error=8は期待しません。
  MIDI中のBEGIN拒否時のresult=4は正常です。その後のI2C STOPでresult=0へ戻ります。
  HOST完了時のI2C状態はDONE(state=3)、error=0です。その後ボタン3でMIDIを再開し、
  MIDI全音停止すると、I2C表示もSTOPPED(state=4)、error=0になります。これは正常です。
  CDCのSTATUS stateとI2C行のstateは別の列挙なので、値だけを直接比較しないでください。

報告
  MIDI中のBEGIN拒否で和音が持続したこと、STOP後の3秒無音、I2C中のMIDI不発音、
  I2C終了後の3秒無音、明示的な新しいNote Onによる復帰、最後の消音を確認してください。
  左右、歪み・予定外の音切れの有無、HOST全ログとRev C側の最後のSTATUS/AUDIO/I2C/MIDIを送ってください。
  2026-11-14、ユーザーの音声確認、HOST全ログとRev C末尾で切替の実機受入を完了しました。
  I2C191/191、audio_ready=1/fault=0/gates=0、MIDI owned=0を確認。rejected=7でした。
  18音全件のプローブ送信完了は未確認であり、7件の拒否と報告された不発音を受入範囲とします。
  次はUSB-DISCONNECT-README.txtの物理USB切断・復帰確認です。
