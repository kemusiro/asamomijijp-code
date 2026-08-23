# 測定記録

## `raw/benchmarks/`

- `memory-run-1.csv`、`memory-run-2.csv`: メモリー間転送を独立して2回測った標準出力
- `pio-run-1.csv`、`pio-run-2.csv`: PIO TX FIFO供給を独立して2回測った標準出力
- `cleanup-test.log`: 意図的な例外後にPIO停止、GP16 Low、DMAチャネル再取得を確認した実機出力

ベンチマークCSVの各`RESULT`行が1標本です。メモリーは1標本内で20コピー、PIOは1標本内で16 KiBを1回供給します。公開収録時に改行をCRLFからLFへ正規化しています。

## `raw/pio-waveforms/`

Analog Discovery 2のDIO0でGP16を4096標本収録したCSVです。精密測定と、10標本/bitで先頭354 bitを見る連続性確認を分けています。

## `raw/cpu-activity/`

DIO0のGP16とDIO1のGP17を同時に4096標本収録したCSVです。GP17エッジを複数含む時間窓を選んでいます。

## `raw/logic-analyzer/`

- `capture_*Sps.bin`: PicoのPIO＋DMAがGP18から収録した16 KiBの原データ
- `timings.csv`: Picoが測った理論時間の整数部、DMA時間、CPU読み出し時間、並行反復回数、チェックサム
- `connectivity.log`: DIO2をLow、High、LowにしたGP18結線確認

`.bin`は取得順の1 bit標本をLSB-firstで詰めています。各条件は入力1 bit当たり10標本です。

## `summary/`と`vcd/`

`src/host/analyze_results.py --write`が生ログだけから生成します。手編集しません。

- `summary/memory.csv`: 2回分の最小値、中央値、最大値、速度比、DMAスループット
- `summary/pio.csv`: 2回分のPIO理論時間、CPU／DMA供給時間、並行反復回数
- `summary/pio-waveforms.csv`: GP16のビット幅と既知パターンの照合
- `summary/cpu-activity.csv`: GP16照合とGP17エッジ数
- `summary/logic-analyzer.csv`: GP18収録時間、速度比、復元bit誤り
- `summary/article-values.json`: 記事の表と照合する全値
- `vcd/*.vcd`: 3個の16 KiB生データから生成したVCD

`SHA256SUMS`は`raw/`、`summary/`、`vcd/`の全ファイルを対象にします。`python3 src/host/verify_results.py`は再集計、VCD再生成、ハッシュ再計算を行い、生成物の手編集や生ログの欠落を検出します。
