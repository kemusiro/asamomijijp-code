# 検証記録

- 日付: 2026-09-26
- 状態: 所有者による最終版の確認済み。MicroPythonは実機でRAM実行、Arduino版はPico 2 W／UNO R4 WiFi／Minimaへ書き込み実機確認
- OS: macOS 26.6.2 / Apple Silicon
- ホストコンパイラー: Apple clang 21.0.0 (clang-2100.3.34.2)
- ホスト条件: C++11、`-Wall -Wextra -Werror -pedantic`、AddressSanitizer、UndefinedBehaviorSanitizer
- Arduino CLI: 1.5.1 (Homebrew, 2026-06-05)
- UNO R4コア: `arduino:renesas_uno` 1.6.0、GNU Arm Embedded 7-2017q4 / GCC 7.2.1 20170904
- Pico 2 Wコア: `rp2040:rp2040` 5.7.0、pqt-gcc 4.1.0-1aec55e / GCC 14.3.0

## 自動テスト

`sh tests/run.sh`成功。テストダブルのPrint/Wireと、送信列をRAMへ反映する簡易LCDモデルを使用。実物のLCDエミュレーターではなく、I2C波形や液晶駆動の正しさを保証しない。

- 5 V/3.3 Vの初期化列、バス初期化の省略、通常・消去・followerの待ち時間
- DDRAMへの文字列、CGRAMへの外字登録、左方向入力時の外字登録と入力設定復元
- `clear()`によるI/D変更への対処、home、直接CGRAM/DDRAMアクセス
- 表示ON/OFF・カーソル・点滅の独立性、カーソル移動・両方向スクロール
- 3表示モード、全コントラスト値0–63、発振・倍率の0–7、boosterとコントラストの相互保持
- 座標・アドレス・外字・enum・設定値の境界、不正な引数で通信しないこと
- NULを含む100バイトの配列送信（Wireバッファー長を超える一括送信をしない）
- 初期化11送信すべての位置で失敗を挿入
- コントラスト4送信、外字登録12送信、follower・発振設定各3送信の全位置で失敗を挿入
- 制御バイト／データバイトのバッファー書き込み不足、Wireエラーコード保持、文字列の部分書き込み数
- 障害後の送信停止と再初期化による復旧、Printエラーの保持

結果: `PASS: initialization, RAM model, controls, validation, timing, fault injection`

## 今回の実機検証対象とビルド

| コード | ボード | 環境 | LCD電源・プルアップ先 |
| --- | --- | --- | --- |
| Arduino版 | Pico 2 W | Arduino-Pico 5.7.0 | 3.3 V |
| Arduino版 | UNO R4 WiFi | Renesas 1.6.0 | 5 V |
| Arduino版 | UNO R4 Minima | Renesas 1.6.0 | 5 V |
| MicroPython版 | Pico 2 W | MicroPython 1.29.0 | 3.3 V |

すべての構成で基本2行表示、外字、点滅、左右スクロール、表示OFF/ON、左向き入力、数値上書きを実機で確認した。Arduino版で実際に書き込んだスケッチのビルド結果は次のとおり。

| FQBN | 例 | プログラム使用量 | グローバルRAM |
| --- | --- | --- | --- |
| `rp2040:rp2040:rpipico2w` | Pico2WFeatures | 315,384 bytes | 70,244 bytes |
| `arduino:renesas_uno:unor4wifi` | UnoR4WiFiFeatures | 60,224 bytes | 9,016 bytes |
| `arduino:renesas_uno:minima` | UnoR4MinimaFeatures | 47,372 bytes | 5,120 bytes |

数値はコア・Wire・Serial等を含むスケッチ全体で、クラス単体の消費量ではない。`architectures=*`はアーキテクチャ固有コードを使わない指定であり、全ボードの検証済み表示ではない。生成ファームウェアはGit管理外に置いた。

## MicroPython版の検証

- CPython: 3.14.6（Mac）
- mpremote: 1.29.0
- デバイス: Raspberry Pi Pico 2 W with RP2350
- ファームウェア: MicroPython 1.29.0 / `v1.29.0 on 2026-08-24 (GNU 16.1.0 MinSizeRel)`
- LCD: AQM1602XA-RN-GBW、秋月販売コード108896（所有者確認）
- 配線: LCD電源3.3 V、SDA=GP16、SCL=GP17、基板のプルアップ有効（所有者申告）
- バス: `I2C(0, freq=100000, scl=17, sda=16, timeout=50000)`
- 電源設定: V3_3、contrast=35、bias=1/5、oscillator=4、follower_ratio=4

`micropython/tests/test_driver.py`はCPythonと接続中のMicroPythonの両方で成功。Arduino版に対応する初期化・全64コントラスト値・3モード・入力検査・通信失敗挿入を行う。加えて短いACK数、ASCII以外の送信前拒否、部分書き込み数、KeyboardInterruptによる未初期化状態への遷移を検査する。模擬I2Cによるテストであり、実LCDの確認とは別。

実I2Cのscan結果は`['0x3e']`。`examples/basic.py`の初期化・2行送信は例外なし、`ready=True`。上段「AQM1602 / Pico2W」、下段「MicroPython 1.29」が正常に読めることを所有者が目視確認した。

`examples/features.py`は外字、点滅、左右スクロール、OFF/ON、左向き入力、数値の桁埋めを実行する。送信はすべて成功。外字の菱形・点滅・左右スクロール・表示OFF/ON・下段右端のCBA・100から空白付き99への上書き・最終表示がすべて正常だったことを所有者が目視確認した。

`mpremote resume mount`でPC側のソースを参照し、RAM上で実行した。既存の保存ファイルとMicroPythonファームウェアは書き換えていない。実行ログは[results/micropython-device.txt](results/micropython-device.txt)。

## Arduino版のPico 2 W実機試験

MicroPython版と同じLCD・3.3 V電源・GP16/GP17・100 kHz・contrast=35を使用。Arduino-Pico 5.7.0で生成した`Pico2WFeatures.ino.uf2`を書き込み、picotoolの検証も成功した。起動時の基本表示はPico2W例と同じ。

上段「AQM1602 / Pico2W」、下段「Arduino 3.3 V」を所有者が目視確認。シリアルの`s`に対して`READY`を受信した。`g`で機能テストを実行し、すべての送信が成功。外字の菱形、点滅、左右スクロール、表示OFF/ON、下段右端のCBA、100から空白付き99への上書き、最終表示「Arduino done」と菱形について、所有者がすべて正常と目視確認した。ログは[results/arduino-device.txt](results/arduino-device.txt)。

試験前にpicotool 2.0.0で全4 MiBをGit管理外へバックアップし、実機との一致を検証した。試験後は同じ4 MiBを書き戻し、全範囲の照合に成功。MicroPython 1.29.0の起動、および既存3ファイルすべてのSHA-256が試験前と一致することを確認した。

## Arduino版のUNO R4 WiFi実機試験

- Arduino UNO R4 WiFi、`arduino:renesas_uno:unor4wifi`、Renesasコア1.6.0
- LCD: 同じAQM1602XA-RN-GBW
- LCD電源・基板プルアップ先: ともに5 V（所有者が配線変更を確認）
- SDA/SCL: 標準ピンソケットのSDA/SCL（A4/A5と同じ`Wire`）、GND共通
- バス: 100 kHz、設定: V5、contrast=35、TwoLines、bias=1/5、oscillator=4、followerRatio=4
- スケッチ: `examples/UnoR4WiFiFeatures/UnoR4WiFiFeatures.ino`

当初の3.3 V配線では試験せず、通常端子の5 V系に合わせてLCD電源・プルアップを5 Vへ変更した。最初の書き込み後は配線誤りにより`lastError=4`（WireTransmission）、`lastWireStatus=2`で停止した。所有者の配線修正後に再起動し、初期化と基本表示に成功した。

所有者が上段「AQM1602 / UNO R4」、下段「Arduino 5 V」を目視確認。シリアル`s`で`READY`を取得し、`g`で機能試験を実行した。外字・点滅・左右スクロール・表示OFF/ON・下段右端のCBA・100から空白付き99への上書き・最後の「Arduino done」と菱形がすべて正常と所有者が目視確認した。送信もすべて成功。ログは[results/arduino-unor4wifi-device.txt](results/arduino-unor4wifi-device.txt)。既存スケッチは所有者の指示でバックアップせず上書きし、試験スケッチを残した。MicroPythonの書き込みは行っていない。

## Arduino版のUNO R4 Minima実機試験

- Arduino UNO R4 Minima、`arduino:renesas_uno:minima`、Renesasコア1.6.0
- LCD: 同じAQM1602XA-RN-GBW
- LCD電源とプルアップ先: 5 V、標準SDA/SCL（Wire）、GND共通（所有者確認）
- バス: 100 kHz、設定: V5、contrast=35、TwoLines、bias=1/5、oscillator=4、followerRatio=4
- スケッチ: `examples/UnoR4MinimaFeatures/UnoR4MinimaFeatures.ino`

DFU書き込み後にシリアル`s`で`READY: Arduino UNO R4 Minima basic display`を取得。所有者が上段「AQM1602 / UNO R4」、下段「Arduino 5 V」を目視確認した。`g`で機能テストを実行し、外字・点滅・左右スクロール・OFF/ON・下段右端のCBA・100から空白付き99への上書き・最終表示「Arduino done」と菱形がすべて正常と所有者が目視確認した。全送信も成功。ログは[results/arduino-unor4minima-device.txt](results/arduino-unor4minima-device.txt)。既存スケッチは所有者の指示でバックアップせず上書きし、試験スケッチを残した。

## 未検証と実機確認手順

Arduino版の実機確認は上記のPico 2 W（3.3 V）とUNO R4 WiFi／Minima（5 V）構成。待ち時間の個体差、電気特性、bias・発振・follower調整、1行・倍高モードは実測していない。確認結果をこれらへ一般化しない。

実機確認時はボード、コア版、モジュール型番、LCD電源、信号電圧、ピン、プルアップ抵抗、コントラストを記録する。まずBasicで2行表示、次にFeaturesで外字・点滅・スクロール・左右入力を確認する。電源再投入後の初期化、桁数が減る上書き、電源・配線不良時の戻り値と再初期化も確認する。モード変更・電源回路設定は各設定を一つずつ変更し、見え方と復帰を記録する。

## mip配布定義の検証（2026-09-26）

`package.json`（配布版1.0.0）を追加。MicroPythonドライバーの実装は変更せず、`micropython/aqm1602.py`を`aqm1602.py`へ、`LICENSE`を`aqm1602.LICENSE`へ配置する定義とした。

- CPython 3.14.6でJSONを読み込み、配布元2ファイルの存在と導入先が相対パスであることを確認。
- 一時ディレクトリへ定義どおりに配置し、`Aqm1602`のインポートと`ADDRESS == 0x3e`を確認。ライセンスを元ファイルとバイト単位で照合。
- `python3 -B micropython/tests/test_driver.py`: 成功。
- `sh tests/run.sh`: 成功（既存Arduino版ホストテスト）。
- `git diff --check`: 成功。

以上はホスト上の静的検査・自動テスト。続いて所有者の指示により、公開後の実機導入検証を実施した。

### 公開済みパッケージの実機導入

- 日付: 2026-09-26
- PC側ツール: mpremote 1.29.0
- ボード: Raspberry Pi Pico 2 W with RP2350、MicroPython 1.29.0（`v1.29.0 on 2026-08-24 (GNU 16.1.0 MinSizeRel)`）
- シリアルポート: `/dev/cu.usbmodem31301`
- 配布元: 公開済みコミット`3dd51c0d97a653415a655eee6a16f57069dacbc2`

```sh
mpremote connect /dev/cu.usbmodem31301 mip install github:kemusiro/asamomijijp-code/projects/aqm1602-arduino-notes/package.json@3dd51c0d97a653415a655eee6a16f57069dacbc2
```

GitHub経由の取得と`/lib/aqm1602.py`・`/lib/aqm1602.LICENSE`の導入が成功。導入前は`/lib`と同名モジュールが存在しないことを確認した。自動soft reset後に、`mount`を使わず導入済みモジュールをインポートし、`aqm1602.__file__ == "/lib/aqm1602.py"`と`Aqm1602.ADDRESS == 0x3e`を確認した。

導入した2ファイルのSHA-256は公開元のローカルファイルと一致。既存の`benchmark.py`、`mandelbrot_core.py`、`network_protocol.py`は導入前後のSHA-256が一致し、それ以外のファイル追加がないことも確認した。

導入済みモジュールを読み込んだ状態で、既存の`micropython/tests/test_driver.py`をRAM上で実行し、初期化・制御・RAMモデル・引数検査・通信失敗処理の全テストが成功した。テスト用スクリプトはボードへ保存していない。ログは[results/micropython-mip-device.txt](results/micropython-mip-device.txt)。ドライバーとライセンスは導入した状態で残している。

続いて所有者がLCD電源とプルアップ先3.3 V、SDA=GP16、SCL=GP17、GND共通の配線を確認した。`mount`を使わず、導入済み`/lib/aqm1602.py`の読み込み元を確認して`micropython/examples/basic.py`を実行。I2C scanは`['0x3e']`、全送信成功、`ready=True`。上段「AQM1602 / Pico2W」、下段「MicroPython 1.29」がともに正常に読めることを所有者が目視確認した。LCD表示ログは[results/micropython-mip-lcd.txt](results/micropython-mip-lcd.txt)。サンプルはRAM上で実行し、ボードへ保存していない。

今回確認したのはPC経由の`mpremote mip install`と導入済みモジュールによる基本2行表示。ボード単体のネットワーク経由の`mip.install()`は未実施。外字・スクロール等の機能表示は今回再試験せず、先の実機確認記録を参照する。導入・確認手順は[MicroPython版README](micropython/README.md)を参照。

## 記事との対応

所有者が2026-09-26に本文・コードの最終版を確定し、コードのコミット・push後に記事へ固定リンクを設定する順序を承認した。記事公開時はこのプロジェクトを含むコミットへリンクし、サイトとコードの版を対応付ける。

サイトのビルドにこのプロジェクトの取得処理を追加しない。サイトとコードのコミットは分ける。
