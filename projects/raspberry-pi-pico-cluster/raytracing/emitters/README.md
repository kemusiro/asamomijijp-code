# 浮動小数点レイトレーサーのコードエミッタ比較

Raspberry Pi Pico 2 Wクラスタ用の同一レイトレーサーを、MicroPythonのoriginal、native、
限定Viper、Thumbインラインアセンブラで比較したソースと実測結果です。320×180 RGB888、
2×アンチエイリアス、2点面光源サンプリング、1回反射の同一ジョブを使用しています。

## 収録方式

| ファイル | 方式 | 状態 |
| --- | --- | --- |
| `raytracer_core_original.py` | originalのMicroPython実装 | 実機合格 |
| `raytracer_core_original.py`を`-X emit=native`でコンパイル | 全モジュールnative | 実機合格、採用方式 |
| `raytracer_core_viper.py` | RGB888への3 byte格納だけ`ptr8`とViperを使用 | 10秒timeoutで実機合格、originalより低速 |
| `raytracer_core_inline_asm.py` | 全モジュールnative＋RGB変換をThumb FPUで実装 | 実機合格 |
| `experiments/raytracer_core_full_viper.py` | tracing hot path全体をViper化した失敗実験 | 4×4 tileでhard lock、使用禁止 |

Viperは機械語整数とpointer処理に向く一方、このrendererは浮動小数点、tuple、辞書を多用します。
限定Viperは出力互換でしたが、関数呼び出し増加を相殺できず高速化しませんでした。全面Viper版は
失敗も含めて検証を再現できるよう隔離してあります。

## 測定環境

| 項目 | 値 |
| --- | --- |
| worker | Raspberry Pi Pico 2 W 6台 |
| MCU | RP2350、ARM CPUモード |
| MicroPython | 1.28.0、`sys.implementation._mpy = 7942` |
| mpy-cross | MicroPython 1.28.0 |
| native architecture | `armv7emsp` |
| job | 320×180、RGB888、2 AA sample、2 shadow sample、1反射 |
| tile | 16×16、240 tile、各worker 40 tile |
| 測定日 | 2026-09-14 |

## 6台実測結果

| 方式 | worker timeout | E2E | worker計算合計 | original比 |
| --- | ---: | ---: | ---: | ---: |
| original | 5秒 | 35,052.376 ms | 197,771 ms | 基準 |
| native | 5秒 | 30,249.129 ms | 168,991 ms | 13.7%短縮 |
| 限定Viper | 5秒 | — | — | 全worker timeout |
| 限定Viper（診断） | 10秒 | 35,314.571 ms | 199,063 ms | 0.7%遅延 |
| native＋inline assembler | 5秒 | 30,832.078 ms | 172,316 ms | 12.0%短縮 |

完了した全方式で完成画像CRC32 `4278ccd8`、基準5画素、240/240 tileが一致しました。
単体中央tileの中央値はoriginal 1,423 ms、native 1,184 ms、限定Viper 1,421 ms、
native＋inline assembler 1,219 msでした。

## ビルド

`.mpy`はMicroPython versionとarchitectureに依存するため収録していません。MicroPython 1.28.0の
`mpy-cross`を用意して、次のように再生成します。

```console
./build_variants.sh /path/to/micropython-1.28.0/mpy-cross/build/mpy-cross
```

`build/`へ次が生成されます。

- `raytracer_core_original.mpy`
- `raytracer_core_native.mpy`
- `raytracer_core_viper.mpy`
- `raytracer_core_inline_asm.mpy`

実機では選択した1ファイルだけを`raytracer_core.mpy`として配置します。異なるMicroPython versionや
RISC-V firmwareへ生成物を転用しないでください。

全面Viper版は通常のビルドから除外しています。停止事象の調査で必要な場合だけ、1台で次のように
生成してください。

```console
/path/to/mpy-cross -march=armv7emsp -s raytracer_core.py \
  -o build/raytracer_core_full_viper.mpy \
  experiments/raytracer_core_full_viper.py
```

## 単体tile測定

選択した`.mpy`をPico側へ`raytracer_core.mpy`として置き、`benchmark_tile.py`を実行します。

```console
mpremote connect auto fs cp build/raytracer_core_native.mpy :raytracer_core.mpy
mpremote connect auto run benchmark_tile.py
```

複数台へ展開する前に、1台でCRC、処理時間、soft reset後の復帰を確認してください。ソースのうち
CPythonで安全に読み込める3方式は次でも照合できます。

```console
python3 verify_variants.py
```

## 全面Viper版の既知の停止

`experiments/raytracer_core_full_viper.py`は、中央tileの空だけを処理する1×1画素では2 msで完了し、
originalとRGB値・CRCが一致しました。しかし、surface shadingへ入る4×4画素では15秒を超えて
完了せず、REPLも応答しなくなりました。復旧にはMicro-B給電の抜き差しが必要でした。

この実験はViperの一般的な不具合を断定するものではありません。停止位置から、浮動小数点、tupleの
生成・展開、大きなnative frame、Viper関数の多段呼び出しを含む`_shade()`経路との不適合が疑われます。
原因を分離できていないため、全面Viper版を展示や複数台試験に使用しないでください。

## 来歴と制約

- original sourceは`kemusiro/cho-eleki-expo-2026`のcommit
  `a5433fc3db6bd2b2a0b6d9e4296d3cbd6e9784ee`から収録しました。
- emitter variantは2026-09-14のIssue #12実機検証で作成したソースです。
- 6台結果は同一画質・tile・通信条件で測定しましたが、originalだけは2026-09-12の基準値です。
- 16台構成の処理時間は未検証です。
- インラインアセンブラ版はARM Thumb FPU専用で、RP2350 RISC-V modeでは動作しません。
- native code、Viper、インラインアセンブラはVMの安全機構が及ばない停止を起こす可能性があります。

このディレクトリのコードには、リポジトリルートのBSD 2-Clause Licenseを適用します。第三者コードは
含みません。
