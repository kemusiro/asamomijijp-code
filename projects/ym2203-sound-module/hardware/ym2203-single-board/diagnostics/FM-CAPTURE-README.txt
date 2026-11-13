YM2203C single board Rev C - 無音FMデジタル出力受信診断 v1.1
2026-11-11

確認済みの経路と今回の目的
--------------------------
同じ組立個体で、バス診断、SSG A/B/C、PCM5102Aの1kHz・3回の左右発音、
DAC MUTE/LINE MUTEの消音がユーザー実機で確認されています。
次にYM2203CのFM出力SD/CLK/SHをPicoで同時取得します。
v1は実機でバス診断まで成功し、受信バッファ作成時のarray乗算で停止しました。
v1.1は乗算を使わない初期化へ修正し、ユーザー実機で受信確認が完了しました。
CLK約1.333MHz、SH約55.556kHz、24クロック/フレームで安定し、キーオフ時は0x0600固定、
キーオン時は454フレーム中217種類の値が確認されました。
次はFM-PLAYBACK-README.txtの受信波形再生診断です。
配線、GPIO、PIO命令、FM設定とミュートの条件はv1から変更していません。

今回、音は出ません。DAC_ALLOWとLINE_ALLOWを一度も上げません。
チップ内部でFMをキーオンしますが、まだDACへ流しません。
FMの音程・音色・音量、浮動小数点形式からPCMへの変換、連続再生は次の段階です。
13ビットのログは生のシリアルデータで、符号付きPCM値ではありません。

同梱物
------
rev_c_bus_check.py: 前回から変更なし。実機で確認済みのバス操作。
rev_c_fm_capture.py: 今回実行するプログラム。
README.txt: この手順。
LICENSE: 診断コードのMITライセンス。
host-tests.txt / validation.json: PC上のテスト、PIO命令検証、SHA-256。

接続
----
・Rev CのJPOWERは現在のモバイルバッテリーから給電します。
・PicoのUSBは、Thonnyを使うPCへ接続します。
・外部ホストI2Cは未接続のままにします。
・AMS-22は前回の別バッテリー給電・PCとのUSBなしのままで構いません。
・Rev CとAMS-22のボリュームは最小にします。LINEは接続したままで構いません。
・ICやモジュールの抜き差し、追加部品、GPIO・配線変更はありません。
・電源を入れ直す場合はJPOWER → Pico USBの順。外す場合はPico USB → JPOWERの順。

Thonnyでの実行
--------------
1) ZIPをPC上で展開します。
2) Thonnyの接続先を前回と同じPico 2のMicroPythonにします。
3) 前回の診断を停止し、シェルでCtrl+D（ソフトリセット）を実行します。
   今回はI2Sを使わずPIO0 SM0を使うため、他のPIO/I2Sプログラムと同時実行しません。
4) rev_c_bus_check.pyがPicoの最上位に保存されていることを確認します。
   同梱ファイルは前回と同じ内容です。
5) PC上のrev_c_fm_capture.pyをThonnyで開き、F5で手動実行します。
   main.py / boot.pyにはしません。
6) 最初に以前と同じ無音バス診断を実行します。
7) KEY OFF 1 → KEY ON → KEY OFF 2の3状態で、各8.192msの入力を取得・解析します。
   解析には数秒以上かかる場合があります。音が出ないのが正常です。
8) 成功・失敗を問わず、シェルの全文を報告してください。
   次のFM音声出力は、この実機ログを確認してから進めます。

ログと判定
----------
  YM2203 Rev C / silent FM capture v1.1
  ...無音診断のSTATUSと6行のPASS reg=...
  KEY OFF 1: CLK=... Hz SH=... Hz frames=... unique=...
    clocks/frame: {...}
    last13 LSB-first: ...
  KEY ON: ...
  KEY OFF 2: ...
  SAFE: ARM=0 RESET_RELEASE=0 LINE_ALLOW=0 DAC_ALLOW=0 capture=stopped
  PASS: FM clocks/frames/key response detected. Send the FULL log before PCM playback.

CLK/SHは16MHz公称のPIO時間軸から求めた概算で、校正済みの測定器による値ではありません。
clocks/frameはSHの立ち下がり間に検出したCLK立ち上がり数です。
last13は各SH立ち下がり直前の13ビットをLSB-firstで並べた16進数です。
初回の不完全なフレームは捨てます。無効ビットの値は判定に使いません。
uniqueは捕捉した13ビット値の種類数です。KEY ONで無音時より明確に増えることを確認します。
単にSDが動いているだけで、正しいPCM復号や正しいFM音を保証するものではありません。

エラーと停止
------------
Ctrl+Cで中断できます。終了時はLINEをミュート・ARM=0でYMをリセットしてから受信を停止します。
例外時はログ全文を保存してください。確認する前に音量を上げたり、別のFM再生を開始しません。
DMA timeout、PIO RX stalled、DMA bus errorは取得データの時刻が信頼できないため中止します。
波形・変化量の判定失敗は、ICの故障を確定するものではありません。実機の形式・位相も確認します。
終了時に例外が出た場合や操作できなくなった場合は、Pico USB → JPOWERの順で電源を外します。
PIOプログラムの登録はソフトリセットまで残ります。次の診断の前もCtrl+Dを実行してください。

実装範囲
--------
・公式Pico 2 MicroPython v1.29.0をそのまま使います。UF2の入れ替えは不要です。
・GP16/17/18を入力のまま、PIO0 SM0とDMA1チャンネルで同時取得します。
・2命令/スナップショット、PIO公称32MHz、標本化公称16MHz。8標本/32bitワード。
・64KiBのバッファに有限個を取得し、取得後のFIFOあふれを避けるためPIOは次のpullで待機します。
・PIO RXSTALLとDMAエラーフラグを確認します。DMA待機は500msで打ち切ります。
・FMチャンネル1、アルゴリズム7、スロット1のみキーオン。TL=48（約36dB減衰）。
  他のスロットTL=127。FNUM=1038、BLOCK=4で約440Hzを意図した設定です。
・FMプリスケーラー、テスト、汎用I/Oポートは変更せず、SSGは消音を維持します。
・今回は3つの短い取得であり、無制限の連続受信・USB/I2C同時実行を検証しません。

PC上の検証
----------
python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
現在はバス8項目、SSG6項目、DAC8項目、FM受信13項目、FM再生7項目、計42項目。
合成シリアル波形からの時刻・フレーム・ビット順の復元、信号欠落・不規則なフレーム・
SD固着、キーオン、書き込み制限、音声許可の維持、取得失敗・Ctrl+C時の停止を確認します。
公式v1.29.0のPIOアセンブラーで命令列と有限取得のカウンターも別途検証しています。
v1.1ではarray乗算を禁止した回帰テストを追加しました。
さらに実際のMicroPython WASMで、元のTypeErrorの再現、修正後の64KiB配列の作成、
32bit読み書きと解析を検証します。WASMはGPIO/PIO/DMAの実機検証を代替しません。
検証コマンド（リポジトリ内で実行）:
./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
配布ZIPにはこの互換性検証結果をmicropython-compatibility.txtとして含めます。
再生診断用にanalyze(..., keep_frames=True)で全フレームを返す任意引数を追加しています。
既定の受信診断の挙動、PIO命令、取得条件とGPIOは変更していません。
実機の電圧、入力タイミング、クロック精度、データ形式、音質の検証を代替しません。

一次資料（メーカーのPDFや実装はZIPへ複製していません）
-----------------------------------------------------
https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf
https://www.quarter-dev.info/archives/yamaha/YM3014B.pdf
https://docs.micropython.org/en/v1.29.0/library/rp2.StateMachine.html
https://docs.micropython.org/en/v1.29.0/library/rp2.DMA.html
https://raw.githubusercontent.com/micropython/micropython/v1.29.0/ports/rp2/modules/rp2.py
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/dreq.h
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/pio.h
https://raw.githubusercontent.com/raspberrypi/pico-sdk/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/addressmap.h
