# Mandelbrotクラスタ実験

512×320、最大64反復のMandelbrot集合を16×16 tileへ分割し、Pico 2 Wへ動的に配る実験です。計算はRP2350上のfloat32へ合わせ、実軸対称性を使って上半分だけを計算します。

## ディレクトリ

- `host/mandelbrot_reference.py`：CPython上でfloat32を再現する参照実装
- `pico/mandelbrot_core.py`：Pico側のtile計算コア
- `pico/benchmark.py`：1台での時間・memory・checksum測定
- `network/manager.py`：Raspberry Pi 5側の複数worker manager
- `network/pico_worker.py`：MicroPython側の共通worker
- `network/mock_worker.py`：CPythonで動く模擬worker
- `network/progress_recording.py`：動画用traceの記録
- `network/render_progress_video.py`：traceからMP4を生成
- `network/rgb_status.py`：carrier board上のRGB状態表示
- `network/protocol.md`：`mandelbrot-wire-v2` protocol

展示jobの期待checksumは`1a26b685`、小規模jobは`9bcd4fd2`です。6台までの実測と実行方法は[プロジェクト全体のREADME](../README.md)を参照してください。
