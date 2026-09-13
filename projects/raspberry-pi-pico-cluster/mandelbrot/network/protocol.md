# マンデルブロ複数ノード通信プロトコル v2

## 目的と範囲

`mandelbrot-wire-v2`は、Raspberry Pi 5管理ノードとPico 2 W計算ノード複数台の
通信込み検証に使用するプロトコルである。参加必須台数を起動時に固定し、全workerの
開始同期、動的タイル割り当て、TCP切断またはworker進捗停止時の未完了タイル再割り当てを扱う。

| 項目 | 値 |
| --- | --- |
| プロトコル | `mandelbrot-wire-v2` |
| 計算 | `mandelbrot-tile-float32-v2` |
| 出力 | `iterations-u8-v1` |
| 全体検査 | `row-crc32-mix-v1` |
| TCP既定ポート | 8765 |
| タイル | 暫定16×16、最大ペイロード256 B |
| 要求ウィンドウ | workerごとに既定4、設定範囲1～16 |
| worker進捗タイムアウト | 既定5秒、設定範囲0.1～300秒 |
| 全体無通信タイムアウト | 既定30秒 |
| 開始通知 | UDPユニキャスト、同一内容を3回送信 |

## 接続と処理順

PicoからPi 5へTCP接続する。Pi 5からPicoへの着信許可設定やPicoの固定IPを不要にするためである。

1. 各PicoがUDPソケットを確保し、Pi 5へTCP接続する
2. 各Pico → Pi 5：`hello`
3. Pi 5 → 各Pico：同一の`job`
4. 各Pico → Pi 5：`ready`
5. Pi 5は指定した全workerの`ready`を待つ
6. Pi 5 → 各Pico：UDP `start`を3回ずつ送る
7. Pi 5 → 各Pico：worker別ウィンドウ上限まで、共有台帳から`tile`を先行送信
8. 各Pico → Pi 5：`tile_result`と生の反復回数配列
9. Pi 5は結果を1件受信するたび、空いたworkerへ次の`tile`を1件補充する
10. workerが切断または進捗タイムアウトした場合、socketを閉じて処理中タイルを共有キューへ戻す
11. 全タイル完了後、Pi 5が下半分を復元し、検査値と既知画素を確認する
12. Pi 5 → 接続中の各Pico：`complete`

Pi 5は上半分だけをジョブ化する。512×320、16×16では640論理タイルのうち320タイルを
送る。Picoは画像全体を保持せず、256 Bの結果バッファを再利用する。Pi 5は受信時に
上側と対応する下側へ同じ行を配置する。

要求ウィンドウはメッセージ形式を変えない通信パイプラインである。Pi 5はworkerごとの
処理中要求を既定4件、最大16件に制限する。Picoは要求を1件ずつ受信、計算、送信するため
計算バッファは増えない。Pi 5は未割り当て、処理中、完了の全体台帳を持ち、結果順序には
依存しない。ウィンドウ1はworkerごとの逐次要求・応答となる。

各`tile_id`は同時には1台だけの処理中集合へ属する。切断または進捗タイムアウトを検出すると、
そのworkerを現在ジョブの割り当て対象から外し、集合を一度だけ未割り当てへ戻す。旧`job_id`、
完了済み、現在そのworkerへ割り当てていない既知タイルの結果は遅延・重複
結果として破棄し、完成数へ加えない。未知タイル、CRC不一致、寸法不一致は送信workerを異常と
みなし、そのworkerの処理中タイルを再割り当てする。

## TCPフレーム

```text
+----------------------+----------------------+------------------+
| JSON長 4 B (BE u32)  | UTF-8 JSONヘッダ     | バイナリpayload  |
+----------------------+----------------------+------------------+
```

- JSONヘッダは最大8,192 B
- ペイロードは最大65,536 B
- JSONの`payload_length`は送信時に追加される
- 受信側は指定長を受け取るまで読み続ける
- タイル結果はbase64化せず、1画素1 Bのまま送る
- TCPでは可能な環境で`TCP_NODELAY`を有効にする

## メッセージ

### `hello`

Picoのノード識別、UDPポート、4種類の版を通知する。版が1つでも異なればPi 5は拒否する。

```json
{
  "type": "hello",
  "protocol_version": "mandelbrot-wire-v2",
  "algorithm_version": "mandelbrot-tile-float32-v2",
  "output_version": "iterations-u8-v1",
  "checksum_version": "row-crc32-mix-v1",
  "node_id": "pico-01",
  "udp_port": 49152
}
```

### `job`

全体条件、タイル数、対称化方式を通知する。`job_id`は再実行ごとに変更する。

```json
{
  "type": "job",
  "job_id": "run-001",
  "job": {
    "name": "exhibition-candidate-v1",
    "xmin": -2.0,
    "xmax": 1.0,
    "ymin": -1.0,
    "ymax": 1.0,
    "width": 512,
    "height": 320,
    "max_iter": 64
  },
  "tile_size": 16,
  "tile_count": 320,
  "symmetry": "real-axis-upper-half"
}
```

実際のメッセージには4種類の版も含む。`tile_count`はジョブ全体のタイル数であり、各workerが
自分で処理すべき件数ではない。workerは`tile_count`件の受信を待たず、`complete`まで割り当て
られた`tile`だけを処理する。この終了規則がv1からv2への非互換変更である。

### `ready`とUDP `start`

`ready`はPicoがジョブを検査し、結果バッファとUDP受信を準備したことを示す。

```json
{"type":"ready","job_id":"run-001"}
```

UDP `start`は次のJSONだけで、ペイロードを持たない。3回届いても同じ`job_id`なら重複として
扱える。v1のPico実装は最初の1個を採用し、ジョブ終了時にUDPソケットを閉じて残りを破棄する。

```json
{"type":"start","protocol_version":"mandelbrot-wire-v2","job_id":"run-001"}
```

### `tile`

```json
{
  "type": "tile",
  "job_id": "run-001",
  "tile_id": 0,
  "x0": 0,
  "y0": 0,
  "width": 16,
  "height": 16
}
```

### `tile_result`

JSONに計算時間、メモリ、ペイロードCRC32を含め、直後に`width * height` Bを送る。

```json
{
  "type": "tile_result",
  "job_id": "run-001",
  "tile_id": 0,
  "x0": 0,
  "y0": 0,
  "width": 16,
  "height": 16,
  "payload_crc32": "12345678",
  "compute_ms": 42,
  "mem_free_before": 100000,
  "mem_free_min_sampled": 50000
}
```

Pi 5は`job_id`、`tile_id`、割り当てworker、座標、寸法、長さ、CRC32を照合してから配置する。
遅延・重複結果は破棄し、未知または不一致のタイルは受け入れない。

### `complete`と`error`

完成結果が期待値と一致した場合だけ、接続中の全workerへ`complete`を返す。workerは受信した
タイル数にかかわらず、これを受け取って現在のジョブを終了する。

```json
{"type":"complete","job_id":"run-001","checksum32":"1a26b685"}
```

エラー時は可能な場合に`error`を送り、TCPを閉じる。

```json
{"type":"error","job_id":"run-001","code":"manager_error","message":"..."}
```

## タイムアウト、再接続、重複

- TCP、UDPと全体無通信は既定30秒でタイムアウトする
- worker進捗タイムアウトは既定5秒、設定範囲0.1～300秒とする
- managerは単調時計を使い、workerが割り当て済みタイルの有効な結果を返すたび期限を更新する
- 他workerから結果が届いていても、各workerの期限を個別に評価する
- 要求ウィンドウはworkerごとに1～16だけを受け付け、既定4とする
- 指定した全workerが`ready`になる前の切断またはタイムアウトはジョブ失敗とする
- 開始後のTCP切断または進捗タイムアウトでは、そのworkerのsocketを閉じ、処理中タイルだけを
  接続中のworkerへ再割り当てする
- 完了済みタイルとPi 5側の途中画像は保持する
- 遅れて届いた旧`job_id`または重複結果は記録して破棄する
- 全workerが切断または進捗タイムアウトした場合、または全workerから30秒間何も届かない場合は、
  workerを復旧して新しい`job_id`で再実行する案内とともにジョブ失敗とする
- Picoは接続を閉じて3秒待ち、次の管理ジョブへ再接続する

5秒の既定値は、2026年8月10日の展示条件で観測した16×16タイル平均約65～91msに対して
50倍超である。実機では最悪タイル時間と通信揺らぎの少なくとも10倍を確保し、正常workerを
誤検出しないことを反復試験で確認する。同一ジョブへの途中参加と代替workerの新規接続は対象外である。

## セキュリティと運用上の制約

- 展示用の閉じたLANを前提とし、アプリケーション暗号化・認証はv1の対象外
- 外部インターネット接続を必要としない
- Wi-Fi SSIDとパスワードは`network_config.py`だけに置き、Gitへ追加しない
- 信頼できないLANでは使用しない
- ログへWi-Fi認証情報を出力しない
