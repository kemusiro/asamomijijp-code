# 超エレキ万博2026：車体進化とPico分散レイトレーシング

2026年11月3日の展示用コード一式です。Pi 4の車体進化、Pico 2 Wの16台巡回描画、Pi 5の2画面表示、導入・監視・停止・復旧用script、既存テストを収録しています。

解説サイト：[asamomiji.jp](https://asamomiji.jp/)。対応記事のURLは
<https://asamomiji.jp/articles/cho-eleki-expo-2026-clusters/>（記事の公開状況はサイト側で確認してください）。

以前の[1～6台のPico実験](../raspberry-pi-pico-cluster/README.md)は別プロジェクトとして保持しています。
このディレクトリは展示版の独立したスナップショットで、以下のコマンドは**本ディレクトリを作業ルート**として実行します。

```bash
cd projects/cho-eleki-expo-2026-clusters
```

## 構成

| 場所 | 内容 |
| --- | --- |
| `projects/raspberry-pi-4-cluster/vehicle-evolution/` | Planck.jsによる2D物理、13遺伝子の進化計算、HTTP worker、ブラウザ表示、K3s manifest |
| `projects/raspberry-pi-pico-cluster/raytracing/` | 球体・車体描画、Pi 4 APIから3D模型への変換、タイル配信・集約、表示、テスト |
| `projects/raspberry-pi-pico-cluster/mandelbrot/` | 共有ネットワークprotocol・worker・RGB・watchdog、模擬worker、基礎計算とテスト |
| `projects/raspberry-pi-4-cluster/traffic-prototype/` | 予備の交通シミュレーション |
| `scripts/` | Pico巡回・USB更新・2画面・監視・正常停止・検証・インフラ導入補助 |
| `projects/raspberry-pi-4-cluster/k3s/` | K3s/NFS CSIの構成例。upstreamライセンスを保持 |

## 手元のPCで車体進化を動かす

Node.js 22以上、ブラウザが必要です。物理ライブラリを同梱しているのでnpm installやCDNは不要です。

```bash
node projects/raspberry-pi-4-cluster/vehicle-evolution/server.mjs \
  --host 127.0.0.1 --port 8090 --workers 4 \
  --course-profile obstacles-55-7p5-v1 --state-file /tmp/vehicle-demo/state.json
```

<http://127.0.0.1:8090/> を開きます。最長30秒のモデル内走行＋結果5秒表示です。探索の計算時間が30秒という意味ではありません。
停止はCtrl+C。checkpointは世代の境界で保存し、同じファイル・条件で再開できます。
画面の「最初から再計算」は保存していたランキングを初期化するため、残す結果は先に退避してください。

2個のHTTP workerで試す場合は、各コマンドを別端末で実行します。

```bash
node projects/raspberry-pi-4-cluster/vehicle-evolution/worker.mjs --port 8790 --id worker-a
node projects/raspberry-pi-4-cluster/vehicle-evolution/worker.mjs --port 8791 --id worker-b
node projects/raspberry-pi-4-cluster/vehicle-evolution/server.mjs \
  --worker-urls http://127.0.0.1:8790,http://127.0.0.1:8791 \
  --course-profile obstacles-55-7p5-v1 --state-file /tmp/vehicle-demo/http-state.json
```

## Picoを使わず車体画像を確認する

Python 3.10以上、標準ライブラリで実行できます。

```bash
python3 -B projects/raspberry-pi-pico-cluster/raytracing/host/render_vehicle.py \
  /tmp/vehicle-reference.png --preset recovery --terrain
```

これはCPythonによる参照描画です。実機速度や、Picoとの全画素ビット一致を保証するものではありません。
同梱の車体JSONは過去の実験fixtureであり、当日進行中の探索結果や最新checkpointではありません。

## 展示構成を再現する

[導入・運用手順](docs/RUNBOOK.md)に、Picoの必要ファイル、Pi 5の巡回、2画面、K3s、停止・復旧を記載しています。
実機例はPi 4×14台（管理1・ストレージ1・計算12）、Pico 2 W×16台、Pi 5×1台です。小さい構成から確認できます。

PicoはMicroPython 1.28.0（RP2350/ARM）、USB更新はmpremote 1.28.0、Pi 5側はPython 3.10以上。
2画面はRaspberry Pi OSのlabwc/Xwayland、Chromium、日本語フォントを前提とします。
K3s用の固定Node.jsイメージとNFS CSIはmanifest内の版を参照してください。OS・iSCSI/NFS・LANの準備、イメージの取得・キャッシュは別途必要です。

IP・ホスト名・NodePortは隔離LANの構成例です。実機のWi-Fi認証情報、SSH秘密鍵、ホスト鍵、K3s token、稼働ログ、個人用バックアップ、OSイメージは含みません。
設定はexampleをコピーして自分の環境で用意し、既存展示へそのまま適用しないでください。

## テストと収録時の確認

```bash
python3 -B -m unittest discover -s projects/raspberry-pi-pico-cluster/mandelbrot/tests -v
python3 -B -m unittest discover -s projects/raspberry-pi-pico-cluster/mandelbrot/network/tests -v
python3 -B -m unittest discover -s projects/raspberry-pi-pico-cluster/raytracing/tests -v
node projects/raspberry-pi-4-cluster/vehicle-evolution/test.mjs
node projects/raspberry-pi-4-cluster/vehicle-evolution/continuous-test.mjs
node projects/raspberry-pi-pico-cluster/raytracing/tests/display-state-test.mjs
python3 -B scripts/test-dual-display-kiosk.py
python3 -B scripts/test-shutdown-exhibition.py
```

通信テストはloopback socketの利用を許可した環境で実行します。実機検証scriptやsudo installerとは区別してください。
確認環境と全suite結果は[検証記録](VALIDATION.json)、元ファイルのhash・公開用変更は[SOURCE_MANIFEST.json](SOURCE_MANIFEST.json)へ記録します。
今回の公開準備では展示機器への書込み・再起動・電源操作・追加性能測定を行っていません。

## 来歴・制約・ライセンス

原コードは2026年8～10月に開発した所有者作成の展示用コードで、11月3日に公開用プロジェクトとして収録しました。
元リビジョンは `1469a66bf281ac00f78594366bc8ad29cbc8cffd`。私有リポジトリの履歴自体は公開していません。
実機のホスト鍵をダミーの設定例へ変換し、停止scriptの既定参照と、入れ子配置時のGit参照パスを調整しました。物理・進化・描画の計算コアは変更していません。

Pi 4の管理系応答停止は原因未特定です。既存の再発時診断・復旧手順で対応し、恒久対策済みとは扱いません。
Picoの40秒は目標周期で、描画完了と最低表示時間を優先するため延長します。車体の3D模型は展示用近似で、3D走行の再計算ではありません。
専用LAN用の認証なしAPIなので外部へポート公開しないでください。台数倍の高速化、PCへの性能優位、長時間無障害を保証しません。

所有者作成部分はルートの[BSD-2-Clause](../../LICENSE)。同梱Planck.jsはMIT、NFS CSI manifestはApache-2.0です。
著作権表示・許諾文と出所は[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)を参照してください。
