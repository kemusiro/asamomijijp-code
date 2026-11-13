YM2203C single board Rev C - 外部I2CによるSSG発音・消音診断 v1.2（切り分け版）
2026-11-11

v1.2の実機結果
--------------
通常6音と約1秒で自動消音する7音目を左右で確認し、歪み/音切れなし、終了時消音まで合格しました。
HOST PASSとRev CのSAFE/DONE、命令108、lease_expirations=1、受信390/送信700、stale_flushes=0。
HOSTの転送バイト数も390/700で一致しました。
次のFM連続変換とI2C制御の同時動作診断はI2C-FM-README.txtを参照してください。
以下のv1/v1.1の失敗は履歴です。ハードウェアI2Cで合格しましたが、元のエラー原因の確定ではありません。

目的と前提
----------
無音I2Cテストは実機合格です。10kHz・アドレス0x42、22パターン、繰り返しSTART、
読み取り専用保護とアドレス周回、HOST PASS、Rev CのSAFE/DONEと無音を確認しました。
受信755/送信730/ignored1/stale_flushes0は想定どおりです。
今回は外部コマンドをSSGの発音・消音へ接続します。
v1は実機でHOSTが6音目へ進んだ後、Rev CがI2C TX abort 0x5000でSAFE停止しました。
このv1試験は完走せず、7音目の期限消音にも到達しませんでした。
0x5000はターゲット送信中のSDA不一致/調停喪失のビットで、メモリ不足や通常の終了通知ではありません。
v1.1はRP2350データシート12.2.10.1.2に合わせ、データをFIFOに入れてからRD_REQを解除します。
準備中にPython処理が止まっても、応答データを用意する前に要求を解除しない順です。
ただし、実機の波形は取得しておらず、0x5000の発生原因がこの順序だけだったとは断定していません。
異常を無視する変更はしていません。0x5000は引き続き失敗・消音停止になります。
v1.1の再試験では6音分のSTOP応答を終え、7音目の開始応答がb'%\xff\xff\xff'となってHOSTが停止しました。
このv1.1試験ではRev CがREADYのまま待機し、完走・7音目の期限消音に到達しませんでした。
v1.2では操作側をSoftI2CからハードウェアI2C0へ切り替え、同じGP0/1・10kHzで比較します。
ターゲットの通信処理v1.1、コマンド、音色、通知期限は変更しません。
この切り替え後のv1.2は上記のとおり実機合格しました。原因はホスト/ターゲット/電気的要因のいずれとも未確定です。
異常時の情報を増やすため、HOSTに転送数と最終応答、Rev Cに停止前の制御状態を記録します。
FMとDACは使用せず、SSGのA/B/Cを固定音程・固定音量で1音ずつ鳴らします。
I2Cターゲットのポーリング処理とSSGのバス操作は確認済みファイルをそのまま使います。

1. 配線・音声の準備
------------------
I2C配線・GPIO・給電は前回と同じです。
  Rev C JHOST 1 GND → 操作側Pico GND（物理3番など）
  Rev C JHOST 2 SDA → 操作側GP0（物理1番）
  Rev C JHOST 3 SCL → 操作側GP1（物理2番）
  JHOST 4もGNDですが、3本配線では未接続でよい。
信号は3.3V、R1/R2各4.7kΩプルアップを使用。電源線同士を接続しません。
結線を変える場合は両方を電源OFFにし、テスト中は両方へ給電します。
Rev Cは従来のJPOWER給電とPico USB、操作側は自分のUSBで給電します。

今回は音を出します。両方のボリュームを低めにしてください。
  Rev C JLINE → AMS-22 3.5mm LINE IN
  AMS-22 → ヘッドホン、DIRECT MONITOR=ON、LOOPBACK=OFF
AMS-22は以前と同様、別バッテリーのDC 5V給電でPCとのUSB接続を外します。
MIC/GUITARは未接続、GAIN最小です。従来と同じPico 2 MicroPythonで実行し、UF2は書き直しません。

2. ファイルの保存先
------------------
ZIPのtarget/から、Rev C側Picoの最上位に保存する4ファイル:
  rev_c_bus_check.py
  rev_c_ssg_check.py
  rev_c_i2c_target_check.py
  rev_c_i2c_ssg_target.py
ZIPのhost/から、操作側Picoの最上位に保存する2ファイル:
  rev_c_i2c_host_check.py
  rev_c_i2c_ssg_host.py
v1.1からの変更は2つのSSG起動ファイルです。残り4ファイルはv1.1と同一です。
今回は全ファイルを上書きし、両方でCtrl+Dを押してください。
旧rev_c_i2c_target_check.pyが残っている場合は、v1.1を要求するエラーで停止します。
ファイルはPC上に置くだけでなく、指定したPico側へ保存します。main.py / boot.pyにはしません。
host用プログラムは必ず操作側で実行します。Rev CのGP0/1はYMのデータ線です。

前回の2つのThonnyで、別々のPicoポートへ接続します。
通常起動した方をRev C、独立設定で起動した方を操作側にすると分かりやすくなります。
macOSで2つ目を起動するコマンド（設定チェックボックスは使いません）:
  mkdir -p "$HOME/Library/Thonny-I2C-Host/runtime"
  env THONNY_USER_DIR="$HOME/Library/Thonny-I2C-Host" \
      XDG_RUNTIME_DIR="$HOME/Library/Thonny-I2C-Host/runtime" \
      /Applications/Thonny.app/Contents/MacOS/thonny
このターミナルは起動中そのまま開いておきます。

3. 実行順と聞こえ方
------------------
1) 両方のシェルでCtrl+D。
2) Rev C側でrev_c_i2c_ssg_target.pyを開いてF5。
   冒頭は YM2203 Rev C / I2C SSG target check v1.2。
   バス検査6項目のPASS後、transport=1.1を含むREADYが出ます。通信部が1.1なのは正常です。
   ここではまだ無音です。
3) READY確認後、操作側でrev_c_i2c_ssg_host.pyを開いてF5。
   冒頭は YM2203 Rev C / I2C SSG host check v1.2 / OTHER Pico only。
   HARDWARE I2C0 と、BUS: I2C(0, freq=..., scl=1, sda=0, timeout=500000)を確認します。
4) 識別情報とSTOPの実行確認後、同じ状態を64回読み取り、消音状態のままKEEPを32回検査します。
   PASS: 64 stable status reads + 32 acknowledged KEEP commands while muted
   が出たら、5秒待って次の音が始まります。この事前検査で失敗した場合は音を出しません。

  A 約440Hz・約2秒 → 無音1秒
  B 約440Hz・約2秒 → 無音1秒
  C 約440Hz・約2秒 → 無音1秒
  上記を2巡（計6回）。各チャンネルの音程は同じです。
  最後にAをもう1回鳴らし、継続通知を止めます。
  7回目は約1秒で自動的に止まり、その後は無音になります。

通常6回の発音中は約200msごとにKEEPを送ります。音は再発音させずに継続します。
各音の終了はSTOPコマンドでSSGを止め、応答で実行を確認します。
7回目はSTOPを送る前に、通知が来ない状態で自動消音したことをステータスでも確認します。
配線や給電は抜かず、ソフトウェア上で通知だけを止める試験です。
全体は5秒待ちを含めて約25～30秒です。左右へ同じモノラル音を出します。

4. ログと報告
-------------
操作側の正常な末尾:
  PASS: lease expired and source muted without a STOP command
  HOST PASS: SSG commands, acknowledged stops and lease mute verified.
  HOST I2C STATS: reads=... read_bytes=... writes=... write_bytes=... last_read=...
  HOST SAFE: GP0/GP1=input; wait for target lease mute if interrupted
Rev C側:
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 I2C=disabled
  TARGET: commands=... lease_expirations=1 received=... sent=... stale_flushes=...
  LAST CONTROL STATE (before reset): ...
  DONE: report six SSG tones, one short watchdog tone, final silence and HOST PASS.

・A/B/Cの通常6音が左右から聞こえ、STOPごとに音が消えるか。
・最後の7音目が約1秒で止まり、その後と終了後にテスト音が消えるか。
・歪み、途中の音切れ、大きなクリック、不意な音量差がないか。
・操作側とRev C側のログ全文。HOST PASS、SAFE、DONEまで含めます。
受信数は継続通知の回数により変わるため、前回の755/730とは比較しません。
背景の小さなサー音は、テスト音の消音判定とは分けてください。
HOST PASSだけで実際の音を判定せず、Rev CのDONEと耳での確認も必要です。
HOST I2C STATSは成功・例外の両方で表示します。read_bytesは実際に返ったバイト数で、
その値が正しいことを示すものではありません。last_readには異常値もそのまま残します。
LAST CONTROL STATEも例外/Ctrl+C時に表示します。これは停止前の診断状態で、SAFE後に発音中という意味ではありません。
HOSTで失敗してRev CがREADYのままの場合は、Rev C側もCtrl+Cで停止し、この追加ログまで保存してください。

5. 停止と制約
-------------
操作側のCtrl+C/例外でKEEPが止まった場合も、約1秒後にソフトウェアで消音します。
Rev C側のCtrl+C/例外では、まずLINEミュートとARM=0、その後GC・I2C停止・ピン解放を行います。
この自動消音はターゲットのPython処理が動いている範囲で有効です。
Pico自体がハングしたときも独立して動くハードウェア保護ではありません。
音が残った場合はRev C側もCtrl+Cで止め、操作できなければ音量を下げ、
Pico USB → JPOWERの順で電源を外してください。
エラー時は両方のログを保存します。再試験は両方Ctrl+D → Rev C READY → 操作側実行です。
READYの待ち時間は診断用に最大5分です。1秒の通信期限も診断用で、楽曲長の上限ではありません。
FM、I2S、DAC、予約演奏、400kHz、USB-MIDIは今回扱いません。

6. 診断専用コマンド
------------------
7bitアドレス0x42、操作側ハードウェアI2C0・10kHz。識別情報は0x00から8バイトのRCSSG01!です。
scanは使わず、非空の書き込みと読み取りで通信します。RP2のscan用ゼロ長書き込みにはSoftI2Cへ戻る経路があるためです。
前回の無音RAM診断とは識別情報を変え、取り違えたhostでは発音しません。
正式な音源APIではなく、固定音による組立診断です。
書き込みは必ず [0x20, opcode] の2バイトとSTOPで1コマンドです。
  0 STOP: 全SSG音量0、全トーン/ノイズ停止、LINEミュート。
  1/2/3: SSG A/B/Cを1つだけ約440Hz、固定レベル10で発音。
  4 KEEP: 有効な発音の通信期限を更新。消音済みの音を再開しない。
  5 FINISH: 消音して診断終了。
コマンド全体を受信し、バスがアイドルになってから実行します。
ポインタだけの不完全な書き込みでは発音せず、未対応の値/長すぎるフレームは失敗終了します。
読み戻せる0x10から4バイト:
  [実行確認カウンター（8bit周回）, 最後のopcode, 発音中チャンネル0～3, 期限消音フラグ0/1]
カウンターはレジスタの読み戻しを含めた実行完了後に更新します。
通知期限超過時は音量0とLINEミュートを行い、チャンネル0/期限フラグ1にします。
期限超過後にKEEPだけを送っても再発音しません。

7. PC上の検証
-------------
ホスト104項目（SSG制御14項目、I2C通信11項目を含む）。実際のhostとターゲットのポーリングを接続したモデルで
通常6回と通知期限消音、コマンド境界、読み戻し失敗、通知期限の周回、不正データ、
古い/不正な実行確認応答、例外/メモリ不足時にGCより先に消音することを確認しました。
MicroPython WASM v1.28.0でも実際のhost/制御処理を、模擬バス・時計・音源で検証します。
応答の準備中に20ms停止させてもRD_REQを解除しないことを確認する回帰テストは、v1で失敗・v1.1で成功しました。
MicroPython WASMでもGCを挟んで送信FIFO書き込み→RD_REQ解除の順序を検証します。
旧版混在の検出と、発音中に0x5000を注入した際の消音停止も確認します。
ハードウェアI2C0のピン/速度/タイムアウト指定とscanしない経路、初期状態の検査、
報告されたb'%\xff\xff\xff'（およびACKが変化しない破損応答）を成功扱いせず発音を再送しないことを検証します。
公式MicroPython v1.29.0 mpy-crossで変更した2ファイルのArm向けコンパイルを確認します。
実機でのI2C応答タイミング、実際の音、1秒消音の実時間は今回の試験で確認します。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
検証ログとSHA-256はZIP内の各ログ・validation.jsonに含めます。

一次資料:
https://datasheets.raspberrypi.com/rp2350/rp2350-datasheet.pdf （12.2.10.1.2、手順5～7）
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/i2c.h
https://raw.githubusercontent.com/micropython/micropython/v1.29.0/ports/rp2/machine_i2c.c
