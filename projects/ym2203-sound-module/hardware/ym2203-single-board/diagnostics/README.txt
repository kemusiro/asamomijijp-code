YM2203C single board Rev C - 無音バス診断 v1
2026-11-11 / 実機での最初の読み書き確認用

対象
----
発注済みYM2203C専用1枚基板 Rev CとRaspberry Pi Pico 2。
実基板のGP0-7を直接操作するプログラムです。WebLabで実行するものではありません。
I2Cホスト、USB-MIDI、FM取り込み、I2S音声出力の実装は含みません。
GPIOと回路・製造データは変更しません。

測定の前提
----------
5V/3.3V電源、ARM=L時のリセット・バッファ無効、4MHzクロック、
VREFと無信号ミキサーの約2.5V、ライン出力DC約0Vを確認済みであること。
テスト中は外部5Vを維持します。ホストI2C・AMS-22は接続しません。

1. MicroPythonを準備する
----------------------
1) JPOWERとPico USBを外し、全電源をOFFにします。
2) Pico 2を主基板のソケットから外します。
3) 以前使ったPicoに保存データがある場合は、書き込み前にバックアップします。
4) Pico 2のBOOTSELを押しながら、データ通信対応USBケーブルでPCへ接続します。
5) 公式ページの通常版（Arm用）MicroPython v1.29.0 UF2を、表示されたUSBドライブへコピーします。
   Pico 2 W用や初代Pico用のファイルは使いません。

   公式ページ: https://micropython.org/download/RPI_PICO2/
   固定版UF2: https://micropython.org/resources/firmware/RPI_PICO2-20260824-v1.29.0.uf2
   導入説明: https://docs.micropython.org/en/v1.29.0/rp2/tutorial/intro.html

6) ThonnyからPicoのMicroPythonへ接続し、シェルに >>> が出ることを確認します。
   Thonny: https://thonny.org/
7) Pico側にboot.pyやmain.pyがある場合は内容を確認します。GPIOを操作する古い
   プログラムがあれば、バックアップして自動実行されない名前へ変更します。
   診断ファイルをboot.py/main.pyという名前で保存しないでください。
8) 確認後にPico USBを外します。

2. 主基板へ戻す
--------------
1) 主基板の電源OFFを確認し、Picoの向きと端子列を合わせてソケットへ戻します。
2) 主電源JPOWERのUSB-Cを先に接続します。
3) TP1約5V、TP2約3.3V、TP4ほぼ0Vを再確認します。
4) その後にPicoのUSBをPCへ接続します。
   JPOWERのUSB-Cは電源入力、PicoのUSBは診断用シリアル接続です。
5) ホストI2C・AMS-22は接続せず、ボリュームは最小にします。

3. 無音診断を実行する
--------------------
1) Thonnyの接続先をPicoのMicroPythonにします。
2) PC上のrev_c_bus_check.pyを開き、「現在のスクリプトを実行」（F5）します。
   最初はPicoへ自動起動ファイルとして保存せず、手動で実行します。
3) シェルの表示を確認します。正常時の例:

   YM2203 Rev C / silent bus check v1
   Keep host I2C and AMS-22 disconnected. External 5V must be on.
   STATUS after reset: 0x00
   PASS reg=0x00 patterns=20
   PASS reg=0x02 patterns=20
   PASS reg=0x04 patterns=20
   PASS reg=0x01 patterns=4
   PASS reg=0x03 patterns=4
   PASS reg=0x05 patterns=4
   SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0
   PASS: silent bus read/write check complete; YM is held in reset.

4) STATUSだけでは音源の存在を判定しません。6行のPASS reg=と最後のPASSまで
   到達したことを確認してください。最後のPASSがなければ合格ではありません。
5) 終了後はARMとRESET_RELEASEをLへ戻すので、TP4・TP5は再びほぼ0Vになります。
6) 出力全文を保存・報告します。失敗時は発音試験へ進まず、表示を確認します。

この診断の動作
--------------
・LINE_ALLOWとDAC_ALLOWは一度もHにしません。SSG音量も常に0です。
・ARMを有効にしてハードウェアリセットを解除し、BUSYとタイマーフラグを確認します。
・SSGの読み書き可能な周波数レジスタを使い、全データビットと複数のアドレスを検査します。
・8bitレジスタは00/FF/55/AAと各bitの1/0パターン、4bitレジスタは0/F/5/Aを使います。
・各値を3回読み戻し、データ線の入出力切り替えを繰り返します。
・CS/WRを無効にしてからGPIOを入力へ戻し、RDを切り替え、待ってからYMを選択します。
・読み終わりはYMを非選択にしてバス解放を待ち、RDを戻してから次の書き込みを行います。
・BUSYが100ms以内に解除されなければ停止します。
・正常終了、Python例外、Ctrl+C時にはfinallyでミュート・リセット・バッファ無効へ戻します。
  停止操作が効かない場合は、Pico USBを外してからJPOWERを外してください。

代表的なエラー
--------------
BUSY timeout:
  読み取りがFF/80に張り付く場合もあります。主電源、YMリセット解除、
  U2の向き・はんだ、U5、A4のCS/RD/A0、データ線を確認します。
Readback mismatch:
  書き込み値と読み戻し値が異なります。reg/expected/actualをそのまま報告します。
  原因をIC一つに断定せず、A3/U2/A4/制御信号/はんだ/タイミングを切り分けます。
FAIL or interrupted:
  最後のPASSは出ません。続く例外表示を保存してください。
Use official Pico 2 MicroPython ...:
  ThonnyがPCのPythonや別のマイコンへ接続されていないか確認します。

確認できないこと
----------------
合格は基本的なレジスタ通信の確認です。FM/SSGの音、タイマー精度、IRQ、
FM SD/CLK/SH、PCM変換、DAC/I2S、USB-MIDI、I2Cスレーブは別途検証が必要です。
ソフトウェア上の待ち時間は初期値です。実際のバス競合・波形は実機測定が必要です。

検証と出典
----------
CPythonのGPIO/音源モデルで、全bit故障の検出、入出力切り替え、BUSYタイムアウト、
時刻の周回、Ctrl+C相当、初期化途中の失敗、無音維持、承認済みGPIOとの一致を検査します。
無音診断は2026-11-11に組立個体で全項目PASSの報告がありました。
発音診断の次の手順はSSG-README.txtを参照してください。
モデル試験は電気的検証を代替しません。

再検証コマンド（PC上、リポジトリのルートから）:
python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v

GPIO/回路の正本: ../rev-c/design.json、../rev-c/ym2203-single/netlist.xml
GPIO API: https://docs.micropython.org/en/v1.29.0/library/machine.Pin.html
YM2203資料: https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf
SSG周波数レジスタ00-05は読み書き可能。FMパラメーターの読み戻しには使えません。

診断コードはこのリポジトリのMITライセンスです。公式UF2は同梱していません。
