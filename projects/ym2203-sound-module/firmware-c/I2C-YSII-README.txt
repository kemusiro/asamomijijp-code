Rev C C SDK 0.5.0-alpha.3 / 操作側MicroPythonからYs IIをI2C再生

受入済み0.4.0-alpha.2と同じI2C v2へUSB-MIDIを追加したC版です。
操作側/lib/ym2203_revc_stream.py、host/main.py、Ys II BINは変更していません。
音声受信・変換・I2S・100%出力と、alpha.2のTX FIFO起動修正を維持します。
USB-MIDIの初期確認は同梱USB-MIDI-README.txtを先に読んでください。
新しいI2C v2は旧MicroPython版v1と非互換。host/lib/ym2203_revc_stream.pyを使います。
全曲BINは操作側Picoから順次読み、Rev Cへは最大1024イベントだけ先送りします。
このZIPのUF2にYs IIは内蔵していません。USBの「組み込みBIN」はオリジナルのテスト音階です。

1. 音量を下げ、両側のプログラムを停止し、電源を切って結線を確認します。
   操作側Pico/Pico2は公式MicroPython v1.29.0、Rev C側Pico2はこのZIPのrevc-c.uf2。
   旧Pico内のmain.py/boot.py/libや必要データはPCへバックアップしてください。
   Rev C JHOST 1=GND →操作側GND、2=SDA→GP0、3=SCL→GP1。
   既存の4.7kΩプルアップを使用。3.3V信号のみ。5V/3.3Vの電源線は両ボード間につながない。
   外部5VはRev C JPOWERから供給。LINE→AMS-22の結線は従来どおり。

2. Rev CをBOOTSELで起動し、外部5Vを供給してrevc-c.uf2をコピーします。
   既存alpha.7へ戻すZIPは保持してください。配線・GPIOの再割当はありません。
   操作画面を再読み込みしてC=0.5.0-alpha.3、audio_ready=1 fault=0を確認します。
   必要なら「音声経路テスト（13秒）」で確認。FM100%、「バス短縮（標準）」を使います。
   このC版はMicroPythonではなく、ThonnyのREPLにはつながりません。

3. Thonnyを操作側Pico/Pico2へ接続します。
   ZIP内host/lib/ym2203_revc_stream.py →操作側 /lib/ym2203_revc_stream.py
   既存の操作側 /music/song.bin はそのまま使用。この修正ZIPにはYs II BINを同梱しません。
   host/main.pyはPCのThonnyエディタで開きます。
   まずはPicoのmain.pyとして保存せず、F5で実行してください。自動起動の登録は不要です。
   「OTHER Pico only」は操作側であることの確認です。Rev C上でこのPythonを実行しません。

4. I2C v2識別後、5秒待ち、ファイルの長さとCRCを検査してから再生します。
   hardware I2C0、GP0/1、100kHz、アドレス0x42。旧版の10kHz/40ms ACK待ちは使いません。
   演奏中はホストの印字で転送を止めないため、進捗表示を行いません。約5分待ちます。
   Rev CのUSB操作画面は30秒ごとにI2C受信・適用件数、音声、遅延を表示します。
   I2C演奏はUSB操作画面を切断しても継続し、操作側とのI2Cリースで監視します。

5. 操作側: HOST PASS、123137/123137、period=298218ms、CRC32=ae592289、DONE。
   Rev C: DONE I2C、events=123137/123137、fault=0、gates=0。
   左右、FM/SSGバランス、歪み・予定外の音切れ、最後の消音を確認してください。
   操作側とRev C両方のログを保存してください。0.4.0-alpha.2での物理I2C完走は受入済みです。この新しい0.5版は実機受入前です。

停止・復帰:
   ThonnyのCtrl+Cで例外処理が動けばSTOPを送り、最後にGP0/1を入力へ戻します。
   USB操作画面の「全音停止」も有効です。
   強制切断などでSTOPを送れなくても、I2C有効命令が1秒来なければ自動消音します。
   音が勝手に再開する仕様ではありません。再演奏はスクリプトを明示的に実行し直します。
   エラー時はそのままログを保存。配線変更や抜き差しは両側を停止・電源断後に行います。

既知の制約:
   SDK2.2.0のI2C slave IRQ、3.3V信号と100kHzの電気特性、操作側の実効速度は実機確認が必要。
   自動試験ではCプロトコル/スケジューラと同じPythonホストを使い、I2Cと時間をモデル化しています。
   C版USB-MIDIの仕様と制御権はUSB-MIDI-README.txtを参照。旧版ZIPは復帰用に維持します。
   host/music/song.binと曲を含む配布ZIPは手元のテスト専用で、Gitへ追加・公開しません。

追加の診断: fault16はTX FIFOを1msで満たせない起動失敗。BEGINのcode12は音声準備失敗。
その場合はRev C側のSTATUS/AUDIO/FAIL/I2C行とHOSTログを保存してください。
