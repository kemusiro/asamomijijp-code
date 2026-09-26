# MicroPython版 Aqm1602

Arduino版と同じAQM1602XA-RN-GBW（販売コード108896）を対象とするドライバーです。`machine.I2C`または`machine.SoftI2C`の初期化済みオブジェクトを渡します。クラスはI2Cピンやクロックを変更しません。

## mipでの導入

プロジェクト直下の[`package.json`](../package.json)で、`aqm1602.py`とBSD-2-Clauseのライセンス文書`aqm1602.LICENSE`を導入します。外部パッケージへの依存はありません。通常はボードの`/lib`へ保存されます。サンプル・テスト・Arduino版は導入しません。

以下のGitHub経由のコマンドは、この`package.json`を含む変更が`main`へ公開された後に使えます。PCに`mpremote`を用意し、MicroPythonのボードをUSB接続して実行します。PCにはインターネット接続が必要ですが、ボードのWi-Fi接続は不要です。

```sh
mpremote mip install github:kemusiro/asamomijijp-code/projects/aqm1602-arduino-notes/package.json
mpremote exec "from aqm1602 import Aqm1602; print(hex(Aqm1602.ADDRESS))"
```

後者は`0x3e`を表示し、LCDへの通信を行わずにインポートを確認します。複数のボードを接続している場合は、`mpremote connect <ポート名> mip install ...`で対象を指定してください。導入はボードのファイルへ書き込み、同名の導入先ファイルは上書きします。ルートに手動配置した`aqm1602.py`がある場合は、古い版を読み込まないよう配置を整理してください。

ネットワーク接続済みで`mip`が使えるボードでは、REPLからも導入できます。

```python
import mip

mip.install("github:kemusiro/asamomijijp-code/projects/aqm1602-arduino-notes/package.json")
```

導入後は`from aqm1602 import Aqm1602`で利用できます。更新前のモジュールを既に読み込んでいる場合は、soft resetして読み直してください。

### 検証済みの版を固定する

上記コマンドはデフォルトブランチの内容を取得します。記事などで再現性が必要な場合は、`package.json`を含む公開済みコミットの完全なSHAを指定します。次の`COMMIT_SHA`は実際の値へ置き換えてください。

```sh
mpremote mip install github:kemusiro/asamomijijp-code/projects/aqm1602-arduino-notes/package.json@COMMIT_SHA
```

ボード上では同じSHAを`mip.install(..., version="COMMIT_SHA")`に渡します。`package.json`の`version`は配布版の情報であり、それだけで取得元のGitコミットを固定するものではありません。

### 公開前のローカル導入確認

プロジェクトルートで次を実行すると、GitHubへの公開前にローカルの定義からボードへ導入できます。

```sh
mpremote mip install ./package.json
mpremote exec "from aqm1602 import Aqm1602; print(hex(Aqm1602.ADDRESS))"
```

実際の表示確認は、下記の配線・最小例を使用してください。配布形式は[MicroPython公式のパッケージ管理仕様](https://docs.micropython.org/en/latest/reference/packages.html#writing-publishing-packages)に従います。

## Pico 2 Wの接続例

- MicroPython 1.29.0
- LCD電源3.3 V、GND共通
- SDA=GP16、SCL=GP17、I2C(0)、100 kHz
- LCD変換基板のプルアップ用ジャンパーを有効化（3.3 Vへプルアップ）

`aqm1602.py`をボード上のインポート可能な場所へ置いて使います。開発時は`mpremote mount`でPC側のファイルを参照すれば、ボードのフラッシュへコピーせずに試せます。

```python
from machine import I2C, Pin
from aqm1602 import Aqm1602

i2c = I2C(0, sda=Pin(16), scl=Pin(17), freq=100_000)
lcd = Aqm1602(i2c)
lcd.begin(supply=Aqm1602.V3_3, contrast=35)
lcd.text("AQM1602 / Pico2W")
lcd.set_cursor(0, 1)
lcd.text("MicroPython 1.29")
```

`begin()`のデフォルトは3.3 V用です。Arduino版のデフォルトは5 V用なので、記事・実験コードでは電源を明示します。設定はLCDの実電源に合わせてください。Pico 2 WのGPIOへ5 Vを加える配線例ではありません。

## API

設定APIは成功時`None`を返し、異常時は例外を送出します。成功時に`True`を返すArduino版とは戻り値の扱いが異なります。

| MicroPython API | 内容 |
| --- | --- |
| `begin(*, supply=V3_3, contrast=35, mode=TWO_LINES, bias=BIAS_ONE_FIFTH, oscillator=4, follower_ratio=4)` | 初期化・DDRAM消去。CGRAMは消去しない |
| `text(str)` | 表示可能ASCII文字列。成功バイト数を返す |
| `write(bytes_or_bytearray)` / `write_byte(code)` | 文字コードを直接送信。成功バイト数を返す |
| `clear()` / `home()` | 消去／表示シフトとカーソルの原点復帰 |
| `set_cursor(column, row)` | 0始まりの16列×2行。1行・倍高モードではrow=0のみ |
| `set_display(bool)` / `set_cursor_visible(bool)` / `set_blink(bool)` | 表示・カーソル・点滅 |
| `set_entry_mode(LEFT_or_RIGHT, shift_display=False)` | 入力方向・自動シフト |
| `move_cursor(LEFT_or_RIGHT)` / `scroll_display(LEFT_or_RIGHT)` | カーソル移動／両行のスクロール |
| `create_char(slot, bitmap)` | 5×8の外字0–7、8行、各行0–31 |
| `set_ddram_address(address)` / `set_cgram_address(address)` | 画面外も含むRAMアドレス指定 |
| `set_mode(TWO_LINES_or_ONE_LINE_or_DOUBLE_HEIGHT)` | 表示形式。1行・倍高は実機表示未確認 |
| `set_contrast(0_to_63)` | コントラスト |
| `set_bias_and_oscillator(BIAS_ONE_FIFTH_or_BIAS_ONE_FOURTH, 0_to_7)` | bias・発振設定 |
| `set_follower(bool, 0_to_7)` / `set_booster(bool)` | 電源回路設定。有効化後は安定待ち |
| `ready` / `last_error` / `bytes_written` | 初期化状態／最後の通信・中断例外／直近の文字送信で成功したバイト数 |

定数はすべて`Aqm1602`のクラス属性です。アドレス・表示形式・外字の契約と制約は[プロジェクトREADME](../README.md)のArduino版と共通です。

`text()`はU+0020〜U+007E以外を、通信開始前に`ValueError`で拒否します。改行やUTF-8日本語を意図せずLCDへ送らないためです。内蔵カナや外字には文字表に対応した`bytes`を使います。`write_byte(0)`は外字0を表示できます。数値は`lcd.text("%5.1f" % temperature)`のように呼び出し側で整形します。

`create_char()`は元の入力方向・自動シフトを復元し、DDRAMのアドレス0に戻ります。元のカーソル位置を復元するAPIではないため、続けて`set_cursor()`してください。倍高モードでの`create_char()`は拒否します。直接CGRAMへ書いた後もDDRAMへ戻す操作が必要です。

## エラーと中断

`writeto()`の`OSError`はそのまま呼び出し側へ返します。ACKされたデータが2バイト未満の場合も`OSError`です。`ready=False`となり、次の操作は送信せず`RuntimeError`となります。`last_error`には最初の失敗を保持します。原因を解消し、同じ設定で`begin()`をやり直してから画面・外字を再描画してください。

`write()`の途中で失敗した場合は`bytes_written`で成功したバイト数を確認できます。一部はすでに表示済みで、ロールバックしません。型・範囲違反は`TypeError`または`ValueError`で通信前に拒否し、初期化済み状態は維持します。不正な`begin()`引数も既存状態を変えずに拒否します。

複数命令の途中や待ち時間にCtrl-Cなどの中断が入った場合も再初期化を必要とします。`last_error`は有効な次の操作の開始時にクリアされます。設定APIでは`bytes_written`を更新しません。

固定待ち時間はArduino版と同じです。同期・ブロッキングAPIであり、複数タスク・IRQから同時に使わないでください。I2C呼び出し自体のタイムアウトはバス実装側の設定に従います。

## 実行とテスト

以下はプロジェクトルートからの実行例です。ポート名は手元の環境に合わせます。`resume`は自動soft resetを省略しますが、実行中のPython処理はREPL制御時に中断される場合があります。`mount`は終了時に解除され、テスト用ファイルをフラッシュへ保存しません。

```sh
# PC上: fake I2Cの単体テスト
python3 -B micropython/tests/test_driver.py

# Pico上: 同じ単体テスト。実I2Cは使わない
mpremote connect /dev/tty.usbmodem31301 resume mount micropython run micropython/tests/test_driver.py

# LCDへ実際に表示する例
mpremote connect /dev/tty.usbmodem31301 resume mount micropython run micropython/examples/basic.py
mpremote connect /dev/tty.usbmodem31301 resume mount micropython run micropython/examples/features.py
```

既に同名モジュールをインポートしていてファイルを編集した場合、上の`resume`ではモジュールキャッシュが残ります。実行中の処理を終了できることを確認して`resume`を外し、自動soft reset後に読み直してください。ファームウェアの書き換えは不要です。

[検証結果と確認範囲](../VALIDATION.md)にはI2C送信成功と目視確認を分けて記録します。

## 参照

- [MicroPython 1.29.0 I2C API](https://docs.micropython.org/en/v1.29.0/library/machine.I2C.html)
- [MicroPython 1.29.0 RP2 quick reference](https://docs.micropython.org/en/v1.29.0/rp2/quickref.html)
- [mpremote](https://docs.micropython.org/en/v1.29.0/reference/mpremote.html)

ライセンスは[BSD-2-Clause](../LICENSE)。第三者ドライバーのコードは収録していません。
