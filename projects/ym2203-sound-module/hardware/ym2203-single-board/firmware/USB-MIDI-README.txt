YM2203 Rev C / USB-MIDI初版 0.2.0-alpha.1
2026-11-13

実装と確認範囲
--------------
公式MicroPython1.29.0のmachine.USBDeviceで、組込みCDCにUSB-MIDI1.0を追加する。
UF2の独自ビルドやGPIO/基板の変更は不要。Pico2のデータ用USB端子をPCへ接続する。
電源/音声接続は前回合格したRev C/AMS-22の構成を使い、最初は音量を低くする。
USBオーディオではない。MIDIを受信してYM2203Cを制御し、音はJLINEから出す。

I2C版alpha.2の基本/3分連続/停止通信復帰はユーザー実機で全件合格済み。
USB-MIDIデバイス認識、FM/SSG音階、全音停止、左右正常、歪み/音切れなし、
Thonny接続は2026-11-13にユーザー実機で確認済み（OS名は未報告）。
USB-MIDI-SIX-HANDOVER-README.txtの6声・I2C切替もユーザーから確認完了の報告あり。
初期受入確認は完了。今回の報告は簡潔な確認であり、HOST全ログや期限超過回数は未提示。
USB物理切断時の消音、可聴遅延の測定、長時間運転は未確認。
Windows/macOS実機での列挙成功や24時間運転を、自動テストから保証しない。

導入（Rev C側）
---------------
1. Rev C側でCtrl+Cを送りSAFEを確認する。既存boot.py/main.pyがあればPCへ保存する。
   更新中の自動起動を止めるため、REPLで次を実行する。
       open('/disable-ym2203','w').close()
2. ZIP内の target/lib/ の全11ファイルを、Rev Cの /lib/ へ保存する。
   alpha.2からの最小差分は次の5ファイル。
       ym2203_fw.py / ym2203_hw.py / ym2203_midi.py / ym2203_usb.py / ym2203_pitch.py
   ym2203_audio.pyと診断由来ヘルパー5本は変更なし。操作側Picoのファイル更新は不要。
3. target/boot.py と target/main.py をRev Cの最上位 /boot.py /main.py へ保存する。
   boot.pyはUSB設定、main.pyは無音の初期化とサーバー起動を行う。
   boot.pyをエディタから実行してUSB構成を切り替えず、次の再起動で読み込ませる。
4. REPLで次を実行し、Ctrl+Dを1回送る。
       import os
       os.remove('/disable-ym2203')
   USBが再認識される。必要ならThonnyでシリアル接続先を選び直し、しばらく待つ。
   ソフトリセット時にUSBポートが一時消えるのはruntime USBの仕様。
   エディタのRUNを繰り返す必要はなく、main.pyが自動で起動する。
5. 起動メッセージは次の版になっていることを確認する。
       YM2203 Rev C firmware 0.2.0-alpha.1 READY I2C=0x42;outputs muted
   初期状態では全音源キーOFF/SSG音量0、出力ゲートOFF。MIDIデータ受信まで発音しない。

PCからの最初の演奏
------------------
DAW等ではMIDI出力先に「YM2203 Rev C MIDI」を選ぶ。ポート名はOSにより異なる場合がある。
同梱の pc/usb-midi-test.html も使える。PCで pc フォルダをカレントディレクトリにして、
次のローカルサーバーを起動する。
    python3 -m http.server 8765 --bind 127.0.0.1
Windowsでpython3がない場合は、同じ引数を py -m http.server に渡す。
ブラウザーで http://127.0.0.1:8765/usb-midi-test.html を開く。
「MIDI接続先を読み込む」を押し、表示されるMIDIアクセス許可を操作する。
送信先を明示的に選択してから、FM CH1またはSSG Aで音階を再生する。
Web MIDIがないブラウザーでは画面にその旨を表示するので、対応ブラウザーやMIDIソフトを使う。
確認画面はシステムのMIDI APIを使い、CDNやネットワーク通信は行わない。

最初の確認は実機合格済み。確認画面に6声・切替用のボタン1/2/3を追加した。
切替用の保持モードだけは別画面へ移っても発音要求を保持し、全音停止/ページ終了/2分で解除する。
通常の音階・単音モードは従来どおり画面を離れると停止する。
最初の確認で使ったMIDIポート認識、FM CH1/SSG Aの音階、全音停止も引き続き利用できる。
できればCDCがThonnyから使えることも確認する。USBを抜いた場合はMIDI音が消え、
再接続しただけでは再発音せず、明示的な新しいNote Onで再開する仕様。
切断確認をする場合、PCへ取り込む音声USBまで一緒に外す必要はない。

MIDIの割り当て
--------------
MIDI1=FM CH1 / MIDI2=FM CH2 / MIDI3=FM CH3
MIDI4=SSG A / MIDI5=SSG B / MIDI6=SSG C
各チャンネル1音、合計FM3+SSG3声。MIDI7..16とUSB cable1以上は無視する。
Note On(0x9n)、Note Off(0x8n)、Note On velocity0に対応。
同じチャンネルへ別ノートを入れると最新ノートで置き換える。
古いノートへのNote Offは無視し、現在ノートのNote Offでその声を停止する。
古い押鍵への戻り/サステインペダル/チャンネル内の複数音割り当ては実装しない。
velocity1..127は発音の判定にのみ使い、強弱は初版では固定。
FMは初期状態で単純な正弦波系音色、SSGは音量7の矩形波。
FMの現在の音色パラメータとSSGミキサー設定はI2C側で変更できるが、演奏中の同時変更は拒否する。
MIDIのFMキーオンは全4オペレーター。SSGのNote Onは固定音量でエンベロープ指定を置き換える。
GM音色番号/Program Change、Pitch Bend、SysEx、ペダル、MIDI送信は未実装。

CC123（All Notes Off）は対象チャンネルのノートを停止する。
CC120（All Sound Off）はMIDI全6声の出力を即時ミュートし、未処理MIDIも破棄する。
System Reset(0xFF)もMIDI全体を停止する。I2C側が所有中の演奏には作用しない。
panic後の停止処理中のNote Onは無視する。確認画面は再発音前に300ms待機する。

4MHzの固定クロックに対応する音程表を使う。FMはノート0..116、SSGは11..127。
範囲外のNote OnはそのMIDI声を停止する。SSGは整数周期のため高音ほど音程の丸めが大きい。
ノート番号60を確認画面のドに使う。DAWのオクターブ名の表記差はノート番号で確認する。

I2Cとの制御権・停止
------------------
I2Cの接続/API/ホストライブラリは従来どおり使える。先に演奏を始めた側を優先する。
I2Cの演奏/処理/予約登録がある間のMIDI Note Onは破棄し、後から自動再演奏しない。
MIDIが所有中のI2C書き込み/PLAY/KEEPはBUSY(3)。PING/状態読み取りとSTOPは使える。
I2C STOPは全体停止としてMIDIにも優先し、MIDIのノート/保留書き込みを破棄する。
I2Cホストライブラリのコンストラクタ/stream()もSTOPを送るため、起動するとMIDI演奏を停止する。
MIDIの全キーOFFと書き込み完了後、135msの排出を経て制御権を解放する。
MIDIはUSBバスが動いている限りNote Offまで保持し、I2C用の1秒KEEPを必要としない。
USB reset、またはSOFフレームの進行が250ms途絶えたときにMIDI出力を閉じる。
USBの休止/切断とアプリだけの終了は異なる。ノートオフなしでアプリだけ終了した場合は、
CC120/CC123またはI2C STOPで停止する。デバイスの1秒リースはI2C演奏にだけ適用する。

処理時間と安全停止
------------------
64バイトの固定受信バッファ、1pollにつき最大1 MIDIイベントを解釈する。
バッファを使い切るまで次のUSB転送を受け付けず、USBのバックプレッシャーを使う。
YM書き込みはI2Cと合計して1poll最大1個、約11.25ms刻み。
発音にはキーOFF/音程2レジスタ/キーONの4段階を使い、初回は全声OFFと無音の排出を行う。
初回の発音や6音同時要求には数百ms程度の準備/逐次適用が入りうる。低遅延を保証する版ではない。
音声のバッファ時間も加わるため、実際の可聴遅延は実機で確認する。
速い連打では各声の最新状態を優先し、途中のノート状態が適用されない場合がある。
USB/I2CコールバックからYM書き込み、ログ出力、明示的GCを行わない。
YM BUSYの100ms超過や既存のFM DMA/期限異常はゲートを閉じて停止する。

更新・復旧
----------
Ctrl+Cでサーバーを止めると、LINE/ARMを下げ、USBのMIDI受信を停止し、音声/I2Cを解放する。
CDC+MIDIのUSB構成自体は保持するので、CDCからファイルを更新できる。
問題がある場合はCtrl+C後に /disable-ym2203 を作りCtrl+Dすると、USB-MIDIと自動起動を抑止する。
I2C専用に戻すには停止中にboot.pyをPCへ退避/削除し、Ctrl+Dする。
新しい/libのままでもboot.pyを実行しなければI2Cのみで動作する。
alpha.2へ完全に戻す場合は保存したalpha.2 ZIPの/lib/main.py構成へ戻す（製造データは変更しない）。

仕様と実装の一次資料
--------------------
https://docs.micropython.org/en/v1.29.0/library/machine.USBDevice.html
https://github.com/micropython/micropython/blob/v1.29.0/shared/tinyusb/mp_usbd_runtime.c
https://www.usb.org/sites/default/files/midi10.pdf
https://raw.githubusercontent.com/raspberrypi/pico-sdk/master/src/rp2350/hardware_regs/include/hardware/regs/usb.h
https://raw.githubusercontent.com/raspberrypi/pico-sdk/master/src/rp2350/hardware_regs/include/hardware/regs/addressmap.h
USB-MIDIは標準デスクリプタ/APIに基づく独自実装。上流USBライブラリのコードは同梱/複製していない。
USBのVID/PIDとCDCデスクリプタは組込みMicroPythonのものを保持し、製品名/追加インターフェースと
bcdDeviceを設定する。
