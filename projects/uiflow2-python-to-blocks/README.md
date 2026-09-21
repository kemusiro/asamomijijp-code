# UiFlow2 Python→ブロック簡易変換（実証版）

2026-09-21作成。UiFlow2 V2.5.3、Core2 v1.3、Unit RGB（M5STACK-U003）を対象とする。
任意のPythonやUiFlow2生成Python全体を逆変換するものではない。
独自ラッパーAPIを作らず、既存メソッドを使う小さな入力言語を採用した。

対応記事は `asamomijijp-site/src/content/articles/drafts/uiflow2-python-to-blocks.md`。
記事URL・公開コードの固定コミットは未確定。公開前に相互リンクを確定する。

## 現状

- ASTによる静的解析、XML生成、自動テスト8件: 成功。
- 実際のWeb IDEで入力例→.m5f2読み込み→Python再生成: 成功。
- 読み込んだSetupのSleep 2を3へ編集し、time.sleep(3)への再生成: 成功。
- PORT.A版のUiFlow2読み込み、編集可能なブロックの復元、`RGBUnit((33, 32), 3)`のPython再生成: 成功。
- M5Stack Core2 v1.3／Unit RGB（M5STACK-U003）／UiFlow2ファームウェア`v2.5.3-CORE2`の実機実行: **未検証**。Core2本体側面へ直接接続するPORT.A版を実機確認に使う。
- 詳しい再現手順・保存形式対応表・未検証事項: [調査記録](results/research-2026-09-21.md)。

## 実行

検証環境: macOS、Python 3.14.6（標準ライブラリのみ）。他のPython版は未検証。
このディレクトリをカレントディレクトリにする。

```sh
python3 -m unittest discover -s tests -v
python3 convert.py examples/blink.py /tmp/blink-new.m5f2
```

出力先は新しいファイル名を指定する。既存ファイルは上書きしない。
Web IDEのフォルダーメニュー→Import project from local fileで出力を開く。
実機への書き込みは行わず、Blocks／Splitで構造と生成Pythonを確認する。

## 入力契約

`import time`と、引数のない`setup`／`loop`定義を一つずつ書く。
各本体は`time.sleep(整数)`または`rgb_0.fill_color(整数)`の呼び出し列。
空本体は単独の`pass`。コメントは構文解析時に失われる。
待機は0〜86400の整数秒、色は0〜0xffffff。これらは実証版の受付範囲であり、UiFlow2や機器の全制約を表すものではない。
デモで往復確認した色は赤、緑(#33ff33)、黒。全色・全待機値は未検証。

代入、別名import、関数再定義、引数、デコレーター、別Unit名、条件分岐、反復、変数引数、算術式、負数、浮動小数、キーワード引数はエラー。
入力は`exec`／`eval`／importして実行しない。実機用初期化や呼び出しループを持たないので、入力ファイルは単独で実行するプログラムではない。

## ひな形

`fixtures/06-port-a.m5f2`はPORT.A設定をWeb IDEへ読み込み、編集可能なブロックとG33/G32の生成を確認して再保存したもの。
ひな形のサンプル処理を除去し、SetupのM5初期化・RGB初期化・page0読み込みと、LoopのM5.updateを残して入力処理をつなぐ。
`blockly`以外のJSON値はコピーし、UnitのinitBlockIdが参照する初期化ブロックIDも維持する。
未知のひな形はSHA-256の照合で拒否する。別機種・別ポート対応は、ひな形採取と再検証を伴うコード変更として扱う。初期調査のPORT.B版も比較記録として保持するが、変換器の既定出力はPORT.A版である。

## 成果物と来歴

- `convert.py`、`tests/`、`examples/blink.py`: 今回作成したコード。リポジトリ既定BSD-2-Clause。
- `fixtures/`: UIで作成・保存した実験設定、取得順の7段階。SHA256.jsonで原データを特定。
- `results/blink-port-a.m5f2`: 現在の変換器によるPORT.A版の出力。実機確認対象。
- `results/blink.m5f2`: 初期調査時のPORT.B版出力。比較記録。
- `results/roundtrip.m5f2`: 上記をWeb IDEへ読み込んで再保存した結果。
- `results/roundtrip.py`: Web IDEエディターから全選択・コピーして取得した生成Pythonを転記。実行していない。
- `results/edited-sleep3.m5f2`: 読み込み後、ブロック側だけで2秒→3秒に変更して再保存。
- `results/roundtrip-port-a.m5f2`、`results/roundtrip-port-a.py`: PORT.A設定をUiFlow2で再保存し、再生成Pythonを採取した結果。
- 公式音声サンプル全文は再配布せず、URL・ハッシュ・観察だけを記録。

第三者ツール由来の生成物は独自コードと区別する。[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)参照。
