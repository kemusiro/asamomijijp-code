YM2203C single board Rev C - SSG A/B/C発音診断 v1
2026-11-11

前提
----
同じ組立個体でrev_c_bus_check.pyが最後のPASSまで成功していること。
この無音診断は2026-11-11にユーザーの実機で全項目PASSと報告されました。
発音診断も2026-11-11にユーザー実機でA/B/C計6回とAMS-22経由の左右出力が確認されました。
LINE接続時の無音ノイズが報告されており、音質の確認は継続中です。
公式Pico 2 MicroPython v1.29.0をそのまま使います。UF2の再書き込みは不要です。
回路・部品・GPIOの変更はありません。

同梱ファイル
------------
rev_c_bus_check.py: 前回と同じ、無音診断および確認済みのバス操作。
rev_c_ssg_check.py: 今回実行する、音が出る診断。
validation.json: ファイルのSHA-256とPC上のテスト結果。
LICENSE: 診断コードのMITライセンス。

1. 音声ケーブルを接続する
------------------------
1) 基板RV1とAMS-22のOUTPUTを最小にします。
2) 基板のPico USB、JPOWERを外して電源をOFFにします。
3) JLINEからAMS-22の3.5mm LINE INへ、3極ステレオTRSケーブルで接続します。
   MIC/GUITARのコンボ端子へは接続しません。
4) AMS-22のヘッドフォン端子へヘッドフォンを接続します。
5) AMS-22をUSBでPCへ接続します。DIRECT MONITOR=ON、LOOPBACK=OFFにします。
6) 基板JPOWERを先に接続し、その後にPicoのUSBをPCへ接続します。
7) ホストI2Cは未接続のままです。

AMS-22のLINE INは固定ゲインです。MIC/GUITAR用のGAINノブでは調節できません。
音量は基板RV1とAMS-22のOUTPUTで調節します。
メーカー説明: https://zoomcorp.com/manuals/ams-22-ja/

2. 2ファイルを準備する
---------------------
1) Thonnyの接続先をPicoのMicroPythonにします。
2) rev_c_bus_check.pyを開き、Pico側の一番上の階層へ同名で保存します。
   今回の発音診断がこのモジュールを読み込みます。
   PC側に置いたままではimportできない場合があります。
3) 次にPC側のrev_c_ssg_check.pyを開きます。
   どちらもmain.py/boot.pyという名前にはしません。
4) F5でrev_c_ssg_check.pyを手動実行します。

3. 聴いて確認する
----------------
最初に無音診断をもう一度行います。ここで失敗すれば音声を有効にしません。
成功後に5秒待ち、その後次を2周します。

  SSG A: 約440Hzを2秒 → ミュート1秒
  SSG B: 約440Hzを2秒 → ミュート1秒
  SSG C: 約440Hzを2秒 → ミュート1秒

SSG固定音量は10/15を初期値としています。音量段階は線形の割合ではありません。
最初はノブを低い位置から少しずつ上げてください。シェルにA/B/Cが表示されるので、
対応する区間で両耳に同じ高さの音が出るか、3系統の音量が概ね揃うかを確認します。
2周目で、チャンネル間と終了後の無音も確認します。
同じモノラル信号を左右へ出す設計です。A/B/Cを左右へ振り分けてはいません。

シェルの表示例:
  YM2203 Rev C / SSG A-B-C check v1
  ...無音診断のSTATUSと6行のPASS reg=...
  BUS check passed. SSG tones start in 5 seconds.
  SSG A / round 1 of 2 / 440.14 Hz / 2 seconds
  MUTE / 1 second
  SSG B / round 1 of 2 / 440.14 Hz / 2 seconds
  ...C、2周目のA/B/C...
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0
  DONE: sequence sent. Report whether A, B and C were heard on both L/R.

DONEは命令の送信終了を示します。音声が実際に出たことを自動判定するものではありません。

4. 報告する内容
--------------
・A/B/Cそれぞれ聞こえたか。
・左右両方から聞こえたか。
・3系統の音量差、歪み、ノイズ、無音区間や終了後の音漏れ。
・シェルの表示全文。例外が出たら全文を保存し、繰り返し実行する前に確認します。

停止
----
Ctrl+Cで中断できます。終了・例外・Ctrl+Cでは音声許可をLにし、ARM=0でYMをリセットします。
停止操作が効かない場合は、Pico USBを外してからJPOWERを外します。
終了後の通常の電源OFFも、先に音量を下げてPico USBを外し、最後にJPOWERを外します。

動作と制約
----------
・データバス操作は、前回実機で成功したrev_c_bus_check.pyをそのまま使用します。
・レジスタの設定と読み戻しはラインをミュートした状態で行います。
・一度にSSGの1チャンネルだけを有効にし、ノイズとエンベロープ音量は使いません。
・設定の読み戻しが一致してからLINE_ALLOWをHにして発音します。
・DAC_ALLOWは常に0で、FMのキーオンやI2S出力は行いません。
・SSGはYMから直接アナログ出力されるため、PCM5102Aはこの音声経路に含まれません。
・4MHz、リセット後の標準分周で、tone period=142を使います。
  f = 4,000,000 / (4 * 16 * 142) = 約440.14Hz。
・2秒の発音・1秒の間隔は、この診断用の長さです。製品の演奏時間上限ではありません。
・この試験ではFM音源、PCM変換、DAC、I2Cスレーブ、USB-MIDIの動作は検証できません。

PC上の検証
----------
python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v

無音診断の8項目と発音診断の6項目を実行します。
6個の独立した発音区間、ミュート間隔、設定失敗時の発音禁止、
発音中のCtrl+C、音量制限、DACのミュート維持、最終的なリセット復帰をモデルで確認します。
実際の発音・音量・音質・アナログミュートはユーザー実機での確認が必要です。
