# UiFlow2 2.5.3公式ソースの参照記録

## 固定した一次資料

- リポジトリ: <https://github.com/m5stack/uiflow-micropython>
- タグ: [`2.5.3`](https://github.com/m5stack/uiflow-micropython/tree/2.5.3)
- コミット: [`50e440780492aa847378c7d3477ab912f7063bac`](https://github.com/m5stack/uiflow-micropython/commit/50e440780492aa847378c7d3477ab912f7063bac)
- ライセンス: [MIT](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/LICENSE)

対象ファイルと取得内容のSHA-256は[`profile.json`](../profile.json)へ記録した。第三者コードはこのプロジェクトへ複製せず、固定URL、ハッシュ、そこから読み取った仕様だけを保持する。

## 変換プロファイルへ採用した仕様

| 根拠 | 採用した内容 |
| --- | --- |
| [`m5stack/libs/unit/rgb.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/unit/rgb.py) | 実行時クラスは`RGBUnit`、基底は`SK6812`。コンストラクターはポート配列の2番目をデータGPIOとして渡す |
| [`rgb_core.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.py) | 公式例の初期化は`RGBUnit((36, 26), 3)`。`set_brightness`、`fill_color`、`set_color`の呼び出しを確認 |
| [`rgb_core.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.m5f2) | 標準ポートは`portType: B`。上記3メソッドに対応するブロック型とフィールド構造を確認 |
| [`docs/source/unit/rgb.rst`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/unit/rgb.rst) | 輝度は0〜100、色はRGB888。RGB UnitのLED数はコンストラクター引数で指定 |

公式例に基づく標準接続はPORT.B、GPIOは`(36, 26)`である。今回の変換プロファイルは、Core2 v1.3本体側面へ接続してWeb IDEと実機で確認したPORT.A、GPIO`(33, 32)`を使用する。標準接続と検証対象の接続を混同しない。

## 公式ソースだけでは決められない範囲

このリポジトリはデバイス側MicroPythonランタイム、文書、サンプルを公開している。UiFlow2 Web IDEのBlockly定義、Python生成器、`.m5f2`の完全なスキーマは含まれていない。

タグ`2.5.3`にある`rgb_core.m5f2`の内部は`"version": "V2.0"`で、`versionNumber`を持たない。そのため、公式例はRGB APIとブロック対応の一次資料に使い、V2.5.3の保存JSON、Core2固有の初期化、PORT.A設定についてはWeb IDEから採取した[`fixtures/06-port-a.m5f2`](../fixtures/06-port-a.m5f2)と往復結果を根拠にする。

公式例に存在する`set_brightness`と`set_color`は`profile.json`へ記録したが、現在の変換器ではまだ生成しない。V2.5.3 Web IDEでブロックを採取し、読み込み、Python再生成、編集を確認してから対応範囲へ加える。
