# YM2203 sound module — 採用設計と再現用資料

非公式のYM2203実音源基板。独自ソースとCADはMIT（例外はTHIRD_PARTY_NOTICES.md）。

- **Rev C**：実機確認済み。回路・組立は[Rev C](hardware/ym2203-single-board/README.md)。
- **C版0.5.0-alpha.4**：[ファームウェア](firmware-c/README.md)、[常用手順](firmware-c/DAILY-USE-README.txt)、[HOSTプレーヤー](firmware-c/PLAYER-README.txt)。既存I2C HOST・USB-MIDI・STOP/leaseの動作を維持する。
- **P2 T/T/N・FAB U**：[採用設計](hardware/p2/README.md)。発注済み、HAL未移植、実機未受入。
- [MicroPythonからCへ移行した理由](docs/C-SDK-MIGRATION.md)。楽曲データや録音は配布しない。

元の公開履歴を書き換えず、採用設計と必要依存を抽出した。privateリポジトリ・旧レビュー・購入カートへのアクセスは不要。
固定ランタイムとC比較試験のため旧MicroPythonソースを一部残す。これをYs II向けの推奨常用版とは扱わない。
`provenance/`の取り込み記録は当時の履歴。現在の全件検査は`release-manifest.json`と以下の手順を使う。

## 検証

CPython、Cコンパイラー、KiCad10.0.5、Gerbonara1.6.3を使用する。

```sh
python3 tools/verify_export.py
python3 -m unittest discover -s firmware-c/tests -p 'test_*.py'
python3 -m unittest discover -s hardware/ym2203-single-board/firmware/tests -p 'test_*.py'
python3 hardware/ym2203-single-board/verify.py
python3 hardware/ym2203-single-board/firmware/build.py outputs/micropython-source.zip
```

C版115試験のうち4件は外部の楽曲を必要とし、`REVC_TEST_SONG`なしではskipする。他の試験は独自の短いテストデータで動く。
C SDK2.2.0/TinyUSB/picotoolは`firmware-c/toolchain-lock.json`、Arm GCCは10.3.1 20210824で固定する。

```sh
python3 firmware-c/tools/setup_sdk.py
python3 firmware-c/tools/build.py --output outputs/revc-c-demo.zip
```

SDK等は公開上流から取得して`.cache/`へ保存する。曲の指定なしでは独自の13秒診断音階・和音を使用する。
P2のERC/DRC、CAMの14異常注入、302参照の一般BOM、発注時Gerber ZIP再生成は[P2手順](hardware/p2/README.md)。

C版の既存実機受入記録は`firmware-c/verification/`。今回の抽出物の静的・ビルド検証を実機受入の追加とは扱わない。
対応記事：[Rev Cの回路とファームウェア](https://asamomiji.jp/articles/ym2203-revc-sound-module/)。サイトのビルドは本ソースやprivate環境から独立する。
