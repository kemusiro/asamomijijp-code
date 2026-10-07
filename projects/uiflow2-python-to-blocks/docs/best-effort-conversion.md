# 任意MicroPythonの最善努力変換

## 目的

厳密変換器が拒否するMicroPythonでも、可能な部分を通常のUiFlow2 Blockへ変換し、残りをPythonコードBlockとして
保持する。完全な意味保存は保証せず、変換による意味・動作の差をJSONとMarkdownの注記として出力する。

対象は従来どおりM5Stack Core2 v1.3、UiFlow2 V2.5.3、`v2.5.3-CORE2`、LVGLページ一つ、
M5STACK-U003／Port Aに固定する。

## 使用するBlock

M5Stack公式`uiflow-micropython`のタグ2.5.3には、次のBlockを使うサンプルがある。

- `execute_code_import`: import、補助関数・クラス定義、変換対象外のトップレベルPythonを保持
- `execute_code`: SetupまたはLoop内のPython文を保持
- `button_was_pressed`: Core2の`BtnA`／`BtnB`／`BtnC`が押された直後かを取得
- `speaker_begin`、`speaker_set_volume_percentage`、`speaker_tone`: Core2内蔵スピーカーの初期化、音量、tone
- `variables_set`／`variables_get`: 単純変数への代入と参照
- `text_convert_str`／`text_replace`: `str(...)`と文字列中のリテラル検索に使う文字列処理
- `components[].type = lvgl_page`／`lvgl_textarea`: M5UIのページとTextArea
- `lvgl_textarea_set_one_line`／`lvgl_textarea_set_text`／`lvgl_textarea_set_text_color`: TextAreaの一行表示、文字、文字色設定

根拠は公式の
[`stampc5_uwb_simple_anchor.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/stamp/uwb/stampc5_uwb_simple_anchor.m5f2)と
[`stampc5_uwb_simple_tag.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/stamp/uwb/stampc5_uwb_simple_tag.m5f2)である。
`button_was_pressed`のXML形式と`BtnA.wasPressed()`の対応は、公式の
[`udp_client_core2_example.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/software/easysocket/udp_client/udp_client_core2_example.m5f2)と
[`udp_client_core2_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/software/easysocket/udp_client/udp_client_core2_example.py)を根拠とする。
`BtnB.wasPressed()`は公式の
[`speaker2_stickcplus2_example.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/hat/speaker2/speaker2_stickcplus2_example.m5f2)と
[`speaker2_stickcplus2_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/hat/speaker2/speaker2_stickcplus2_example.py)、
`BtnC.wasPressed()`はCore2用の
[`relay2_core2_example.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/relay2/relay2_core2_example.m5f2)と
[`relay2_core2_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/relay2/relay2_core2_example.py)を根拠とする。
コードBlockの二つの公式例はファイル内部の`versionNumber`がV2.4.9で対象機種はStampC5、
最初のボタン`.m5f2`例は`versionNumber`がV2.4.1で対象機種はCore2である。BtnBの公式例は
StickC Plus2、BtnCの公式例はCore2で、いずれも名前を`button_was_pressed`の`NAME`フィールドへ保存する。
SpeakerのPythonとBlockの対応は、公式の
[`stackchan_servo_control_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/controllers/stackchan/stackchan_servo_control_example.py)と
[`stackchan_servo_control_example.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/controllers/stackchan/stackchan_servo_control_example.m5f2)を根拠とする。
`str(...)`は公式の
[`cores3_m5ui_table_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/table/cores3_m5ui_table_example.py)と
[`cores3_m5ui_table_example.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/table/cores3_m5ui_table_example.m5f2)にある`text_convert_str`を根拠とする。
`M5Page`と`M5TextArea`の部品構造は公式の
[`cores3_buttonmatrix_basic_example.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/buttonmatrix/cores3_buttonmatrix_basic_example.py)と
[`cores3_buttonmatrix_basic_example.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/m5ui/buttonmatrix/cores3_buttonmatrix_basic_example.m5f2)を根拠とする。
`M5TextArea.set_text_color`の引数の意味は公式ランタイムの
[`base.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/m5ui/base.py)と
[`textarea.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/m5ui/textarea.py)を根拠とする。
2026-09-28にUiFlow2 V2.5.3のCore2プロジェクトでTextAreaを配置し、`lvgl_textarea_set_text_color`の
Blockly XMLと、`set_text_color(色, 255, lv.PART.MAIN | lv.STATE.DEFAULT)`のPython生成を確認した。
2026-09-28にUiFlow2 V2.5.3でCore2を選択したWeb IDEを確認し、Systemカテゴリに
`Execute mpy code (e.g. import ...)`と`Execute mpy code`が表示されることを確認した。
TextArea文字色の最小BlockはWeb IDEで確認済みだが、最善努力変換器が生成した
[`results/count-three.m5f2`](../results/count-three.m5f2)全体のImport、Python再生成、実機実行は未確認である。

実装済みと検証済みを区別した一覧は[現在仕様・対応状況](current-status.md)に記載する。

独自のBlockly型をXMLへ追加するだけでは、UiFlow2 Web IDE側に表示定義とPython生成器がないため編集できない。
この試作では新しい非公式Block型を作らず、公式のコードBlockをフォールバックとして使う。
Web IDEには`Custom (Alpha)`のBlock Designerもあるが、生成物へ定義を保存・配布する形式と互換性仕様を
公式資料から確定できていない。移植できない独自Blockを埋め込むより、V2.5.3で表示される公式Blockを優先した。

## global変数の表現

UiFlow2のBlockly側には、Pythonの`global`文に対応する独立したBlockは見つかっていない。ワークスペース変数は
`blockly` XML先頭の`<variables>`で名前とIDを宣言し、`variables_set`と`variables_get`が同じIDを参照する。

```xml
<variables>
  <variable id="variable_count">count</variable>
</variables>
<block type="variables_set">
  <field name="VAR" id="variable_count">count</field>
  <!-- VALUE -->
</block>
```

公式の`cores3_m5ui_table_example.m5f2`と対になる生成Pythonを照合すると、UiFlow2はこの情報から
モジュール先頭の`count = None`に相当する宣言と、`setup()`／`loop()`内の`global count`を自動生成する。
ページやUI部品も同様に、外側JSONの`components`とBlockからグローバル名を導出する。

したがって最善努力変換器は、Setup／Loopで代入・参照する名前の`global`文を省略し、通常の変数Blockまたは
`components`へ変換する。UiFlow2生成Pythonにある重複したトップレベル初期宣言も、同じSetup初期値へ変換できる
場合は`execute_code_import`へ残さない。対象外の動的な名前操作、補助関数固有のスコープ、`nonlocal`はこの
正規化の対象外であり、コードBlockへ保持する。

## 変換戦略

`best_effort.py`は次の順で変換する。

1. 既存の厳密変換を試す。
2. 成功すればSleepとRGBを通常Blockとして出力する。
3. 失敗しても、引数なしの`setup()`と`loop()`があればハイブリッド変換を行う。
4. Setup／Loop内の既知のSleepとRGBは通常Blockへ変換する。
5. `BtnA.wasPressed()`、`BtnB.wasPressed()`、`BtnC.wasPressed()`は条件式用の専用Blockへ変換する。
6. 対応するSpeaker呼び出しは専用Blockへ変換する。
7. 対応する`M5Page`と`M5TextArea`コンストラクターは`components`へ変換する。
8. TextAreaの対応操作は専用Blockへ変換する。
9. 変数とUI部品に対応する`global`文、重複するトップレベル初期宣言をUiFlow2側の自動生成へ正規化する。
10. `import M5`、`from M5 import *`、`import m5ui`、`import lvgl as lv`は固定プロファイルが再生成するため省略する。
11. すべての参照先を部品属性または値Blockへ変換できたリテラル定数は、参照先へ値を埋め込んで宣言を省略する。
12. モジュールdocstringはBlockにせず注記へ移す。
13. その他の文は`execute_code`へ変換する。
14. 未知のimport、補助関数、未変換コードから参照される定数などは`execute_code_import`へまとめる。
15. `setup()`／`loop()`が見つからない場合は、ソース全文を一つの`execute_code_import`へ格納する。

構文エラーでASTを作れないPythonだけは変換できない。

## 制御構文

`setup()`と`loop()`の中では、次の構文を入れ子2段まで通常Blockへ変換する。

| Python | UiFlow2 Block |
| --- | --- |
| `if`／`elif`／`else` | `controls_if` |
| `while 条件` | `controls_whileUntil` |
| `for i in range(N)` | `controls_for_range` |
| `for i in range(start, stop[, step])` | `controls_for` |
| `for item in iterable` | `controls_forEach` |
| 単純変数の代入・複合代入 | `variables_set`／`variables_get`と演算Block |
| 比較、`and`、`or`、`not` | `logic_compare`／`logic_operation`／`logic_negate` |
| 四則演算、べき乗、剰余 | Math Block |
| `BtnA/B/C.wasPressed()` | `button_was_pressed` |
| `Speaker.begin()` | `speaker_begin` |
| `Speaker.setVolumePercentage(0.0..1.0)` | `speaker_set_volume_percentage` |
| `Speaker.tone(周波数, ミリ秒)` | `speaker_tone` |
| `変数 = str(対応式)` | `variables_set`＋`text_convert_str` |
| `"文字列" in 変数`／`not in` | `text_replace`前後の比較による真偽値Block |
| `変数 = m5ui.M5Page(...)` | `components`の`lvgl_page` |
| `変数 = m5ui.M5TextArea(...)` | `components`の`lvgl_textarea` |
| `textarea.set_one_line(...)` | `lvgl_textarea_set_one_line` |
| `textarea.set_text(...)` | `lvgl_textarea_set_text` |
| `textarea.set_text_color(色, lv.OPA.COVER, lv.PART.MAIN \| lv.STATE.DEFAULT)` | `lvgl_textarea_set_text_color` |

一番外側の制御構文を深さ1、その本体中の制御構文を深さ2と数える。`elif`は同じ`if`の枝なので
深さを増やさない。深さ3へ到達した時点で、その制御構文と子孫全体を一つの`execute_code`へ格納する。

次は深さ2以内でも制御構文全体を`execute_code`へ格納する。

- `for ... else`、`while ... else`
- `async for`、内包表記
- タプルなどへの複数代入を伴う反復
- 0または動的なstepを持つ`range()`
- `BtnA/B/C.wasPressed()`以外の関数呼び出し、添字、属性参照など、対応外の式を条件または反復対象に使う構文
- `try`、`with`、`match`など、今回の対象外構文

`break`と`continue`、通常Block化していない関数呼び出しなどは、対応する制御Blockの本体に
`execute_code`として残す。コードBlockが生成されるたびに、行番号、理由、意味・動作の差を注記する。

## 注記レポート

`.m5f2`と同時に次を生成する。

- `<出力名>.notes.json`: ツール処理用の機械可読レポート
- `<出力名>.notes.md`: 人が確認する注記

注記には次を含む。

- 使用した戦略
- 元ソースのSHA-256
- 通常Block、コードBlock、置換・省略したASTノードの数
- 元の行番号と桁番号
- 対象コード
- 何へ変換したか
- どの意味・動作が変わり得るか
- 全体に適用される制約

通常Block、部品、プロファイル生成だけで表現でき、コードBlockが一つも残らない場合の戦略名は
`best-effort-native`とする。コードBlockが一つ以上残る場合は`hybrid-native-and-raw`とする。

注記を`.m5f2`へ独自フィールドとして埋め込まない。未知のトップレベル項目でWeb IDE互換性を損なわないため、
サイドカーファイルとして管理する。

## 代表的な差

| 状況 | 出力 | 起こり得る差 |
| --- | --- | --- |
| 厳密対応できるSleep/RGB | 通常Block | 固定プロファイルの初期化と配置へ正規化 |
| Setup／Loop内の未知文 | `execute_code` | BlockとしてはPython文字列編集。コメントと書式を失う場合がある |
| 深さ1・2の対応制御構文 | 通常の制御Block | Block ID、配置、式の分割方法を正規化 |
| `BtnA/B/C.wasPressed()` | `button_was_pressed` | 呼び出しをCore2の標準ボタン名へ正規化 |
| 対応するSpeaker呼び出し | Speaker専用Block | 音量の0.0～1.0をBlock上の0～100へ換算 |
| 対応するM5UIコンストラクター | `components`の編集可能なUI部品 | ID、layer、createTimeを再生成 |
| TextAreaの既定状態の文字色変更 | `lvgl_textarea_set_text_color` | 色はRGB888、不透明度は0～255へ正規化 |
| 対応変数・部品の`global`文 | `<variables>`または`components`からUiFlow2が再生成 | 明示文の位置と名前の並び順は維持しない |
| 固定プロファイルの既知import | UiFlow2が自動生成 | importの表記と並び順を再生成 |
| 変換済み箇所だけで使うリテラル定数 | 部品属性または値Blockへインライン化 | 生成Pythonでは変更可能なモジュール変数として残らない |
| モジュールdocstring | 注記へ移して省略 | 生成Pythonの`__doc__`は元の文字列を保持しない |
| 深さ3以上の制御構文 | 構文全体を`execute_code` | その部分は個別Blockとして編集できない |
| 対応外の条件式を持つ制御構文 | 構文全体を`execute_code` | 条件と本体を個別Blockとして編集できない |
| 未知のimport・補助関数・未変換コードが使う定数 | `execute_code_import` | 生成importとの順序や名前衝突が変わり得る |
| 独自のmain処理 | 固定UiFlow2 mainへ置換 | 例外処理、終了条件、呼び出し順が変わり得る |
| Setup／Loopがないスクリプト | ソース全文をコードBlock化 | UiFlow2の固定setup／loopも生成され、到達性や名前解決が変わり得る |
| Core2以外のAPI | Pythonコードとして保持 | 対象実機にAPIやデバイスがなく実行時エラーになる場合がある |

## 実行

```sh
python3 best_effort.py examples/arbitrary-micropython.py /tmp/arbitrary.m5f2
```

次の三ファイルが作られる。

```text
/tmp/arbitrary.m5f2
/tmp/arbitrary.notes.json
/tmp/arbitrary.notes.md
```

既存ファイルは上書きしない。入力Pythonは実行せず、`ast.parse`とXML生成だけを行う。

## 保証しないこと

- 任意のMicroPythonがCore2で実行できること
- PythonとBlockの完全な意味一致
- import時の副作用、割り込み、非同期処理、スレッドの順序
- 例外の型、発生位置、終了動作
- グローバルとローカルの完全なスコープ保存
- コメント、空白、元の書式
- コードBlock内を通常Blockとして編集できること
- Core2に存在しない機器やモジュールの代替

変換成功は「UiFlow2プロジェクトを生成できた」ことを示し、同じ動作を保証しない。
必ず注記レポートと、UiFlow2の再生成Python、実機試験結果を合わせて確認する。
