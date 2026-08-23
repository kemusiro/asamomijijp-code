# Raspberry Pi Pico 2 WのMicroPython DMA実験

[`asamomiji.jp`の「Raspberry Pi Pico 2 WのDMAをMicroPythonで試す」](https://asamomiji.jp/articles/raspberry-pi-pico-2-w-micropython-dma/)に対応する、実機コード、Analog Discovery 2収録コード、生ログ、集計処理です。

## 目的

MicroPython 1.28.0の`rp2.DMA`を使い、次の三項目を再現します。

1. `bytearray`間の32 bit DMAコピーとスライス代入の比較
2. PIO0 SM0のTX FIFOへCPUまたはDMAで16 KiBを供給する比較
3. GP18をPIO0 SM0で連続サンプリングし、RX FIFOからDMAで16 KiBを収録する簡易ロジックアナライザー

一般的なRP2350の性能上限を求めるものではなく、記録した1台のPico 2 W、公式MicroPython 1.28.0 ARM版、150 MHzでの実測です。

## ファイル

### Pico 2 Wで実行するコード

- `src/pico/memory_benchmark.py`: メモリー間コピーを2方式、5サイズ、31標本で測定
- `src/pico/pio_tx_benchmark.py`: PIOのTX FIFOへのCPU供給とDMA供給を3周波数で測定
- `src/pico/pio_output_capture.py`: GP16へ既知パターンをDMAで出力
- `src/pico/pio_cpu_activity_capture.py`: GP16出力中にPythonからGP17を反転
- `src/pico/cleanup_test.py`: 意図的な例外後にPIOとDMAチャネルが解放されることを検査
- `src/pico/logic_analyzer.py`: GP18をPIO＋DMAで収録し、CPU読み出し時間とも比較

### ホストで実行するコード

- `src/host/capture_pio_waveforms.py`: AD2でGP16またはGP16＋GP17を4096標本収録
- `src/host/check_logic_input.py`: DIO2をLow、High、LowにしてGP18の結線を検査
- `src/host/run_logic_analyzer.py`: DIO2から既知パターンを出し、Picoの収録データを回収
- `src/host/signal_analysis.py`: ビット列、ラン長、誤り、VCDを処理する純粋なPythonコード
- `src/host/analyze_results.py`: 全生ログから集計CSV、記事値JSON、VCD、SHA-256一覧を生成
- `src/host/verify_results.py`: 件数、記事掲載値、2回の測定差、生成物、個人情報を検査

測定記録の構成は[`results/README.md`](results/README.md)を参照してください。

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
| 測定器 | Digilent Analog Discovery 2 |
| WaveForms SDK | DWF 3.19.5 |
| AD2内部クロック | 100 MHz |
| 実測日 | 2026-08-23 |

## 結線

| Pico 2 W | 物理ピン | AD2 | 用途 |
| --- | ---: | --- | --- |
| GP16 | 21 | DIO0 | PIO出力 |
| GP17 | 22 | DIO1 | DMA中のCPU動作確認 |
| GND | 23 | GND | 共通GND |
| GP18 | 24 | DIO2 | 簡易ロジックアナライザー入力 |

DIO2を出力にする応用実験では、PicoのGP18を入力にします。PicoとAD2のGNDを必ず共通にし、GP16、GP17、GP18同士を短絡しないでください。

## 必要なソフトウェア

- Pico 2 W用MicroPython 1.28.0 ARM版公式ファームウェア
- `mpremote` 1.28.0
- 集計と検査にはCPython 3.11以降
- AD2自動収録にはWaveFormsとWaveForms SDK

ホストコードはPython標準ライブラリだけを使用します。WaveForms SDKは`ctypes`で動的に読み込みます。SDKライブラリが標準位置にない場合は、`--dwf`または`DWF_LIBRARY`で指定します。`mpremote`も`--mpremote`または`MPREMOTE`で指定でき、USBポートは`--port`で指定できます。個別PCのパスやポート番号はソースへ固定していません。

## ベンチマークの実行

プロジェクトのルートで実行します。`run`はコードをRAM上で実行し、Picoのファイルシステムへコピーしません。

```console
mpremote connect auto run src/pico/memory_benchmark.py
mpremote connect auto run src/pico/pio_tx_benchmark.py
mpremote connect auto run src/pico/cleanup_test.py
```

メモリーとPIOの測定は独立して2回実行し、標準出力を`results/raw/benchmarks/`へ保存します。ファイル名は`memory-run-1.csv`、`memory-run-2.csv`、`pio-run-1.csv`、`pio-run-2.csv`です。測定中はREPL操作やWi-Fi通信を行いません。

## AD2によるPIO出力確認

GP16のパターンを5条件で収録します。

```console
python3 src/host/capture_pio_waveforms.py \
  --mode output \
  --mpremote mpremote \
  --port auto
```

GP16とGP17を同時収録します。

```console
python3 src/host/capture_pio_waveforms.py \
  --mode activity \
  --mpremote mpremote \
  --port auto
```

各CSVには4096標本と時刻、DIO0、必要な場合はDIO1が入ります。出力確認では100 kHzと1 MHzに精密測定と長時間窓、10 MHzに100 MS/sの収録を使います。CPU動作確認では100 kHzと1 MHzを10 MS/s、10 MHzを20 MS/sで収録します。

## 簡易ロジックアナライザー

最初にDIO2からGP18への方向と配線を検査します。

```console
python3 src/host/check_logic_input.py --mpremote mpremote --port auto
```

次に1、5、10 Mbit/sのパターンを出し、それぞれ10、50、100 MS/sで収録します。

```console
python3 src/host/run_logic_analyzer.py \
  --mpremote mpremote \
  --port auto
```

この処理は16 KiBの生データ、Picoが測ったDMA／CPU時間、VCDを保存します。CPU方式はRX FIFOが満杯になるとPIOを停止させるため、DMA方式と同じ連続時間窓の収録ではありません。

## 集計と検査

保存した生ログから集計結果を生成します。

```console
python3 src/host/analyze_results.py --write
```

生成対象は次のとおりです。

- `results/summary/*.csv`: 実験別集計
- `results/summary/article-values.json`: 記事掲載値の正本
- `results/vcd/*.vcd`: 生バイナリから再生成したVCD
- `results/SHA256SUMS`: 生ログと生成結果のSHA-256

公開前検査は次の1コマンドです。

```console
python3 src/host/verify_results.py
```

この検査は、31標本の欠落、2回分のログ、記事表との丸め一致、GP16の既知パターン、GP17のエッジ、GP18から復元した13,100 bit、VCDと集計の再生成、後始末、結線確認、ハッシュ、個人用パスの混入を確認します。

## 2026年8月23日の結果

第2回測定の主要値は次のとおりです。詳細は`results/summary/`にあります。

| 実験 | 条件 | CPUまたはスライス | DMA | 比率 |
| --- | ---: | ---: | ---: | ---: |
| メモリーコピー | 256 byte | 8.30 µs | 23.30 µs | 0.356倍 |
| メモリーコピー | 4 KiB | 29.35 µs | 26.55 µs | 1.105倍 |
| メモリーコピー | 64 KiB | 362.10 µs | 130.55 µs | 2.774倍 |
| PIO TX FIFO | 100 kHz | 1,310,346 µs | 1,310,395 µs | DMA中285,258反復 |
| PIO TX FIFO | 10 MHz | 13,139 µs | 13,172 µs | DMA中2,843反復 |
| GP18収録 | 10 MS/s | 71,558 µs | 13,138 µs | 5.447倍 |
| GP18収録 | 100 MS/s | 71,208 µs | 1,340 µs | 53.140倍 |

GP16のPIO出力は各周波数で先頭354 bitまで期待値と一致し、観測範囲内にFIFO停止を検出しませんでした。GP17にはDMA中のPython実行を示す複数エッジがありました。GP18の三収録はラン長から各13,100 bitを復元し、誤りは0 bitでした。

## 公開版コードの検証状態

2026年8月23日に、公開用にパスを一般化した後のコードを同じPico 2 WとAD2で再検査しました。

- `memory_benchmark.py`: 5サイズ、2方式、各31標本を完走し、全コピーが一致
- `pio_tx_benchmark.py`: 3周波数、2方式、各31標本を完走し、`META,status,ok`
- `cleanup_test.py`: 例外前にDMA動作中、例外後にPIO停止、GP16 Low、DMAチャネル0再取得
- `check_logic_input.py`: DIO2のLow、High、Lowに対し、GP18のHigh回数が0、101、0
- `capture_pio_waveforms.py --mode output`: 5収録すべてで既知パターンの不一致0
- `capture_pio_waveforms.py --mode activity`: 3収録すべてでGP16不一致0、GP17に40、35、16エッジ
- `run_logic_analyzer.py`: 1、5、10 Mbit/sの各再収録で復元bit誤り0
- `verify_results.py`: 生ログ、集計、記事値、VCD、SHA-256、公開安全性の全検査に成功

この再検査は公開コードが完走することを見るスモークテストです。記事の表と`results/`の正本値は、独立して保存した当初の測定ログから生成し直しており、スモークテストの時間値へ置き換えていません。

## 来歴と公開用整形

- Pico、PIO波形、AD2連携、簡易ロジックアナライザーのコードは、2026年8月23日の記事実験用に作成しました。
- `results/raw/benchmarks/`は実機標準出力です。公開収録時にCRLFをLFへ正規化しましたが、行内容は変更していません。
- AD2のCSVとPicoの16 KiB収録バイナリは実測原データです。
- 公開版ホストコードでは、測定時の固定ポート、一時ディレクトリ、実行ファイルの絶対パスをCLI引数へ置き換えました。信号解析の結果は原データから再計算し、記事値と照合しています。
- Picoコードには説明用docstringと関数化を加えましたが、測定区間、転送設定、標本数、実行順、データパターンは実測時と同じです。
- 原稿中の短いコード抜粋は、このプロジェクトの設定と照合して公開します。

## 制約

- Pico 2 W 1台、MicroPython 1.28.0 ARM版、150 MHzだけを測っています。
- `time.ticks_us()`にはMicroPython API、ループ、DMA設定、完了確認が含まれます。
- DMA回路単体のサイクル数やRP2350の理論上限ではありません。
- DMAチャネル優先度、リング、連結、割り込み、Wi-Fi／Bluetoothとの競合は比較しません。
- GP16の連続性は131,072 bit全体ではなく、収録した先頭354 bitまでを直接確認しています。
- GP17の反転は定性的な確認信号で、ベンチマークの整数カウンターとは負荷が異なります。
- 簡易ロジックアナライザーは1チャネル、16 KiB、単発収録で、トリガー、複数バッファー、連続ストリーミング、プロトコルデコードを備えません。

## 第三者要素

第三者のソースコード、ファームウェア、WaveForms SDK、実行ファイルはこのプロジェクトに含めていません。外部依存関係は[`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)に記録しています。

## ライセンス

このプロジェクトで新規作成したコードには、リポジトリのルートにあるBSD 2-Clause Licenseを適用します。実測ログは実験の記録として提供し、外部ソフトウェアには各提供元のライセンスが適用されます。
