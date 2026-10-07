# VS CodeからUiFlow2 Web IDEまでの自動化

## 目的

VS CodeなどのエディターでMicroPythonを保存した後、UiFlow2へ渡す`.m5f2`と注記を自動更新する。
変換成功時は`.m5f2`の絶対パスをクリップボードへコピーし、必要ならUiFlow2 Web IDEも開く。

## 一回だけ変換する

プロジェクトディレクトリで次を実行する。

```sh
python3 workflow.py /path/to/main.py \
  --output-dir build \
  --copy-path \
  --open-uiflow
```

`main.py`の場合、次のファイルを生成または更新する。

```text
build/main.m5f2
build/main.notes.json
build/main.notes.md
build/main.ready.json
```

`ready.json`は全成果物の書き込みが完了したことを示す。元ソース、SHA-256、プロファイル、変換戦略、
警告数、各成果物の絶対パスを記録する。

変換戦略は`strict-native`、`best-effort-native`、`hybrid-native-and-raw`、`whole-module-raw`のいずれかである。
意味と現在の対応状況は[現在仕様・対応状況](current-status.md)を参照する。たとえば
[`examples/count-three.py`](../examples/count-three.py)は、現在`best-effort-native`としてコードBlockなしで変換できる。

## 保存を監視する

```sh
python3 workflow.py /path/to/main.py \
  --output-dir build \
  --watch \
  --copy-path \
  --open-uiflow
```

起動直後に一度変換し、その後はファイルの更新日時またはサイズが変わるたびに再変換する。
出力は一時ファイルへ書いてから置換するため、UiFlow2へ途中まで書かれたJSONを渡さない。

変換エラー時は最後に成功した`.m5f2`を残し、`build/main.error.txt`へエラーを記録する。
次の保存で変換に成功するとエラーファイルを削除する。

`Ctrl+C`で監視を終了する。

## VS Codeタスク

このプロジェクトディレクトリをVS Codeでフォルダーとして開く。変換するPythonをアクティブにして、
`Terminal`→`Run Task...`から次のどちらかを実行する。

- `UiFlow2: Convert active Python`: 一回変換して`.m5f2`のパスをコピー
- `UiFlow2: Watch active Python`: 保存監視、パスコピー、UiFlow2を開く

タスク定義は[`.vscode/tasks.json`](../.vscode/tasks.json)にある。成果物はプロジェクト内の`build/`へ置き、
Git管理から除外する。

## UiFlow2での読み込み

macOSでは変換成功のたびに`.m5f2`の絶対パスがクリップボードへ入る。

1. UiFlow2の`Import project from local file`を選ぶ。
2. ファイル選択画面で`Command+Shift+G`を押す。
3. パスを貼り付けてEnterを押す。
4. 選択を確定する。

通常のWebページはブラウザの保護により、ユーザー操作なしで任意のローカルファイルを選択できない。
UiFlow2 V2.5.3には文書化されたプロジェクトImport APIも確認できていない。このため標準構成では、
ファイル選択の確定だけを手動操作として残す。

Playwright、ブラウザ拡張、macOSのアクセシビリティ操作を使えば選択操作も自動化できるが、
UiFlow2のDOM変更、ブラウザプロファイル、OS権限に依存する。変換器本体とは分離して扱う。

## オプション

| オプション | 内容 |
| --- | --- |
| `--output-dir DIR` | 出力先。既定値は`build` |
| `--name NAME` | 成果物のベース名を変更 |
| `--watch` | 入力ファイルを継続監視 |
| `--interval SECONDS` | 監視間隔。既定値は0.4秒、最小0.1秒 |
| `--copy-path` | `.m5f2`の絶対パスをクリップボードへコピー |
| `--open-uiflow` | UiFlow2 Web IDEを既定ブラウザで開く |

`--copy-path`の自動実装対象はmacOSとWindowsである。変換は入力Pythonを実行せず、既存の
最善努力変換器を呼び出す。
