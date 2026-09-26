# AQM1602XA Arduino／MicroPythonクラス

[AQM1602 LCDをArduinoとMicroPythonで使う](https://asamomiji.jp/articles/aqm1602-arduino-notes/)に対応する完全版です。対象は秋月電子通商の販売コード108896に含まれる **AQM1602XA-RN-GBW（ST7032i）**。別世代のAQM1602への互換性は未検証です。

2026-09-26に記事内の説明用クラスを起点として新規実装しました。Arduino版は`Print`を継承し、動的メモリー確保なしで動作します。MicroPython版は初期化済みのI2Cバスを受け取ります。両版で自動テストを行い、Pico 2 W（3.3 V）で実LCDの表示・機能を確認しています。Arduino版はUNO R4 WiFi／Minima（5 V）でも実機確認済みです。詳細は[検証記録](VALIDATION.md)を参照してください。

- [MicroPython版の導入・API・実行方法](micropython/README.md)（`package.json`によるmip導入に対応）
- 以下はArduino版の導入とAPIです。

## Arduino版の導入と最小例

このフォルダー全体をArduinoのライブラリフォルダーへ`Aqm1602`という名前で配置するか、Arduino CLIの`--library`で指定します。`src/`だけをコピーするとサンプルや説明が欠けるため、フォルダー全体を使用してください。

```cpp
#include <Aqm1602.h>

Aqm1602 lcd;

void setup() {
  if (!lcd.begin()) return;  // LCD電源5 V用の初期値
  lcd.print("Hello");
  lcd.setCursor(0, 1);
  lcd.print(23.5, 1);
}
void loop() {}
```

エラー報告を含む例は[Basic](examples/Basic/Basic.ino)、外字・点滅・スクロールなどは[Features](examples/Features/Features.ino)にあります。同じGP16/GP17・3.3 V配線をArduino-Picoコアで使用する例は[Pico2W](examples/Pico2W/Pico2W.ino)です。実機試験用の[Pico2WFeatures](examples/Pico2WFeatures/Pico2WFeatures.ino)は起動時に同じ基本表示を行い、シリアルへ`s`を送ると状態を返し、`g`を送ると5秒後に機能テストを開始します。シリアル速度は115200 bpsです。`println()`はCR/LFを文字コードとして送り、行移動をしません。UTF-8変換、自動折り返し、行末の自動消去は行いません。

I2Cアドレスはモジュールの固定値`0x3E`です。配線はLCDの`+V`、`GND`、`SDA`、`SCL`を使用し、Arduino側のピンはボード資料を参照してください。HIGH電圧はLCDとMCU両方の仕様を満たす必要があります。LCD電源5 Vと3.3 V MCUを無条件に直結する例ではありません。変換基板のプルアップ用ジャンパーと既存のプルアップ先電圧を確認してください。

## 電源とバスの設定

```cpp
Aqm1602::Config config;
config.supply = Aqm1602::Supply::V3_3;  // 実際のLCD電源に合わせる
config.contrast = 35;  // 今回の3.3 V実機で確認した値。個体に合わせて調整
if (!lcd.begin(config)) {
  // lastError() / lastWireStatus()を記録する
}
```

`Config`の初期値は5 V、コントラスト35、2行、1/5 bias、発振設定4、follower倍率設定4です。`supply`は実電圧を変えず、初期化時のbooster設定だけを選びます。3.3 Vではboosterを有効、5 Vでは無効にします。今回の3.3 V実機では、Arduino版とMicroPython版の両方で35で両行を読めることを確認しました。個体・視線角度に合わせて調整してください。電源構成を変える場合は電源を切って配線を変更し、対応する`Config`で再初期化します。

既に初期化済みのバスは`lcd.begin(config, false)`で使えます。別のバスを使う場合は`Aqm1602 lcd(Wire1);`のように渡します（`Wire1`の有無はコアによる）。バスのピン、クロック、タイムアウトは呼び出し側で設定してください。このクラスは共有バスのクロックやタイムアウトを変更しません。LCDのSCL上限は400 kHzです。

## APIと対応範囲

設定・操作APIは成功時`true`、失敗時`false`。`write()`は成功したバイト数を返します。引数の列・行・slotは0始まりです。

| 機能 | API | 契約 |
| --- | --- | --- |
| 初期化 | `begin()` / `begin(config, beginWire)` | DDRAM消去、表示ON、カーソル・点滅OFF、右方向入力。CGRAMは初期化しない |
| 文字・数値 | `print(...)`, `write(byte)`, `write(data, size)` | LCDの文字コードを送信。配列は1バイトごとに通信、失敗した時点で停止 |
| 全消去 | `clear()` | DDRAM消去。設定済みの入力方向・自動シフトを再設定 |
| 原点復帰 | `home()` | 文字を残して表示シフトとカーソルを原点へ戻す |
| 表示位置 | `setCursor(column, row)` | 16列。2行モードのみrow=1を許可。表示シフト後も元のDDRAM配置を基準にする |
| 画面外DDRAM | `setDdramAddress(address)` | 2行: 00–27/40–67、1行: 00–4F、倍高: 00–27（16進） |
| 表示・カーソル・点滅 | `setDisplay(bool)`, `setCursorVisible(bool)`, `setBlink(bool)` | 他の表示制御ビットを維持 |
| 入力方向・自動シフト | `setEntryMode(Direction, shiftDisplay=false)` | Rightでアドレス増加、Leftで減少。自動シフトONでは画面は入力方向と逆向きに動く |
| カーソル移動 | `moveCursor(Direction)` | 1位置移動。画面上の16文字端で折り返す処理はしない |
| 表示移動 | `scrollDisplay(Direction)` | 両行の表示を1位置移動 |
| 表示形式 | `setMode(Mode)` | `TwoLines`, `OneLine`, `DoubleHeight`。変更後home、DDRAMは保持 |
| 外字登録 | `createChar(slot, bitmap)` | 5×8ドット、slot 0–7、8バイト、各行0–31。倍高モードでは拒否 |
| CGRAM直接操作 | `setCgramAddress(address)` + `write(...)` | 0–63。終了後は明示的にDDRAMを選択 |
| コントラスト | `setContrast(value)` | 0–63。上下位ビットを更新し、booster設定は維持 |
| bias・発振 | `setBiasAndOscillator(Bias, value)` | `OneFifth`/`OneFourth`、F2..F0=0–7 |
| follower | `setFollower(enabled, ratio)` | Rab2..Rab0=0–7。有効化後は安定待ち |
| booster | `setBooster(enabled)` | 有効化は3.3 V設定時のみ許可。有効化後は安定待ち |
| 診断 | `ready()`, `lastError()`, `lastWireStatus()`, `getWriteError()` | 下記エラー処理を参照 |

1行・倍高文字モードはコントローラーの設定を公開する実験用APIです。モジュール上の見え方や倍高モードの外字構成は未確認です。`createChar()`は確認可能な5×8の登録形式に限定し、倍高モードを拒否します。必要なCGRAMアクセス自体は低水準APIで可能ですが、倍高外字の動作保証を意味しません。2行＋倍高の禁止組み合わせと、I2Cでは不要な4ビットバス設定はAPIで作れません。

AQM1602XAにないICON表示、I2C経由のBusyフラグ・アドレス・RAM読み出し、バックライト制御は提供しません。コントローラー全品種向けのドライバーではありません。未知の命令による内部状態の不一致を避けるため、汎用の生コマンド送信APIも公開していません。

## 外字と状態

`createChar()`は入力方向を一時的に右向き・自動シフトなしにし、8行分を書き込みます。成功後はDDRAMのアドレス0へ戻り、元の入力方向・自動シフト設定を復元します。表示シフトは変更しません。登録前のカーソル位置は復元しないため、続けて`setCursor()`してください。

外字0は`lcd.write(static_cast<uint8_t>(0))`で表示します。NULを含む文字コード列にはC文字列ではなく`write(data, size)`を使います。`bitmap`は呼び出し中に読める8バイトのRAM配列としてください。AVRのPROGMEM専用アクセスは実装していません。

生の`setCgramAddress()`以降は`write()`の送信先がCGRAMになります。`setDdramAddress()`、`setCursor()`、`home()`、`clear()`のいずれかでDDRAMへ戻してください。読み出しの代わりに推測したカーソル位置を返すAPIはありません。

## 通信エラーと復旧

`lastError()`は`None`, `NotInitialized`, `InvalidArgument`, `WireBuffer`, `WireTransmission`のいずれかです。`lastWireStatus()`には`Wire.endTransmission()`の結果を保存します。ステータス番号の意味は使用コアのWire仕様を確認してください。Wireバッファーへの書き込み不足でも失敗とし、開いた送信は閉じます。

通信が失敗した場合は、LCDがどこまで命令を受け付けたか不明なため`ready()`を`false`にします。それ以降の操作は送信せず失敗し、元の診断を保持します。配線や電源を確認し、`begin(config)`を成功させてから再描画・外字再登録してください。Wire実装自体が停止する場合をこのクラスだけで中断することはできません。

引数エラーは通信せず拒否し、初期化済み状態は維持します。次の有効な操作で`lastError()`は更新されます。`Print`の`getWriteError()`は成功後も残るため、確認後に`clearWriteError()`を使ってください。これだけでは通信障害から復旧しません。`begin()`成功時にはクリアされます。複数バイトの転送途中で失敗した場合は一部が既に表示済みで、ロールバックしません。

待ち時間は通常送信100 µs、消去・home 3 ms、初期化開始100 ms、follower有効化後201 msです。固定待ち時間方式の同期APIであり、ノンブロッキングではありません。割り込みや複数タスクから同時呼び出しをせず、同じLCDへ別クラスや生Wireで命令を送らないでください。電源断・外部リセットは検出できないので、呼び出し側で再初期化します。

## UNO R4 WiFi／Minimaでの実機試験

WiFi向けの[UnoR4WiFiFeatures](examples/UnoR4WiFiFeatures/UnoR4WiFiFeatures.ino)とMinima向けの[UnoR4MinimaFeatures](examples/UnoR4MinimaFeatures/UnoR4MinimaFeatures.ino)は通常のSDA/SCL端子（A4/A5と同じ`Wire`バス）を使います。LCD電源とLCD基板のプルアップ先を両方5 Vにし、GNDを共通にしてください。初期化は`Supply::V5`、contrast=35、100 kHzです。UNO R4 WiFiのQwiicは別の3.3 Vバス`Wire1`なので、この例の接続先ではありません。

起動時は「AQM1602 / UNO R4」「Arduino 5 V」を表示します。115200 bpsのシリアルへ`s`を送ると状態を返し、`g`を送ると5秒後に機能テストを開始します。通信失敗時はエラーを繰り返し報告して停止します。配線を直した後はリセットして再初期化してください。

## Arduino版の検査手順

プロジェクトのルートで実行します。

```sh
sh tests/run.sh
arduino-cli compile --fqbn rp2040:rp2040:rpipico2w --library . --build-path /tmp/aqm1602-pico2w-features examples/Pico2WFeatures
arduino-cli compile --fqbn arduino:renesas_uno:unor4wifi --library . --build-path /tmp/aqm1602-unor4wifi-features examples/UnoR4WiFiFeatures
arduino-cli compile --fqbn arduino:renesas_uno:minima --library . --build-path /tmp/aqm1602-unor4minima-features examples/UnoR4MinimaFeatures
```

ホスト検査はC++11とAddressSanitizer/UndefinedBehaviorSanitizerに対応するC++コンパイラーが必要です。`CXX=clang++ sh tests/run.sh`のように指定できます。MicroPython版の検査は`python3 -B micropython/tests/test_driver.py`。Picoでの実行手順はMicroPython版READMEにあります。Arduinoのボードコアは別途インストールが必要です。上のコンパイルは接続したボードへ書き込みません。

## 出典・来歴・ライセンス

設計時に参照した一次資料（2026-09-26確認）:

- [AQM1602XA-RN-GBW説明書](https://akizukidenshi.com/goodsaffix/AQM1602_rev2.pdf): 電源、booster、ICON非搭載、読み出し不可、初期化例
- [ST7032データシートV1.3](https://akizukidenshi.com/goodsaffix/ST7032-0Dv1_3.pdf): pp.12–17、20–29の通信・RAM・命令・初期化仕様
- [Arduino Print実装](https://github.com/arduino/ArduinoCore-avr/blob/master/cores/arduino/Print.cpp): 継承API

第三者ライブラリの実装・データシート・文字ROMデータを本プロジェクトへ複製していません。テスト用のArduino/Print/Wireスタブと外字の菱形パターンも本プロジェクト用の新規実装です。外部依存のArduinoコア・Wireはそれぞれのライセンスに従い、このリポジトリのライセンスへ変更しません。新規ソースにはリポジトリの[BSD-2-Clause](LICENSE)を適用します。

記事には本プロジェクトに対応する説明用の抜粋を掲載します。再現するコードの版は、記事内のコミット固定リンクを参照してください。
