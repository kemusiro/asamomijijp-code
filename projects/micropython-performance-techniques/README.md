# MicroPythonコードエミッタの実機ベンチマーク

[`asamomiji.jp`の「MicroPythonのnative・Viper・インラインアセンブラ」](https://asamomiji.jp/articles/micropython-performance-techniques/)に掲載する、bytecode、native、Viper、Thumbインラインアセンブラの比較コードと実測記録です。

## 対象と目的

同じRaspberry Pi Pico 2 W上で、次の四方式を比較します。

- 通常のMicroPython bytecode
- `@micropython.native`
- `@micropython.viper`
- `@micropython.asm_thumb`

整数ループとバッファー処理を分け、各方式が得意とする処理と、Python互換性・安全性とのトレードオフを確認します。一般的な性能順位や、別のボード、ファームウェア、CPU周波数へ適用できる数値を求めるものではありません。

## ファイル

- `benchmark.py`: Pico 2 W上で実行する完全なベンチマーク
- `raytrace_native.py`: 同じ整数レイトレーサーをbytecodeとnativeで比較する応用例
- `export_raytrace_pgm.py`: native版の描画結果をhostへPGM形式で保存するスクリプト
- `verify_results.py`: 保存した測定ログの件数と集計値をCPythonで再検査するスクリプト
- `verify_raytrace_results.py`: レイトレーサーの画像検証値と測定集計を再検査するスクリプト
- `results/pico2w-arm-micropython-1.28.0-2026-08-17.log`: 2026年8月17日の第2回測定ログ
- `results/repeat-summary.csv`: 独立した2回の測定結果
- `results/pico2w-raytrace-native-2026-08-17.log`: レイトレーサーの第2回測定ログ
- `results/raytrace-repeat-summary.csv`: レイトレーサーを独立して2回測った集計
- `results/raytrace-native-pico2w.pgm`: Pico 2 Wのnative版から取得した64×48画素の実画像
- `disassembly/emitter-disassembly.py`: 逆アセンブル対象をベンチマークから抜き出したソース
- `disassembly/armv7emsp-objdump.txt`: MicroPython 1.28.0の`mpy-cross`が出力した6関数のThumb命令列

## 測定環境

| 項目 | 値 |
| --- | --- |
| ボード | Raspberry Pi Pico 2 W |
| MCU | RP2350、ARM CPUモード |
| MicroPython | 1.28.0、公式`RPI_PICO2_W`ビルド |
| ファームウェアのビルド日 | 2026-04-06 |
| コンパイラー表記 | GNU 14.2.0、MinSizeRel |
| CPU周波数 | 150,000,000 Hz |
| ホスト | macOS、USB CDC接続 |
| 実行ツール | mpremote 1.28.0 |
| タイマー | `time.ticks_us()` |

ファームウェアは測定前から実機に入っていた公式1.28.0を使用し、再書き込みやCPU周波数の変更は行っていません。`mpremote run`でRAM上へコードを送り、Picoのファイルシステムには保存していません。

## ワークロード

### 整数ループ

1から20,000までの和を、減算しながら加算する`while`ループで求めます。1標本につき関数を20回呼ぶため、合計400,000ループです。期待値`200010000`を全方式で確認します。

この処理では、bytecodeとnativeはPythonの整数として演算し、Viperとインラインアセンブラは32ビットの機械語整数として演算します。今回の入力と結果は、どちらでも同じ正の値になる範囲に収めています。

### バッファー処理

4,096 bytesの`bytearray`を先頭から走査し、各要素と`0x5a`の排他的論理和を取ります。1標本につき20回処理するため、合計81,920 byte更新です。偶数回のXORで元のバッファーへ戻ることと、1回処理時の全要素を測定前に確認します。

Viper版は`ptr8`、インラインアセンブラ版は`ldrb`と`strb`を使います。これらにはPythonの添字アクセスが行う境界検査がないため、速度と引き換えに安全性が下がります。

### 整数レイトレーサー

64×48画素のグレースケール画像へ球を描きます。各画素についてカメラからのレイと球の交差判定を行い、交差した場合はビット演算による整数平方根から表面の奥行きと明るさを求めます。浮動小数点や`math.sqrt()`を使わないため、既存のC関数ではなくMicroPythonで実行される整数演算と分岐を比較できます。

bytecode版とnative版はデコレータ以外が同じ関数本体です。別々の`bytearray`へ描画し、全3,072画素、球との交差数、画素値合計が一致することを測定前後に確認します。Viper型、ポインター、インラインアセンブラは使っていません。

## 測定方法

次の手順は`benchmark.py`による四方式の測定です。レイトレーサーは1回の描画を1標本とし、bytecode版とnative版を11回ずつ、実行順を交互にして測りました。

1. 各関数の結果を照合する。
2. 各関数を測定外でウォームアップする。
3. 各標本の直前に`gc.collect()`を実行する。
4. `time.ticks_us()`と`time.ticks_diff()`で20回の関数呼び出し全体を測る。
5. 四方式の実行順を標本ごとに回転させる。
6. 各方式を31回測り、最小値、中央値、最大値を求める。

割り込みは無効化していません。最小値と中央値だけでなく最大値も残し、USBやシステム割り込みを含む実機上のばらつきを確認できるようにしています。時間には20回分のPython側の呼び出しループと関数呼び出しコストも含まれます。

## 実行方法

MicroPython 1.28.0のARM版公式ファームウェアを入れたPico 2 Wを接続し、リポジトリのこのディレクトリで実行します。

```console
mpremote connect auto run benchmark.py
```

このコマンドは`benchmark.py`をRAM上で実行し、ボードのファイルシステムへコピーしません。測定結果を保存した後は、ホスト側で検査します。

```console
python3 verify_results.py results/pico2w-arm-micropython-1.28.0-2026-08-17.log
```

レイトレーサーは次のように実行・検査します。

```console
mpremote connect auto run raytrace_native.py
python3 verify_raytrace_results.py \
  results/pico2w-raytrace-native-2026-08-17.log \
  results/raytrace-native-pico2w.pgm
```

測定後には32×24文字のプレビューを表示します。`PRINT_FRAME`を`True`にすると、64×48画素そのものも16進数で出力できます。どちらの出力も測定区間の外です。

PGM画像は、プロジェクトディレクトリだけを`/remote`へ一時mountし、Picoのファイルシステムを経由せずに取得できます。

```console
mpremote connect auto mount . run export_raytrace_pgm.py
```

保存したPGMは64×48画素、3,085 bytesで、SHA-256は`9eed5c9b05849d51135d93f8f6577a0bcb7b9a80b8fb5e07fbd57830e4712db0`です。

## 2026年8月17日の結果

第2回測定の中央値は次の通りです。時間は1標本、すなわち20回の関数呼び出し全体の値です。「bytecode比」は同じワークロードの中央値を基準にしています。

| ワークロード | 方式 | 中央値 | bytecode比 |
| --- | --- | ---: | ---: |
| 整数ループ | bytecode | 797,662 µs | 1.000倍 |
| 整数ループ | native | 371,856 µs | 2.145倍 |
| 整数ループ | Viper | 29,551 µs | 26.993倍 |
| 整数ループ | `asm_thumb` | 10,870 µs | 73.382倍 |
| バッファー | bytecode | 424,722 µs | 1.000倍 |
| バッファー | native | 308,844 µs | 1.375倍 |
| バッファー | Viper | 21,531 µs | 19.726倍 |
| バッファー | `asm_thumb` | 4,704 µs | 90.290倍 |

第1回と第2回の中央値は、整数ループで各方式とも0.002%以内、バッファー処理で0.023%以内でした。詳細は`results/repeat-summary.csv`と第2回の生ログを参照してください。

### 整数レイトレーサー

第2回測定では、通常版とnative版を11回ずつ交互に実行しました。

| 方式 | 最小値 | 中央値 | 最大値 | bytecode比 |
| --- | ---: | ---: | ---: | ---: |
| bytecode | 192,375 µs | 192,471 µs | 192,609 µs | 1.000倍 |
| native | 97,595 µs | 97,616 µs | 97,627 µs | 1.972倍 |

両版の結果は1,481ヒット、画素値合計323,731で、`bytearray`全体も一致しました。独立した第1回と第2回の中央値差はbytecodeが0.001%未満、nativeが0.004%未満でした。

native化によりバイトコードの命令ディスパッチはなくなりますが、整数はPythonオブジェクトのままで、画素の添字アクセスや演算のランタイム呼び出しも残ります。この約2倍という結果は、デコレータだけで同じアルゴリズムを改善できる一方、Viperの機械語整数ほど意味を変えていないことを示す応用例です。

## 生成コードの確認

`disassembly/`には、実機と同じMicroPython 1.28.0、ARMv7E-M単精度浮動小数点ABIを指定して生成した機械語と逆アセンブル結果を収録しています。実機のRAMを読み出したものではなく、同じ版の公式`mpy-cross`を使った再現用出力です。生成条件、コード領域の取り出し方、読み方は[`disassembly/README.md`](disassembly/README.md)を参照してください。

## 解釈上の制約

- 数値はこのPico 2 W、MicroPython 1.28.0 ARM版、150 MHzでの結果です。
- 四方式で同じ答えになる処理を選んでいますが、実行時の意味は同一ではありません。ViperとインラインアセンブラはPythonの任意精度整数や境界検査を提供しません。
- インラインアセンブラ版はARM Thumb専用です。RISC-V版ファームウェアでは`asm_rv32`として別に実装する必要があります。
- ワークロードは単純なループです。I/O待ち、ネットワーク通信、浮動小数点、オブジェクト生成が中心のプログラムへ倍率を適用できません。
- レイトレーサーは説明用の整数モデルであり、反射、影、複数物体、透視補正などを備えた汎用レンダラーではありません。
- `time.ticks_us()`による経過時間であり、CPUサイクル数ではありません。

## 出典

- [MicroPython 1.28.0: Maximising MicroPython speed](https://docs.micropython.org/en/v1.28.0/reference/speed_python.html)
- [MicroPython 1.28.0: Inline assembler for Thumb2 architectures](https://docs.micropython.org/en/v1.28.0/reference/asm_thumb2_index.html)
- [Pico 2 W公式MicroPythonファームウェア](https://micropython.org/download/RPI_PICO2_W/)
- [MicroPython 1.28.0のRP2ポート設定](https://github.com/micropython/micropython/blob/v1.28.0/ports/rp2/mpconfigport.h)

## ライセンス

このプロジェクトのコードには、リポジトリのルートにあるBSD 2-Clause Licenseを適用します。第三者コードは含みません。
