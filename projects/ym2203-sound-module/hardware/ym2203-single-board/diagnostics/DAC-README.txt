YM2203C single board Rev C - PCM5102A DAC単独診断 v1
2026-11-11

目的と前提
----------
SSGの次に、Pico → I2S → PCM5102A → ミキサー → LINE出力を確認します。
確認済みの公式Pico 2 MicroPython v1.29.0をそのまま使います。UF2の再書き込みや
回路・部品・GPIOの変更は不要です。YM2203Cも搭載したままです。
YM2203Cは診断中ずっとハードウェアリセット状態です。FM受信・PCM変換は次の段階です。
PC上のモデル検証に加え、ユーザー実機で3回の左右発音とDAC/LINE両方のミュートが確認されました。
次段階はFM-CAPTURE-README.txtの無音FM受信診断です。

同梱ファイル
------------
rev_c_bus_check.py: 実機で確認済みのものと同一。安全なGPIO初期化・終了に使います。
rev_c_dac_check.py: 今回実行する診断。音が出ます。
README.txt: 本手順。
LICENSE: 診断コードのMITライセンス。
host-tests.txt / validation.json: PC上の検証結果とSHA-256。

1. 接続を確認する
-----------------
・JPOWERは今のモバイルバッテリーから給電します。
・PicoのUSBはThonnyを使うPCへ接続します。
・AMS-22は別のモバイルバッテリーでDC 5V端子から給電し、PCとのUSBは外します。
・Rev C JLINE → AMS-22の3.5mm LINE INへ、3極ステレオTRSケーブルで接続します。
・ヘッドホンはAMS-22へ接続します。Rev Cへ直接接続しません。
・AMS-22はDIRECT MONITOR=ON、LOOPBACK=OFF。MIC/GUITARは未接続、GAIN最小。
・外部ホストI2Cは未接続のままです。
・Rev CのボリュームとAMS-22のOUTPUTは低い位置から始めます。

配線変更で電源を入れ直す場合は、音量を最小にしてPico USB → JPOWERの順で外し、
JPOWER → Pico USBの順で接続します。ICやモジュールの抜き差しは全電源OFFで行います。

2. Thonnyで実行する
------------------
1) ZIPをPC上で展開します。
2) Thonnyの接続先を、前回と同じPicoのMicroPythonにします。
3) rev_c_bus_check.pyをPicoの一番上の階層へ同名で保存します。
   前回のファイルが残っていればそのまま使えます。PC側だけではimportできません。
4) PC上のrev_c_dac_check.pyをThonnyで開き、F5で手動実行します。
   main.py / boot.pyにはせず、自動実行させません。
5) 約5秒後、1kHzの音が始まります。両方の音量ノブを低い位置から少しずつ上げます。
   初回に間に合わなければ、正常終了後、音量を低く保って再実行できます。

3. 期待する動作
---------------
TONE 1    1kHzの音を2秒
DAC MUTE  約1秒、テスト音が聞こえない（DACのXSMTによる消音）
TONE 2    同じ音を2秒
LINE MUTE 約1秒、テスト音が聞こえない（アナログスイッチによる消音）
TONE 3    同じ音を2秒、その後終了・消音

内部バッファの排出と安定待ちのため、各無音区間は表示の1秒より少し長くなります。
音の先頭と末尾を10msでフェードさせています。背景の小さなサー音は今回の判定から分け、
ミュート区間で1kHzのテスト音が消えるかを確認してください。
モノラル音を左右へ複製する回路なので、3回とも両耳から聞こえるのが期待値です。
SSG診断より小さな音になる可能性があります。音量差そのものは不合格ではありません。

正常終了時:
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 I2S=stopped
  DONE: samples sent; report 3 tones, both L/R, and both mute intervals.

DONEはデータ送信の終了で、実際に音が出たことを自動判定していません。
「3回とも聞こえたか」「左右両方から聞こえたか」「2つのミュートで音が消えたか」
「歪みや大きなポップ音の有無」と、Thonnyの出力全文を報告してください。

停止とエラー
------------
Ctrl+Cで中断できます。終了・例外・中断時はLINE/ARM/DACを下げてからI2Sを停止します。
例外が出た場合は全文を保存し、繰り返し実行する前に確認してください。
machine.I2Sがない場合も、勝手にUF2を入れ替えずMicroPythonの版を報告してください。
停止操作が効かない場合や終了時の例外が出た場合は、まず音量を下げ、Pico USBを外して
最後にJPOWERを外します。

実装の範囲とPC上の検証
----------------------
・GP10=DATA、GP11=BCLK、GP12=LRCK。既に承認された割り当てを維持。
・48kHz、16bitステレオ、BCLK公称1.536MHz。PCM5102AのSCKなしPLL条件に対応。
・ピーク4096/32768（約-18dBFS）の1kHz正弦波を左DACだけへ送信。右DACは未接続のため0。
・GP22=ARMだけを上げ、GP9=RESET_RELEASEは0のまま。YMのバス操作・FMキーオンはしません。
・フルスケール、I2Cスレーブ、USB-MIDI、YM FMデータ受信、音量上限は未検証。
・PC上のモデルは波形・音量・左右順・フェード・ミュート・途中停止・失敗時の消音を確認。
  実際のクロック精度、DMA連続動作、音質・音量・回路のミュートは実機で確認が必要です。

検証コマンド:
python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
無音バス8項目、SSG6項目、今回のDAC8項目、合計22項目。

一次資料:
https://docs.micropython.org/en/v1.29.0/library/machine.I2S.html
https://raw.githubusercontent.com/micropython/micropython/v1.29.0/ports/rp2/machine_i2s.c
https://www.ti.com/lit/ds/symlink/pcm5102a.pdf
https://zoomcorp.com/manuals/ams-22-ja/
