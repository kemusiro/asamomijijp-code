# Raspberry Pi Pico 2 Wクラスタ実験

Raspberry Pi 5を管理ノード、複数のRaspberry Pi Pico 2 Wを計算ノードとして、Wi-Fi経由で画像計算を並列実行する実験プロジェクトです。Mandelbrot集合と、反射・影・アンチエイリアスを含むレイトレーシングを収録しています。

掲載先：[asamomiji.jp](https://asamomiji.jp/)（関連記事は2026年9月14日時点で未公開）

## 収録内容

- `mandelbrot/`：float32 Mandelbrot計算コア、Pi 5側manager、Pico側worker、テスト
- `raytracing/`：RGB888レイトレーサー、Pi 5側manager、Pico側worker、テスト
- `raytracing/emitters/`：original、native、限定Viper、Thumbインラインアセンブラの比較
- `results/`：1～6台の実測値
- `videos/`：実機実行時のtile到着時刻から再構成した進捗動画

managerはTCPでjobとtile結果を交換し、UDPで一斉開始を通知します。workerごとの要求window、ready barrier、切断workerの未完了tile再割り当てを備えています。Picoは画像全体を保持せず、1 tileずつ計算します。

## 動作環境

実機検証に使用した主な環境は次のとおりです。

| 役割 | 環境 |
| --- | --- |
| 管理ノード | Raspberry Pi 5、Python 3.13.5 |
| 計算ノード | Raspberry Pi Pico 2 W（RP2350、ARMモード）×1～6台 |
| firmware | MicroPython 1.28.0（RPI_PICO2_W） |
| network | 外部公開しない同一LAN、TCP 8765、UDPはnodeごとの固定port |

Wi-FiのSSID、password、管理ノードのIP addressは収録していません。

## ホストテスト

リポジトリルートから実行します。外部Python packageは不要です。

```console
python3 -B -m unittest discover \
  -s projects/raspberry-pi-pico-cluster/mandelbrot/tests -v
python3 -B -m unittest discover \
  -s projects/raspberry-pi-pico-cluster/mandelbrot/network/tests -v
python3 -B -m unittest discover \
  -s projects/raspberry-pi-pico-cluster/raytracing/tests -v
```

Mandelbrotのmanagerと模擬worker 2台だけで通信を確認する例です。

```console
python3 projects/raspberry-pi-pico-cluster/mandelbrot/network/manager.py \
  --host 127.0.0.1 --workers 2 --job exhibition --tile-size 16 \
  --request-window 4 --job-id local-exhibition-1
```

別の2端末から次を1回ずつ実行します。

```console
python3 projects/raspberry-pi-pico-cluster/mandelbrot/network/mock_worker.py \
  --host 127.0.0.1 --node-id mock-pico-1
python3 projects/raspberry-pi-pico-cluster/mandelbrot/network/mock_worker.py \
  --host 127.0.0.1 --node-id mock-pico-2
```

展示jobの期待値はchecksum `1a26b685`、320 tile、payload 81,920 byteです。

## Pico側の準備

`network_config.example.py`をGit管理外の`network_config.py`へコピーし、nodeごとに`NODE_ID`と`UDP_PORT`を変えます。認証情報をGitへ追加しないでください。

```console
cp projects/raspberry-pi-pico-cluster/mandelbrot/network/network_config.example.py \
  projects/raspberry-pi-pico-cluster/mandelbrot/network/network_config.py
```

Mandelbrot workerへ必要なファイルは次の5個です。

- `mandelbrot/pico/mandelbrot_core.py`
- `mandelbrot/network/network_protocol.py`
- `mandelbrot/network/pico_worker.py`
- `mandelbrot/network/rgb_status.py`
- ローカルで作成した`network_config.py`

自動起動する場合だけ`mandelbrot/network/pico_main.py`をPico上の`main.py`として配置します。まず1台へ転送し、checksum、既知画素、soft reset後の復帰を確認してから複数台へ展開してください。

レイトレーシングworkerでは上記の共通ファイルに加えて、次を配置します。

- `raytracing/pico/raytracer_core.py`
- `raytracing/network/ray_worker.py`

REPLから1回だけ実行する場合は`import ray_worker; ray_worker.run_once()`、再接続を続ける場合は`run_forever()`を使います。

## Pi 5側での実行

Mandelbrotを6台で実行する例です。

```console
python3 -B projects/raspberry-pi-pico-cluster/mandelbrot/network/manager.py \
  --workers 6 --job exhibition --tile-size 16 --request-window 4 \
  --worker-timeout 5 --timeout 30 --job-id mandelbrot-demo-1
```

レイトレーシングを6台で実行し、PNGと動画生成用traceを保存する例です。

```console
mkdir -p recordings output
python3 -B projects/raspberry-pi-pico-cluster/raytracing/network/ray_manager.py \
  --workers 6 --preset exhibition --tile-size 16 --request-window 4 \
  --worker-timeout 5 --timeout 180 \
  --record-trace recordings/raytracing-6.json \
  --output output/raytracing-showcase.png
```

traceから実際のtile到着順と時間を再現したMP4を作成できます。動画作成には`ffmpeg`が必要です。

```console
python3 projects/raspberry-pi-pico-cluster/mandelbrot/network/render_progress_video.py \
  recordings/raytracing-6.json output/raytracing-6.mp4 \
  --fps 30 --scale 2 --speed 1 --hold 1
```

## 実測結果

### Mandelbrot（512×320、最大64反復、16×16 tile）

| node数 | E2E中央値 | 1台比speedup | 並列効率 |
| ---: | ---: | ---: | ---: |
| 1 | 29,834.725 ms | 1.000× | 100.0% |
| 2 | 14,874.854 ms | 2.006× | 100.3% |
| 3 | 9,966.117 ms | 2.994× | 99.8% |
| 4 | 7,497.681 ms | 3.979× | 99.5% |
| 5 | 6,066.971 ms | 4.918× | 98.4% |
| 6 | 5,094.576 ms | 5.856× | 97.6% |

各node数でwarm-up 1回＋測定5回を実施し、36/36回でchecksum、既知画素、320 tileが一致しました。詳細値は[`results/mandelbrot-six-node-scaling.csv`](results/mandelbrot-six-node-scaling.csv)にあります。

### レイトレーシング（320×180、RGB888、6 node）

| 方式 | E2E | original比 | 結果 |
| --- | ---: | ---: | --- |
| original bytecode | 35,052.376 ms | 基準 | 合格 |
| native | 30,249.129 ms | 13.7%短縮 | 合格・最速 |
| 限定Viper（10秒timeout） | 35,314.571 ms | 0.7%遅延 | 合格 |
| native＋inline assembler | 30,832.078 ms | 12.0%短縮 | 合格 |

完了した全方式で画像CRC32 `4278ccd8`、基準5画素、240/240 tileが一致しました。Viperの詳細と既知の停止条件は[`raytracing/emitters/README.md`](raytracing/emitters/README.md)を参照してください。

## 検証動画

[`videos/README.md`](videos/README.md)にMandelbrot 1／3／6 node、レイトレーシング1／3／6 node、およびnative版6 nodeの動画とchecksumを収録しています。動画はカメラ撮影ではなく、managerが保存した完成画像とtile到着時刻から生成した実験記録です。

Gitで動画を収録したのは、各ファイルが600 KB未満、合計約1.4 MBと小さく、ソースと同じrevisionで人間が確認できる再現結果を保持するためです。再生成可能な`.mpy`や通常の出力画像は収録しません。

## 来歴と制約

- 2026年8月10日～9月14日に`kemusiro/cho-eleki-expo-2026`で開発・実機検証した自作コードを、公開用に独立プロジェクト化しました。
- 元プロジェクト固有のWi-Fi設定、端末名、絶対path、USB device名は含めていません。
- 6 nodeまでは実機検証済みです。16 node構成の処理時間、長時間運転、障害注入は未検証です。
- managerのlocal socketを使うテストは、実行環境によってloopback通信の許可が必要です。
- native、Viper、inline assemblerの`.mpy`はMicroPython versionとCPU architectureに依存するため、Gitには収録せずsourceから生成します。
- full Viper実験は4×4 tileでhard lockし、電源再投入が必要になりました。展示や複数台実行には使用しないでください。

このプロジェクトのコードと実験動画には、リポジトリルートのBSD 2-Clause Licenseを適用します。第三者コード・第三者映像・音声は含みません。
