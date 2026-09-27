# 任意MicroPythonの最善努力変換

## 目的

厳密変換器が拒否するMicroPythonでも、可能な部分を通常のUiFlow2 Blockへ変換し、残りをPythonコードBlockとして
保持する。完全な意味保存は保証せず、変換による意味・動作の差をJSONとMarkdownの注記として出力する。

対象は従来どおりM5Stack Core2 v1.3、UiFlow2 V2.5.3、`v2.5.3-CORE2`、page0、
M5STACK-U003／Port Aに固定する。

## 使用するBlock

M5Stack公式`uiflow-micropython`のタグ2.5.3には、次のBlockを使うサンプルがある。

- `execute_code_import`: import、グローバル、関数・クラス定義などトップレベルPythonを保持
- `execute_code`: SetupまたはLoop内のPython文を保持

根拠は公式の
[`stampc5_uwb_simple_anchor.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/stamp/uwb/stampc5_uwb_simple_anchor.m5f2)と
[`stampc5_uwb_simple_tag.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/stamp/uwb/stampc5_uwb_simple_tag.m5f2)である。
これらは公式タグ2.5.3に含まれるが、ファイル内部の`versionNumber`はV2.4.9、対象機種はStampC5である。
2026-09-28にUiFlow2 V2.5.3でCore2を選択したWeb IDEを確認し、Systemカテゴリに
`Execute mpy code (e.g. import ...)`と`Execute mpy code`が表示されることを確認した。
この試作が生成した`.m5f2`のImport、Python再生成、実機実行は未確認である。

独自のBlockly型をXMLへ追加するだけでは、UiFlow2 Web IDE側に表示定義とPython生成器がないため編集できない。
この試作では新しい非公式Block型を作らず、公式のコードBlockをフォールバックとして使う。
Web IDEには`Custom (Alpha)`のBlock Designerもあるが、生成物へ定義を保存・配布する形式と互換性仕様を
公式資料から確定できていない。移植できない独自Blockを埋め込むより、V2.5.3で表示される公式Blockを優先した。

## 変換戦略

`best_effort.py`は次の順で変換する。

1. 既存の厳密変換を試す。
2. 成功すればSleepとRGBを通常Blockとして出力する。
3. 失敗しても、引数なしの`setup()`と`loop()`があればハイブリッド変換を行う。
4. Setup／Loop内の既知のSleepとRGBは通常Blockへ変換する。
5. その他の文は`execute_code`へ変換する。
6. import、グローバル、補助関数などは`execute_code_import`へまとめる。
7. `setup()`／`loop()`が見つからない場合は、ソース全文を一つの`execute_code_import`へ格納する。

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

一番外側の制御構文を深さ1、その本体中の制御構文を深さ2と数える。`elif`は同じ`if`の枝なので
深さを増やさない。深さ3へ到達した時点で、その制御構文と子孫全体を一つの`execute_code`へ格納する。

次は深さ2以内でも制御構文全体を`execute_code`へ格納する。

- `for ... else`、`while ... else`
- `async for`、内包表記
- タプルなどへの複数代入を伴う反復
- 0または動的なstepを持つ`range()`
- 関数呼び出し、添字、属性参照など、対応外の式を条件または反復対象に使う構文
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

注記を`.m5f2`へ独自フィールドとして埋め込まない。未知のトップレベル項目でWeb IDE互換性を損なわないため、
サイドカーファイルとして管理する。

## 代表的な差

| 状況 | 出力 | 起こり得る差 |
| --- | --- | --- |
| 厳密対応できるSleep/RGB | 通常Block | 固定プロファイルの初期化と配置へ正規化 |
| Setup／Loop内の未知文 | `execute_code` | BlockとしてはPython文字列編集。コメントと書式を失う場合がある |
| 深さ1・2の対応制御構文 | 通常の制御Block | Block ID、配置、式の分割方法を正規化 |
| 深さ3以上の制御構文 | 構文全体を`execute_code` | その部分は個別Blockとして編集できない |
| 対応外の条件式を持つ制御構文 | 構文全体を`execute_code` | 条件と本体を個別Blockとして編集できない |
| import・補助関数・グローバル | `execute_code_import` | 生成importとの順序や名前衝突が変わり得る |
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
