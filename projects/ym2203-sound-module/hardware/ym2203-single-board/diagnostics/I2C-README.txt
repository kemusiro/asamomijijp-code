YM2203C single board Rev C - 外部I2C・無音通信診断 v1
2026-11-11

前提と目的
----------
6音・3分間の連続運転v1.1は、実機で左右正常・音切れ/歪みなし・終了時消音、SAFE/DONEまで確認済みです。
16000ブロック/180000ms、最大変換1119us、期限超過0、空きメモリは前後406960バイトで差0でした。
次は、もう1台のPico/Pico 2からRev CのJHOSTへI2C接続し、識別情報とRAMの読み書きを検査します。
初版v1のI2C診断は実機合格です。HOST PASS・SAFE/DONEと無音、受信755/送信730/ignored1/stale_flushes0を確認しました。
通信処理v1.1ではSSG試験中の送信アボートを受け、データをFIFOに入れてからRD_REQを解除する順序へ変更しました。
最新版の実機での再確認はこれからです。詳細はI2C-SSG-README.txtを参照してください。
YM2203は常にリセット、DAC/LINEはミュートのままで、音は出しません。
次の外部I2CによるSSG発音・消音診断はI2C-SSG-README.txtを参照してください。
発音制御・音声との同時動作・USB-MIDIは含みません。

1. 結線
-------
両方の電源を切って結線します。テスト中は両方を給電した状態で使用します。
GPIOは以前承認済みのままです。JHOSTのピン番号は基板のシルク/回路図で確認してください。

Rev C JHOST      操作側Pico/Pico 2
1 GND       ---> GND（物理3番など）
2 SDA       ---> GP0（物理1番）
3 SCL       ---> GP1（物理2番）
4 GND            1番と同じGND。3本配線では未接続でよい。

JHOSTは1=GND、2=SDA、3=SCL、4=GNDです。VCC端子はありません。
操作側の3V3/VBUS/VSYSはJHOSTやRev C電源へ接続しません。信号は3.3Vです。
短いジャンパー線を使います。SDA/SCLを取り違えないでください。
Rev CのR1/R2（各4.7kΩ、SDA/SCLから基板3.3Vへのプルアップ）が実装済みであることを確認します。
未実装の場合は給電を切り、R1/R2を実装するか、同じ位置へ各4.7kΩを外付けします。
両方へ重複して追加する必要はありません。内部の弱いプルアップだけを前提にしません。
Rev Cは従来のJPOWER給電とPico USB、操作側は自分のUSBで給電します。
AMS-22の接続は前回のままでも構いませんが、今回の判定は無音です。
結線/取り外しは両方の電源を切って行い、片側を無給電のまま放置しません。

2. ファイルの保存先
------------------
ZIPのtarget/内から、Rev Cに載っているPico 2へ保存する2ファイル:
  rev_c_bus_check.py             以前と同一
  rev_c_i2c_target_check.py       今回追加
ZIPのhost/内から、操作側のもう1台のPico/Pico 2へ保存する1ファイル:
  rev_c_i2c_host_check.py         今回追加
それぞれPicoの最上位に保存します。main.py / boot.pyにしません。
host用ファイルは必ず操作側で実行します。Rev C側のGP0/1はYMデータ線です。
Rev C側のMicroPython UF2を書き直す必要はありません。
操作側には、そのPicoの機種に合った通常版MicroPythonが必要です。

3. Thonnyを2台へ同時接続する
---------------------------
2つの独立したThonnyを使い、それぞれ別のUSBシリアルポートを選びます。
同じポートへ両方を接続しないでください。両方でMicroPythonの >>> を確認します。
Macでは、設定画面の複数起動チェックボックスを操作すると無応答になるとの報告がありました。
設定画面を使わず、2つ目の設定・プロセス間通信先を分けて起動できます。
通常起動したThonnyをRev C側に使い、ターミナルで次を実行してください。
  mkdir -p "$HOME/Library/Thonny-I2C-Host/runtime"
  env THONNY_USER_DIR="$HOME/Library/Thonny-I2C-Host" \
      XDG_RUNTIME_DIR="$HOME/Library/Thonny-I2C-Host/runtime" \
      /Applications/Thonny.app/Contents/MacOS/thonny
設定と通信先が分離することは、このMacのThonny同梱コードで確認済みです。
新しい方は設定が初期状態なので、必要に応じて初回設定を行ってください。
起動中はこのターミナルを開いたままにします。
片方をRev C、もう片方を操作側へ接続します。起動時の自動接続先も確認してください。
実行中のRev Cを切断して接続先を切り替える方法は使いません。

4. 実行順
---------
1) 両方のシェルでCtrl+Dを押し、以前の診断が停止している状態にします。
2) Rev C側でrev_c_i2c_target_check.pyを開き、F5。
   YM2203 Rev C / silent I2C target check v1.1
   READY: address=0x42 SDA=GP20 SCL=GP21; start host within 5 minutes.
   と表示されれば、そのまま待機させます。ここから最大5分待ちます。
3) READY確認後、操作側でrev_c_i2c_host_check.pyを開き、F5。
   最初の周波数は10kHz、7bitアドレス0x42です。通常は数秒で終了します。
4) 操作側で以下を確認します。
   SCAN: ['0x42']
   PASS: signature b'RCI2C01!'
   PASS: 22 patterns x 32 bytes; STOP and repeated-start reads
   PASS: read-only identity and address wrap
   HOST PASS: silent I2C link complete; finish command sent.
   HOST SAFE: GP0/GP1=input
5) Rev C側も終了し、以下を表示します。
   SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 I2C=disabled
   TARGET: received=... sent=... ignored=... stale_flushes=...
   DONE: host requested finish; confirm HOST PASS and no sound on both logs.

両方のログ全文と、テスト音が出なかったことを報告してください。
ターゲット側のDONEだけでは、読み戻し一致を判断しません。HOST PASSも必要です。
操作側で失敗した場合はRev C側もCtrl+Cで止め、両方のログを保存します。
再試験は両方Ctrl+D → Rev C側READY → 操作側実行の順です。
5分のタイムアウトも同様にやり直します。

5. 診断プロトコルと範囲
-----------------------
0x42はこの診断だけのアドレスです。正式な音源API/WebLab仮想音源APIとは別です。
各書き込みの先頭1バイトはRAMアドレスです。その後のデータと読み取りはポインタを自動加算します。
ポインタは0xFFの次に0x00へ戻ります。読み取り前のポインタ設定はSTOPあり/繰り返しSTARTの両方を検査します。
  0x00～07: 識別情報RCI2C01!（読み取り専用）
  0x20～3F: 診断用RAM32バイト（読み書き）
  0x7Fへ0xA5を書き込み: ホスト検査成功後の終了要求。バスがアイドルになってから終了します。
その他は0を読み返し、書き込みは無視します。YMのレジスタやGPIOには転送しません。
読み取り専用の検査でignoredは通常1となります。

ターゲットはRP2350 I2C0ハードウェアを使い、受信・読み取り要求をMicroPythonからポーリングします。
RX FIFO満杯時と読み取り応答待ちはハードウェアのクロックストレッチを使います。
操作側SoftI2Cはストレッチ待ち500msです。対象側の実行中にログ表示や明示的GCは行いません。
この方法は低速・無音の組立診断用です。400kHz、FM連続変換との同時動作、予約演奏は未検証です。
終了・例外・Ctrl+C時にI2Cを無効化し、GP20/21を入力へ戻します。
I2Cの応答があっても、無音であることだけではFM/SSGへの制御を確認したことにはなりません。

6. PC上の検証と出典
-------------------
ホスト89項目（今回I2C10項目）: 両スクリプトを接続したレジスタモデル、22パターン、FIFO例外、
繰り返しSTART、終了時のACK/STOP待ち、タイムアウト、読み取り専用保護、割り込み時の無音/解放を検証。
公式MicroPython v1.29.0 mpy-crossで両スクリプトをArm向けにコンパイル。
MicroPython WASM v1.28.0でRAMプロトコルと実際のホストの全パターンを検証。
Raspberry Pi pico-sdk 2.2.0のRP2350定義で22個のレジスタアドレスとステータスビットを照合しました。
モデルやWASMは実機のACK、クロックストレッチ、立ち上がり時間を検証しません。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
validation.jsonと各検証ログを同梱しています。SDKソース、コンパイラー、UF2は同梱しません。

一次資料:
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/i2c.h
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/addressmap.h
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2_common/hardware_i2c/i2c.c
https://docs.micropython.org/en/v1.29.0/library/machine.I2C.html
