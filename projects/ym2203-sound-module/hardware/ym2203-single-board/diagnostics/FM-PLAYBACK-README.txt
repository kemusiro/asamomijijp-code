YM2203C single board Rev C - 受信FM波形のPCM再生診断 v1
2026-11-11

目的
----
実機で確認済みのFM受信とDAC出力を、PCM復号処理でつなぐ段階です。
最初は音声をミュートしたまま、キーオフ → キーオン → キーオフのFM波形を取得します。
次にYMをリセットして受信を停止し、取得波形から1周期を取り出してDACから3回再生します。
この診断はPC/WASMに加え、ユーザー実機で3回の左右発音・ミュートと歪みなしが確認されました。
実機ログは入力範囲-127～127、推定439.87Hz、再生440.37Hzでした。
次段階はFM-LIVE-README.txtの連続受信・変換診断です。

これは取得後の再生です。連続リアルタイム変換、FM音色変更への即時追従、FM+SSG同時演奏、
USB-MIDI、I2Cスレーブはまだ検証しません。再生中、YM2203Cはリセット状態です。

確認済みの実機結果
------------------
・バスの読み書き、SSG A/B/Cの6回の左右発音。
・DACの1kHz、3回の左右発音とDAC MUTE/LINE MUTE。
・FM受信のCLK約1.333MHz、SH約55.556kHz、24クロック/フレーム。
・キーオフは0x0600固定。キーオンは454フレーム中217種類。
・USB接続由来が疑われるチリチリ音は別途USB絶縁対策を予定。

1. 接続
-------
前回と同じ配線・給電を使います。GPIOや部品の変更はありません。
JPOWERは今のモバイルバッテリー、Pico USBはThonnyのPCへ接続します。
AMS-22は別バッテリーでDC 5V端子から給電し、PCとのUSBは外します。
JLINE → AMS-22の3.5mm LINE IN、ヘッドホン → AMS-22。
DIRECT MONITOR=ON、LOOPBACK=OFF、MIC/GUITAR未接続・GAIN最小。
外部ホストI2Cは未接続。最初はRev CとAMS-22の音量を低くします。
電源を入れ直す場合はJPOWER → Pico USB、外す場合はPico USB → JPOWERの順です。

2. ファイルを準備する
--------------------
ZIPを展開し、以下4ファイルをThonnyでPicoの最上位に保存してください。
・rev_c_bus_check.py（前回から変更なし）
・rev_c_fm_capture.py（今回同梱の版で上書き。再生診断用の任意引数を追加）
・rev_c_dac_check.py（前回から変更なし）
・rev_c_fm_playback.py（今回の実行対象）
main.py / boot.pyにはしません。Picoに古い同名モジュールが残っている場合は上書きします。
PC上のファイルを開いただけでは、Picoからimportできないことがあります。

3. 手動実行
-----------
1) ファイル保存後、ThonnyのシェルでCtrl+Dを押し、ソフトリセットします。
2) rev_c_fm_playback.pyを開き、F5で実行します。
3) 以前と同じ無音バス診断、KEY OFF 1 / KEY ON / KEY OFF 2の受信ログが表示されます。
4) PCM: input range=... source=... Hz playback=... Hz が表示されます。
   sourceは取得波形から推定した音程、playbackは今回の再生音程です。
5) 約5秒後に音が出ます。Rev CとAMS-22の音量を低い位置から少しずつ上げてください。
   FM REPLAY 1 → ミュート → FM REPLAY 2 → ミュート → FM REPLAY 3 → ミュート・終了。
   各音は約440Hz・約2秒、間隔は約1秒です。今回は前回の1kHzより低い音です。

期待する終端ログ:
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 capture/I2S=stopped
  DONE: captured FM replay sent. Report 3 tones, both L/R, and silent gaps.

3回とも左右から聞こえるか、間のミュートでテスト音が消えるか、歪みや大きなクリックが
ないかを確認し、ログ全文とともに報告してください。DONEは音の自動判定ではありません。
小さな背景のサー音は今回のテスト音と分けて評価します。
初回で音量調整が間に合わなければ、正常終了後Ctrl+Dで再実行できます。

4. 停止・エラー
---------------
Ctrl+Cで中断できます。例外時はログ全文を保存し、再試行の前に確認します。
波形・形式・音程の検査に失敗した場合はDACもLINEも有効にしません。
受信後はYMをリセットし、受信DMAを終了してからI2Sを開始します。
終了・例外時はLINEミュートとARM=0を先に行い、その後I2Sを止めます。
ソフトリセットまでは受信用PIOプログラムの登録が残るため、他の診断の前もCtrl+Dを使います。
操作に応答しない場合は音量を下げ、Pico USB → JPOWERの順で外してください。

5. 変換の範囲と制約
-------------------
・既存のPIO取得条件・ピン割り当ては変更していません。
・13ビットの下位10ビットをオフセットバイナリの仮数M、上位3ビットを指数Eとして、
  PCM = (M - 512) << (E - 1) とします。E=0は無効として中止します。
  YM3014のアナログ式にある半LSBのオフセットは除き、0x0600をPCMの0へ対応させます。
・無音時のPCMがほぼ0、発音時に正負があること、推定音程が400～480Hzであることを検査します。
・取得波形の正方向のゼロ交差から完全な1周期を取り、線形補間で48kHzの整数長1周期へ変換。
  例: 元の約440Hzを109サンプルに丸めると、48,000/109 = 約440.37Hzで再生します。
  音程には整数周期化の誤差があり、この診断の上記範囲では1%未満です。
・周期のDCを除き、ピーク4096/32768（約-18dBFS）へ音量を揃えます。
  元のFM振幅をそのまま再現する診断ではなく、過小音量を避けた経路確認です。
・開始と終了に短いフェードを付け、バッファ継ぎ目は完全周期でつなぎます。
・I2Sは前回確認済みと同じ48kHz・16bitステレオ。左DACだけへ送り、基板で左右へ複製します。
・I2S開始時は空いているSMを使います。停止済みの受信SMのGPIO入力を出力へ変えません。
・1周期の再生なので、アタック・リリース・変調の時間変化や演奏全体は再現しません。
  連続受信・レート変換・音色変更追従は次の段階です。

6. PC上の検証
-------------
python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs

42項目のホストテストに加え、実際のMicroPython WASMで配列作成・ユーザーログの復号・
波形の補間・音量上限・ステレオ配置を検証しています。
WASMではGPIO/PIO/DMAの実機動作を検証していません。版は同梱ログを参照してください。
validation.jsonはファイルのSHA-256、host-tests.txtとmicropython-compatibility.txtは検証結果です。
LICENSEは診断コードのMITライセンスです。

一次資料
--------
https://www.quarter-dev.info/archives/yamaha/YM3014B.pdf （p.3、仮数・指数とアナログ式）
https://docs.micropython.org/en/v1.29.0/library/machine.I2S.html
https://raw.githubusercontent.com/micropython/micropython/v1.29.0/ports/rp2/machine_i2s.c
メーカー資料・ファームウェア・他者の音楽データはZIPへ複製していません。
