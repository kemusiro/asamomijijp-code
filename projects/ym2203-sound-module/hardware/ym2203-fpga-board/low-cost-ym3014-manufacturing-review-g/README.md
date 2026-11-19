# review F 製造・購入資料 G

2026-11-19。配線済み[review F](../low-cost-ym3014-pcb-review-f/README.md)から製造用データを生成した。Fの回路図・PCB・GPIOは変更せず保存。裸基板は3種類各5枚、実装部品は1セット分、すべて手ハンダ。YM2203CはRev Cから流用、YM3014B-Fは支給品とする。

| 基板 | 外形 / 層数 | 注文数量 | ローカル生成ZIP |
| --- | --- | ---: | --- |
| ベース | 100×100mm / 4層 | 5枚 | [Gerber](local-output/p2-base-f-5pcs-gerber.zip) |
| YM2203音源 | 100×80mm / 2層 | 5枚 | [Gerber](local-output/p2-module-f-5pcs-gerber.zip) |
| I2C音色編集パネル | 100×76mm / 2層 | 5枚 | [Gerber](local-output/p2-panel-f-5pcs-gerber.zip) |

ZIP・XLSXはGit管理外の`local-output/`に生成する。GitにはGerber/Excellon/JSON/CSV/SVGと再生成ツールを残す。公開Releaseや注文は行っていない。

- [発注条件](ORDERING.md)：鉛フリーHASL・1.6mm・標準ビア。ベース4層、他2層。
- [購入・組立](PURCHASING.md) / [購入用CSV](purchase-plan.csv) / [購入用JSON](purchase-plan.json)
- [送料込み見積](COST.md)：商品・送料約25,603円、予備費2,500円を含め**約28,103円**。目標30,000円。
- [検証記録](VALIDATION.md) / [CAM照合](cam-verification.json) / [製造ファイルSHA-256](manufacturing-manifest.json)
- [ローカル生成購入表](local-output/outputs/review-g/purchase-plan.xlsx)：数量・包装・余り・税込単価・送料を計算する2シート。

3枚ともネイティブERC/DRC・未接続・回路図差異0件。CAMの外形、銅層構成、全ドリル/長穴がKiCadと一致した。P2実機受入やファームウェア移植の完了を意味しない。価格は公開ページと手入力のPCBシミュレーターによる概算で、最終カート/製造者のGerber審査は未実施。在庫と保存価格の確認残りは購入表で明示する。

## 維持するインターフェース

G40全40端子、ADC・I2S入力・DACを維持。FM=37番、SSG=39番のアナログ入力をベースで合成する。YM3014通常プロファイルでは同じFMのI2S寄与を0、TX_DISABLEをHIGHとし二重加算しない。既存HOST I2C v2（0x42/100kHz）、USB-MIDI、STOP/リース/USB切断の安全停止契約はFから変更しない。新P2への実装・実機確認は別工程。

## 再生成

KiCad CLI 10.0.5、KiCad同梱pcbnew Python 3.9.13、Gerbonara 1.6.3を使用。以下の`PCB_PYTHON`と`CAM_PYTHON`は各環境の実行ファイルへ置き換える。

```sh
python3 tools/build_manufacturing.py --pcb-python "$PCB_PYTHON" --cam-python "$CAM_PYTHON"
"$CAM_PYTHON" tools/test_cam.py .
python3 tools/verify_purchase.py .
```

購入表は`purchase-plan.json`を正本入力とし、`@oai/artifact-tool`を使う`tools/build_purchase.mjs`からCSVとXLSXを生成する。Codexのbundled runtimeで動作確認。依存パッケージはリポジトリへコピーしない。
