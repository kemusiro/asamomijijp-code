# UiFlow2 2.5.3公式ソースの参照記録

## 固定した一次資料

- リポジトリ: <https://github.com/m5stack/uiflow-micropython>
- タグ: [`2.5.3`](https://github.com/m5stack/uiflow-micropython/tree/2.5.3)
- コミット: [`50e440780492aa847378c7d3477ab912f7063bac`](https://github.com/m5stack/uiflow-micropython/commit/50e440780492aa847378c7d3477ab912f7063bac)
- ライセンス: [MIT](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/LICENSE)

対象ファイルと取得内容のSHA-256は[`profile.json`](../profile.json)へ記録した。第三者コードはこのプロジェクトへ複製せず、固定URL、ハッシュ、そこから読み取った仕様だけを保持する。

## 変換プロファイルへ採用した仕様

### RGB Unit

| 根拠 | 採用した内容 |
| --- | --- |
| [`m5stack/libs/unit/rgb.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/unit/rgb.py) | 実行時クラスは`RGBUnit`、基底は`SK6812`。コンストラクターはポート配列の2番目をデータGPIOとして渡す |
| [`rgb_core.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.py) | 公式例の初期化は`RGBUnit((36, 26), 3)`。`set_brightness`、`fill_color`、`set_color`の呼び出しを確認 |
| [`rgb_core.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.m5f2) | 標準ポートは`portType: B`。上記3メソッドに対応するブロック型とフィールド構造を確認 |
| [`docs/source/unit/rgb.rst`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/unit/rgb.rst) | 輝度は0〜100、色はRGB888。RGB UnitのLED数はコンストラクター引数で指定 |

公式例に基づく標準接続はPORT.B、GPIOは`(36, 26)`である。今回の変換プロファイルは、Core2 v1.3本体側面へ接続してWeb IDEと実機で確認したPORT.A、GPIO`(33, 32)`を使用する。標準接続と検証対象の接続を混同しない。

### ボタン

| 根拠 | 採用した内容 |
| --- | --- |
| [`docs/source/hardware/button.rst`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/button.rst) | Core2は`BtnA`、`BtnB`、`BtnC`を持ち、`wasPressed()`などの状態取得APIを提供する |
| [`speaker2_stickcplus2_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/hat/speaker2/speaker2_stickcplus2_example.py)と[`.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/hat/speaker2/speaker2_stickcplus2_example.m5f2) | `BtnA.wasPressed()`／`BtnB.wasPressed()`と`button_was_pressed`の対応、ボタン名を`NAME`フィールドへ保存する形式 |
| [`relay2_core2_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/relay2/relay2_core2_example.py)と[`.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/relay2/relay2_core2_example.m5f2) | Core2上の`BtnA.wasPressed()`／`BtnC.wasPressed()`と同じBlock型の対応 |

BtnBの例はStickC Plus2、BtnCの例はCore2である。共通Block型と`NAME`の保存規則の根拠には使うが、
BtnA/B/Cを含む変換結果のCore2実機検証は別途必要である。

### Speaker

| 根拠 | 採用した内容 |
| --- | --- |
| [`docs/source/hardware/speaker.rst`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/speaker.rst) | 内蔵SpeakerのAPI |
| [`stackchan_servo_control_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/controllers/stackchan/stackchan_servo_control_example.py)と[`.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/controllers/stackchan/stackchan_servo_control_example.m5f2) | `Speaker.begin()`、`setVolumePercentage()`、`tone()`と専用Blockの対応 |

現在は上記三つを生成する。XML構造と音量の値変換は自動テスト済みだが、変換器出力のWeb IDE往復と
Core2実機での発音は未確認である。

### 変数、文字列、画面部品

| 根拠 | 採用した内容 |
| --- | --- |
| [`cores3_m5ui_table_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/table/cores3_m5ui_table_example.py)と[`.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/table/cores3_m5ui_table_example.m5f2) | `str(...)`と`text_convert_str`の対応、`<variables>`と`variables_set`／`variables_get`からトップレベル変数と関数内`global`を生成する形 |
| [`examples/module/llm/tts.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/module/llm/tts.m5f2) | `text_replace`のXML形式 |
| [`cores3_buttonmatrix_basic_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/buttonmatrix/cores3_buttonmatrix_basic_example.py)と[`.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/buttonmatrix/cores3_buttonmatrix_basic_example.m5f2) | `M5Page`／`M5TextArea`と`components`の`lvgl_page`／`lvgl_textarea`構造 |
| [`m5stack/libs/m5ui/base.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/m5ui/base.py)と[`textarea.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/m5ui/textarea.py) | `set_text_color`の色、不透明度、part/state引数と、TextArea初期文字色の実装 |

UIの公式サンプル対はCoreS3用であるため、部品構造とPython生成規則の候補として使った。2026-09-28に
Core2を選択したUiFlow2 V2.5.3でTextArea文字色Blockを別途作成し、`lvgl_textarea_set_text_color`と
`set_text_color(色, 255, lv.PART.MAIN | lv.STATE.DEFAULT)`の生成を確認した。

### PythonコードBlock

公式タグ2.5.3の[`stampc5_uwb_simple_anchor.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/stamp/uwb/stampc5_uwb_simple_anchor.m5f2)と
[`stampc5_uwb_simple_tag.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/stamp/uwb/stampc5_uwb_simple_tag.m5f2)には、
importや補助定義を保持する`execute_code_import`と、関数内の文を保持する`execute_code`がある。
該当`.m5f2`の`versionNumber`はV2.4.9で機種も異なるため、
2026-09-28にCore2／V2.5.3のWeb IDEで両BlockがSystemカテゴリに存在することも確認した。
変換器が生成したコードBlock入り`.m5f2`のImportとPython再生成は未確認である。

## 公式ソースだけでは決められない範囲

このリポジトリはデバイス側MicroPythonランタイム、文書、サンプルを公開している。UiFlow2 Web IDEのBlockly定義、Python生成器、`.m5f2`の完全なスキーマは含まれていない。

タグ`2.5.3`にある`rgb_core.m5f2`の内部は`"version": "V2.0"`で、`versionNumber`を持たない。そのため、公式例はRGB APIとブロック対応の一次資料に使い、V2.5.3の保存JSON、Core2固有の初期化、PORT.A設定についてはWeb IDEから採取した[`fixtures/06-port-a.m5f2`](../fixtures/06-port-a.m5f2)と往復結果を根拠にする。

公式例に存在する`set_brightness`と`set_color`は`profile.json`へ記録したが、現在の変換器ではまだ生成しない。V2.5.3 Web IDEでブロックを採取し、読み込み、Python再生成、編集を確認してから対応範囲へ加える。

CoreS3やStickC Plus2のサンプル、V2.4.xの`.m5f2`は、API名とBlock型の候補には使うが、Core2／V2.5.3の
保存形式を保証するものではない。現在の根拠と検証段階の対応は[現在仕様・対応状況](current-status.md)にまとめる。
