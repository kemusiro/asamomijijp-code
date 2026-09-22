# レイトレーシング・クラスタ実験

320×180 RGB888画像を16×16 tileへ分割してPico 2 Wへ配る、見栄えを重視した並列計算デモです。対角2 sampleのanti-aliasing、2点の面光源近似、球4個とchecker床、拡散反射、鏡面highlight、Fresnelを含む1回反射を使用します。

## ディレクトリ

- `host/render_reference.py`：CPython参照描画とPNG出力
- `pico/raytracer_core.py`：MicroPython互換のtile計算コア
- `pico/build_native_core.sh`：RP2350 ARM向けnative `.mpy`の生成
- `network/ray_manager.py`：Raspberry Pi 5側manager
- `network/ray_worker.py`：Pico側worker
- `network/ray_main.py`：自動起動用entry point（Pico上では`main.py`）
- `emitters/`：original、native、限定Viper、inline assemblerの比較

## 画質preset

| preset | 解像度 | AA sample | shadow sample | 反射 |
| --- | ---: | ---: | ---: | ---: |
| `preview` | 160×90 | 1 | 1 | なし |
| `exhibition` | 320×180 | 2 | 2 | 1回 |
| `high-quality` | 384×216 | 4 | 4 | 1回 |

実機で検証した`exhibition` presetの完成CRC32はMicroPython/RP2350が`4278ccd8`、CPython参照が`7686fe75`です。両者はfloat32とfloat64の違いにより57,600画素中13画素が異なりますが、基準5画素は一致しました。

6台でoriginal、native、限定Viper、native＋inline assemblerを比較し、nativeが30,249.129 msで最速でした。実行方法、動画、制約は[プロジェクト全体のREADME](../README.md)、詳細値は[`emitters/README.md`](emitters/README.md)を参照してください。
