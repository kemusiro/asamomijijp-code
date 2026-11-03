# 展示版の導入・運用

コマンドは `projects/cho-eleki-expo-2026-clusters/` を作業ルートにします。
既存機への適用前にソース・設定・checkpoint・service定義を退避し、対象機器と台数を確認してください。
以下は自分の隔離LANへ導入する手順で、展示機材に対してこの公開作業中に実行したものではありません。

## 1. Pico 2 Wを1台準備する

MicroPython 1.28.0（Pico 2 W / ARM）と `mpremote==1.28.0` を用意します。
共有設定例をローカル設定へコピーし、Wi-Fi SSID/password、Pi 5の管理IP、nodeごとのNODE_ID・UDP_PORTを設定します。

```bash
cp projects/raspberry-pi-pico-cluster/mandelbrot/network/network_config.example.py \
  projects/raspberry-pi-pico-cluster/mandelbrot/network/network_config.py
```

本番のTCPは8765。node IDは `pico-01` から順に重複しない値を使います。
新規のPicoには次のファイルを転送します。`main.py`は最後に置きます。`raytracer_core.py`は巡回routerで、球体計算コアは別名 `gallery_raytracer.py` です。

| 元ファイル（以下はprojects/raspberry-pi-pico-cluster/配下） | Pico上の名前 |
| --- | --- |
| mandelbrot/pico/mandelbrot_core.py | mandelbrot_core.py |
| mandelbrot/network/network_protocol.py | network_protocol.py |
| mandelbrot/network/pico_worker.py | pico_worker.py |
| mandelbrot/network/rgb_status.py | rgb_status.py |
| mandelbrot/network/network_config.py | network_config.py |
| raytracing/network/ray_worker.py | ray_worker.py |
| raytracing/pico/raytracer_core.py | gallery_raytracer.py |
| raytracing/pico/vehicle_raytracer.py | vehicle_raytracer.py |
| raytracing/pico/scene_raytracer.py | raytracer_core.py |
| raytracing/network/pico_main.py | main.py |

転送例（実際のUSBポートを選び、上表の各ファイルを配置）：

```bash
PICO_PORT=/dev/ttyACM0
mpremote connect "$PICO_PORT" fs cp \
  projects/raspberry-pi-pico-cluster/mandelbrot/network/network_config.py :network_config.py
```

既存の球体workerから更新する場合はrunnerを止め、`scripts/manage-pico-scene-workers.py install --help`の専用更新処理を使えます。
まず1台だけを指定し、新しい `--backup-dir` と期待node IDで退避・導入・復旧を確認します。`restore`は同じ退避先を使い、前後hash一致を確認します。
`--previous-revision`はこの公開リポジトリに存在する確認済みの40桁SHAを指定します。私有リポジトリの旧SHAはここでは参照できません。
初回公開前の展示firmwareを、履歴が同じだと仮定して更新しないでください。

## 2. Pi 5から小さい3描画を確認する

先にREADMEの車体進化サーバを起動します。別ホストならNode.jsの `--host`・URLを隔離LANへ合わせます。
Pi 5の本プロジェクトルートで実行します。

```bash
python3 -B scripts/run-pico-raytracing-exhibition.py \
  --scene-mode alternating --vehicle-api http://127.0.0.1:8090/api/state \
  --workers 1 --sphere-preset recovery --vehicle-preset recovery \
  --tile-size 8 --worker-timeout 7 --manager-timeout 120 --cycles 3 \
  --minimum-display-seconds 2 --cycle-seconds 2 --output-dir /tmp/pico-probe
```

worst→best→sphere、全タイル、node参加、保存画像・CRC・出所を確認します。APIでランキングが未取得なら、役割を警告した球体へ退避します。
正常ならnode IDとポートを分け、1台ずつ確認して16台へ広げます。USB列挙16台だけではWi-Fi参加16台を証明しません。

## 3. 16台巡回と表示

Pi 4クラスタでは車体APIの例が `http://192.168.2.1:30096/api/state` です。各自のIPとnode構成へ合わせてください。

```bash
python3 -B scripts/run-pico-raytracing-exhibition.py \
  --scene-mode alternating --vehicle-api http://192.168.2.1:30096/api/state \
  --workers 16 --vehicle-preset smooth --sphere-preset detailed \
  --worker-timeout 7 --manager-timeout 120 --minimum-display-seconds 4 \
  --cycles 0 --output-dir /tmp/pico-exhibition
```

別端末で表示サーバを起動します。

```bash
python3 -B scripts/serve-pico-raytracing-display.py \
  --host 127.0.0.1 --port 8080 --output-dir /tmp/pico-exhibition
```

<http://127.0.0.1:8080/> を開きます。車体320×180・8×8タイル・2 sample、球体480×270・16×16タイル・2 sample/2 shadow/反射1回です。
車体cycle開始時にAPIから入力を固定し、API取得失敗時は同役割の正常キャッシュ、初回未取得なら警告付き球体へ退避します。
watchdogは8秒、worker期限は7秒。40秒は周期目標で、完成後の最低4秒表示を優先します。

systemd化は、既存定義を保存し、まず `scripts/install-pico-raytracing-exhibition.sh --help` を確認します。
Pi 5のデスクトップユーザーを `--run-user` に指定し、`--repo-dir`はこのプロジェクトの絶対パスを渡します。
球体用serviceの準備後、`scripts/install-pico-scene-cycle.sh`で `--vehicle-api`・新しい `--backup-dir` を指定して巡回用drop-inを導入します。
これらはsudoでservice・ブラウザ設定を書き換える処理です。検査用ホストテストとは別操作です。

2画面はPi 5のデスクトップ端末から対象の出力名を調べ、次の例を環境に合わせて使います。重複起動を避け、最初は `--dry-run` を付けて確認します。

```bash
python3 -B scripts/start-dual-display-kiosk.py \
  --vehicle-url http://192.168.2.1:30096/ --pico-url http://127.0.0.1:8080/ \
  --vehicle-output HDMI-A-2 --pico-output HDMI-A-1 --dry-run
```

永続化は `scripts/install-dual-display-kiosk.py`。labwcのデスクトップユーザーで実行し、sudoは使いません。
片方のURLが失敗すると、配信元の応答が2回続いた時点で該当画面を再表示します。計算処理の停止は表示復旧だけでは直りません。

## 4. Pi 4のK3s配置

管理1台・計算12台がK3sに参加し、ストレージは参加しません。K3s、NFSとStorageClass、Node.js ARM64イメージのローカル準備が必要です。
`projects/raspberry-pi-4-cluster/vehicle-evolution/k8s/workload.yaml` のnode名・ラベル・PVC・イメージ固定版を確認します。
K3s導入補助は `scripts/install-k3s-node.sh`、NFSは `projects/raspberry-pi-4-cluster/k3s/nfs-csi/`。OS・iSCSI rootや資格情報の用意は各自の環境で行います。

node名がnode10～node21の場合のラベル例です。実際の対象を確認してから設定します。

```bash
sudo k3s kubectl label node node{10..21} \
  exhibition.asamomiji.jp/role=compute \
  exhibition.asamomiji.jp/vehicle-worker=enabled --overwrite
sudo bash projects/raspberry-pi-4-cluster/vehicle-evolution/deploy-k3s.sh first
# 1台から順にhealth・版・候補評価を確認して全workerをそろえてから：
sudo bash projects/raspberry-pi-4-cluster/vehicle-evolution/deploy-k3s.sh all
```

まず1台でhealth・30秒モデル・候補評価を確認します。ConfigMapが大きいのでserver-side applyを使います。
`vehicle-evolution/deploy-k3s.sh first`はcoordinator停止のまま適用し、workerを確認します。`all`で全体、`display`は表示側の更新用です。
既存状態を退避せずに適用したり、apply競合を一括で強制上書きしたりしないでください。

## 5. 停止・復旧

ローカルのcoordinator・runner・表示サーバは対象端末のCtrl+Cで停止します。checkpoint・正常キャッシュ・結果は退避して保持します。
同じ保存ファイルを複数coordinatorへ同時に書かせないでください。

クラスタ全体の正常停止は `scripts/shutdown-exhibition.py`です。
同梱の `shutdown-hosts.example.json` は**すべてダミーのホスト鍵**です。実機のホスト名・IP・ユーザー・確認済みSSHホスト鍵fingerprintを記入したローカル設定を別名で用意します。

```bash
python3 -B scripts/shutdown-exhibition.py --dry-run
python3 -B scripts/shutdown-exhibition.py \
  --config projects/raspberry-pi-4-cluster/shutdown-hosts.local.json --check
# 対象・順序・退避を確認できてから、同じ--configで--executeを実行する。
```

停止順はPicoサービス→車体・交通処理→計算12台→iSCSI/NFS接続解放→storage→mng→Pi 5です。
計算ノードが動いている間はstorageを停止しません。SSH無応答だけで給電断可能とせず、現物停止を確認します。
Pico給電・AP・スイッチ・表示器の電源はscript対象外です。

起動後は13/13 Readyを確認し、停止時に外したworkerラベルを計算12台へ戻してから、車体coordinatorを1へ戻します。
交通coordinatorは予備のため0を維持します。車体の評価進行、Pico16台の完成画像、上下表示を確認してから展示を始めます。
管理系応答停止の原因未特定という制約を引き継ぎ、診断は `scripts/monitor-pi4-management.py` と設定exampleを使います。
