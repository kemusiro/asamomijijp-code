YM2203C Rev C 常用ファームウェア 0.2.0-alpha.1 / I2C API v1.1 + USB-MIDI1.0
2026-11-13

実装内容と位置づけ
------------------
常用I2C版alpha.2の基本再生、3分間補充式再生、停止・通信復帰の総合確認は実機で合格済み。
今回の0.2.0-alpha.1は、CDCを保持するUSB-MIDI1.0、FM3+SSG3声、I2C/MIDIの制御権を追加した初版。
USB-MIDIの認識、FM/SSG音階、全音停止、左右正常、歪み/音切れなし、Thonny接続は実機合格。
USB-MIDI-SIX-HANDOVER-README.txtの6声・I2C切替もユーザーから確認完了の報告あり。
初期受入確認は完了。今回の報告は簡潔な確認であり、HOST全ログや期限超過回数は未提示。
可聴遅延の測定、物理USB切断・長時間運転は未確認。
USB-MIDI-README.txtに導入、PC確認画面、対応MIDIと制約、復旧手順をまとめた。
I2Cのワイヤ形式/既存ホストライブラリは互換。状態窓の追加はprotocol-v1.mdを参照。
新しいGPIOは使用しない。YM/DACのPIO、音声変換、出力上限はalpha.2から変更しない。
既存の配布ZIPは当時の実装・検証記録として変更しない。実機記録はhardware-results.jsonを参照。

前提
----
- Rev C基板、YM2203C、4MHzクロック、Pico 2/RP2350 Arm。
- 実機診断と同じ公式MicroPython v1.29.0。UF2自体は同梱しない。
  https://micropython.org/download/RPI_PICO2/
- GPIO割り当て、基板、結線は変更なし。
  GP0..7=YM D0..7、8=A0、9=RESET_RELEASE、10/11/12=I2S DATA/BCLK/LRCK、
  13/14/15=CS/WR/RD、16/17/18=FM SD/CLK/SH、19=LINE_ALLOW、
  20/21=外部I2C SDA/SCL、22=ARM、26=DAC_ALLOW、28=IRQ、27=予備。
- 操作側Pico/Pico 2: hardware I2C0、GP0=SDA/GP1=SCL、10kHz、3.3V。
  Rev C JHOST1=GND→HOST GND、2=SDA→HOST GP0、3=SCL→HOST GP1。
  Rev Cの4.7kΩプルアップを使用。ボード間の電源線は接続しない。
- JPOWER外部5V、JLINE→AMS-22 LINE IN。音量は低くして開始する。
  既知のUSB/GNDノイズ対策は別工程。診断合格時と同じ給電・音声接続を使用する。

Thonnyでの導入
--------------
USB-MIDIを使う場合は USB-MIDI-README.txt の手順に従い、target/lib/全11ファイルと
最上位のboot.py/main.pyを保存する。boot.pyはUSB設定を音声起動前に行う。
I2Cだけで使う場合はboot.pyを入れず、/libを保存してCtrl+D後に次を手動実行してもよい。
    from ym2203_hw import run
    run()
操作側Picoの/lib/ym2203_revc.py、example.py、endurance.py、recovery.pyはalpha.2のまま使える。
PC側のUSB-MIDI確認はpc/usb-midi-test.htmlをローカルサーバーから開く。

停止・復旧・更新
----------------
- HOSTのstop()は全音・ゲートを停止し、残りの予約イベントを破棄する。
- I2C演奏中の通信が途絶えると最後の有効な更新から約1秒で全音を停止する。状態読み取りだけでは
  リースを延長しない。復帰時は明示的stop()後、音色・譜面を再設定してplay()/stream()。
- Ctrl+C/エラー/メモリ不足ではLINE_ALLOWとARMを先に下げ、リセット・ミュート・
  DMA/PIO/I2S/I2Cの解放を行いSAFEへ戻る。自動で再発音しない。
- 起動を止めるには、2秒の待機中にCtrl+C、またはThonnyから
       open('/disable-ym2203','w').close()
  を作成してCtrl+D。このファイルがあると自動起動しない。
  再開はファイルを削除。main.pyを削除/別名保存してもよい。
- 更新はCtrl+C後に/libとmain.pyを置き換えCtrl+D。通電中の配線変更はしない。
  診断時と同様に完全な電源再投入が必要なら、Pico USBとJPOWER両方を外して5秒待つ。

ホスト側のAPI
-------------
    from machine import Pin,I2C
    from ym2203_revc import YM2203
    chip=YM2203(I2C(0,sda=Pin(0),scl=Pin(1),freq=10000,timeout=500000))
コンストラクタは識別子を確認し、STOPで既存セッションを明示的に停止する。
    chip.write_registers([(register,value), ...])  # 5書き込みずつ送信
    chip.pure_fm(channel=0)                       # FM0..2の単純音色
    chip.ssg_bass()                               # SSG低音和音の準備、音量0
    chip.enqueue([(delta_ms,register,value), ...]) # 2イベントずつ補充
    chip.seal()                                  # この演奏の最終イベント登録済み
    chip.play()                                  # 補充済みキューを開始
    chip.keepalive()                             # 約1秒以内に更新
    chip.gates(dac=True,line=True)                # 出力のみ変更、演奏時刻は進む
    chip.status()                                # seq,result,flags,queued の4バイト
    chip.stop()                                  # キュー破棄・全音停止・障害復帰
    chip.stream(events,prefill=32)                # ジェネレータを補充しながら再生
stream()は事前に設定した音色を保ち、開始前と終了/例外時にSTOPする。
有限/無限ジェネレータを扱えるが、生成処理が1秒以上停止すると通信期限で消音する。
enqueue()/write_registers()は送信フレーム単位で検証する。後続フレームが不正だった場合に
既に受理したフレームまで巻き戻す機能はない。
I2C失敗時は要求を自動再送しない。リースで停止させ、明示的stop()で同期を取り直す。
stream()中の音色変更やミュートを別スレッド/別ホストから割り込ませない。

実装上の限界
------------
- 1回の音声処理は625入力→540出力フレーム、約11.25ms。
  YMレジスタ書き込みは1回に1個。時刻は前の予定時刻を基準とし、積算遅延を避けるが、
  同時刻の複数書き込みは順番に処理される。100ms超の遅れはFAULTで停止する。
  密なVGMデータの完全再生やサンプル単位の同期を保証する版ではない。
- イベント間隔0..65535ms。長い待ちは副作用のない許可レジスタへの同値書き込みで分割する。
  未SEALでキューが空になると補充を待ち、その間の発音状態を保持する。
- SEAL後の正常終了は全6声のキー/音量を順次オフにし、135ms排出後に出力を閉じる。
  STOP/リース/障害停止はゲートを即座に閉じる。PLAY前には約135msの無音準備がある。
- 変換利得は全FM入力範囲に対応する1/8、PCM出力上限±4096を維持する。
  診断専用の弱い音色(TL64、利得32)とは音色と利得の組み合わせが異なる。
  このため診断用音色をそのまま使った場合の音量は異なる。pure_fm()はTL0を使用する。
- CSM/CH3特殊モード、プリスケーラ、SSG I/Oポート、テスト/予約レジスタは禁止。
  音色はRAM上のみ。プリセット永続保存、MIDI音色/強弱/ピッチベンド/SysEx、
  汎用BINファイルの直接入力は未実装。
- 基本サンプルと3分間再生の音質は実機確認済み。GPIO/割り込み/USB/電源の
  最悪時の時間特性、物理USB切断、24時間運転は未確認。

検証と再現
----------
詳細はvalidation.json、protocol-v1.md、firmware-lock.jsonを参照。
CPythonの自動テスト、実MicroPython WASMでのホスト結合、Unix v1.29の割り当て測定、
公式mpy-cross v1.29 Armコンパイルを区別して記録する。ハードウェアはモデルで代用。
元の診断ヘルパー5ファイルはruntime-lock.jsonで固定し、変更せず取り込む。
ソースツリーでは次を実行する。
    python3 -m unittest discover -s hardware/ym2203-single-board/firmware/tests -v
    ./scripts/use-node.sh node hardware/ym2203-single-board/firmware/verify-micropython.mjs
    MICROPYPATH=hardware/ym2203-single-board/firmware/src <Unix MicroPython> hardware/ym2203-single-board/firmware/verify-heap.py
    python3 hardware/ym2203-single-board/firmware/build.py <新規出力ZIP>
配布物は.pyソース。Arm Viper部分はPicoへのimport時にコンパイルされる。
上流MicroPythonおよび本プロジェクトのMITライセンスを保持する。
