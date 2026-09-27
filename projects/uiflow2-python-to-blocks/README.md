# UiFlow2生成Python→編集可能ブロック変換（試作版）

2026-09-21作成、2026-09-26にUiFlow2生成Python全文の入力へ拡張。
対象プロファイルを固定し、生成Pythonから動作が同等な編集可能UiFlow2プロジェクトを作る。
元のブロック配置、ID、分割方法を復元するものではなく、対応する処理を標準的なブロック列へ正規化する。

対応記事は `asamomijijp-site/src/content/articles/drafts/uiflow2-python-to-blocks.md`。
記事URL・公開コードの固定コミットは未確定。公開前に相互リンクを確定する。

## 対応プロファイル

- Profile ID: `core2-v1.3-uiflow2-v2.5.3`
- 本体: M5Stack Core2 v1.3
- UiFlow2: V2.5.3
- ファームウェア: `v2.5.3-CORE2`
- Unit: RGB LED Unit（SK6812、M5STACK-U003）、プロファイル接続PORT.A、LED 3個（公式標準はPORT.B）
- 画面: `page0`一つ
- 対応命令: `time.sleep(整数)`、`rgb_0.fill_color(整数)`

本体、UiFlow2、ファームウェア、Unitのいずれかが異なるPythonは、このプロファイルの入力として扱わない。
Unit追加は、公式ランタイム実装と同一タグのサンプル対を調べたうえで、初期化・メソッド・保存JSON・Blockly XMLの対応表とV2.5.3検証用fixtureをUnitごとに追加して行う。

## 仕様の根拠

機械可読な対応プロファイルは[`profile.json`](profile.json)に置く。変換器はこのファイルからプロファイルID、ファームウェア、RGB UnitのLED数、検証対象PORT.AのGPIOを読み込む。

M5Stack公式[`uiflow-micropython`](https://github.com/m5stack/uiflow-micropython)のタグ[`2.5.3`](https://github.com/m5stack/uiflow-micropython/tree/2.5.3)、コミット[`50e440780492aa847378c7d3477ab912f7063bac`](https://github.com/m5stack/uiflow-micropython/commit/50e440780492aa847378c7d3477ab912f7063bac)をAPI仕様の一次資料として固定した。参照ファイル、SHA-256、採用した仕様、公式ソースだけでは決められない範囲は[公式ソース参照記録](docs/official-uiflow-micropython-2.5.3.md)に記載する。

公式例はRGB UnitをPORT.B、`RGBUnit((36, 26), 3)`としている。今回のプロファイルはCore2 v1.3本体側面への接続を対象に、UiFlow2 V2.5.3の往復変換と実機で確認したPORT.A、`RGBUnit((33, 32), 3)`を使う。

公式リポジトリにはデバイス側ランタイム、文書、`.m5f2`とPythonのサンプル対があるが、Web IDEのBlockly生成器や`.m5f2`の完全なスキーマはない。そのため、APIと標準Port Bは公式ソース、V2.5.3保存形式とPORT.A設定は今回採取したfixtureを根拠にする。

`.m5f2`のJSON外枠、Blockly XML断片、画面・Unit・ブロック間の参照関係、確認済み項目と未確定事項は[`.m5f2`構造調査メモ](docs/m5f2-structure.md)にまとめる。

## 現状

- ASTによる静的解析、コメントメタデータ解析、XML生成、自動テスト13件: 成功。
- 短縮入力と、UiFlow2 V2.5.3が生成したPython全文の両方に対応。
- 2026-09-26、全文入力例から生成した`.m5f2`をWeb IDEへ読み込み、編集可能なRGB／Sleepブロックと、`RGBUnit((33, 32), 3)`を含むPython再生成を確認。
- 実際のWeb IDEで短縮入力例→`.m5f2`読み込み→Python再生成: 成功。
- 読み込んだSetupのSleep 2を3へ編集し、`time.sleep(3)`への再生成: 成功。
- PORT.A版のUiFlow2読み込み、編集可能なブロックの復元、`RGBUnit((33, 32), 3)`のPython再生成: 成功。
- Core2 v1.3／M5STACK-U003／`v2.5.3-CORE2`の実機実行: 成功。赤2秒の後、緑1秒と消灯1秒を繰り返すことを確認した。
- コメントでrotationや背景色を既定値以外へ変更した出力は、Web IDEと実機ではまだ再確認していない。
- 2026-09-26、全文入力例をCore2のRAM上で実行し、赤2秒の後、緑1秒と消灯1秒を繰り返すことを再確認。診断時の実測は赤2002ms、緑・消灯1001〜1002msだった。
- 詳しい再現手順・保存形式対応表・検証範囲: [調査記録](results/research-2026-09-21.md)。

## 実行

検証環境: macOS、Python 3.14.6（標準ライブラリのみ）。他のPython版は未検証。
このディレクトリをカレントディレクトリにする。

```sh
python3 -m unittest discover -s tests -v
python3 convert.py examples/blink-uiflow2-generated.py /tmp/blink-new.m5f2
```

出力先は新しいファイル名を指定する。既存ファイルは上書きしない。
Web IDEのフォルダーメニュー→Import project from local fileで出力を開く。

入力は実行せず、`tokenize`でメタデータコメント、`ast`でPython構文を解析する。
`exec`、`eval`、入力ファイルのimportは行わない。

## UiFlow2生成Python全文モード

入力例は [`examples/blink-uiflow2-generated.py`](examples/blink-uiflow2-generated.py)。
UiFlow2からコピーした生成Pythonの先頭へ、次の3行を追加する。

```python
# uiflow2-convert: {"schema":1,"profile":"core2-v1.3-uiflow2-v2.5.3","firmware":"v2.5.3-CORE2"}
# uiflow2-unit: {"name":"rgb_0","type":"rgb","port":"A","leds":3}
# uiflow2-page: {"name":"page0","rotation":1,"background":"#ffffff"}
```

各指示は一つずつ必要で、未知の項目を許可しない。JSONの型、値域、色の`#RRGGBB`形式を検査する。
コメントの指定とPython中の次のコードが矛盾した場合は変換を中止する。

- import一式
- `page0`と`rgb_0`のグローバル宣言
- `M5.begin()`、`m5ui.init()`などの初期化順序
- `Widgets.setRotation(...)`
- `m5ui.M5Page(bg_c=...)`
- `RGBUnit((33, 32), 3)`
- `M5.update()`
- `if __name__ == '__main__':`以下のメインループと例外処理

一致した定型処理はプロファイル所有の処理として取り除き、`setup()`と`loop()`の対応命令をBlocklyへ変換する。
背景色は`.m5f2`の`components`、rotationは`screen`へ反映する。

変換用コメントは、UiFlow2がブロックからPythonを再生成したときに残るとは限らない。
最初の取り込み後は`.m5f2`内の`units`、`components`、`screen`を設定の正本とする。
再生成Pythonだけから再び変換する場合は、指示コメントを再度追加する。

## 短縮入力モード

従来の小さな入力形式も維持する。
`import time`と、引数のない`setup`／`loop`定義を一つずつ書く。
各本体は`time.sleep(整数)`または`rgb_0.fill_color(整数)`の呼び出し列とする。
空本体は単独の`pass`にする。

```python
import time


def setup():
    rgb_0.fill_color(0xff0000)
    time.sleep(2)


def loop():
    rgb_0.fill_color(0x33ff33)
    time.sleep(1)
    rgb_0.fill_color(0x000000)
    time.sleep(1)
```

短縮入力では検証済みテンプレートのpage0、rotation、背景色、RGB Unit設定をそのまま使用する。

## 対応範囲とエラー

待機は0〜86400の整数秒、色は0〜`0xffffff`。公式RGB APIで確認した`set_brightness`と`set_color`はプロファイルへ記録しているが、V2.5.3 Web IDEでの往復確認前なので変換対象には含めない。
デモで往復確認した色は赤、緑（`#33ff33`）、黒。全色・全待機値を実機検証したものではない。

次はエラーにする。

- 代入、別名import、関数再定義、引数、デコレーター
- RGB Unit以外のUnit、PORT.A以外、LED数3以外
- 条件分岐、反復、ユーザー定義関数
- 変数引数、算術式、負数、浮動小数、キーワード引数
- 未知の初期化、API呼び出し、トップレベル文
- 定型コードまたはメタデータとの不一致

未知の処理を黙って捨てない。構文要素に位置情報がある場合は、行番号と桁番号をエラーへ含める。

## 出力の保証範囲

対応範囲内では、SetupとLoopの区分、命令順序、整数引数を維持する。
UiFlow2固有の初期化、更新、終了処理はプロファイルの標準形を使用する。
出力には新しいブロックIDと接続を割り当て、Unitの`initBlockId`との整合性を維持する。

次は維持しない。

- 元のブロック座標とID
- 元のブロックの分割方法
- shadowブロックの選択状態
- 折り畳み状態と編集履歴
- Pythonの空行、字下げ幅、コメント

## ひな形

`fixtures/06-port-a.m5f2`はPORT.A設定をWeb IDEへ読み込み、編集可能なブロックとG33/G32の生成を確認して再保存したもの。
ひな形のサンプル処理を除去し、SetupのM5初期化・RGB初期化・page0読み込みと、Loopの`M5.update()`を残して入力処理をつなぐ。
未知のひな形はSHA-256照合で拒否する。

## 成果物と来歴

- `convert.py`、`tests/`、`examples/`: 今回作成したコード。リポジトリ既定BSD-2-Clause。
- `profile.json`、`docs/`: 公式タグに固定した参照情報、抽出仕様、今回の検証プロファイル。第三者コード本文は複製していない。
- `fixtures/`: UIで作成・保存した実験設定、取得順の7段階。`SHA256.json`で原データを特定。
- `results/blink-port-a.m5f2`: 変換器によるPORT.A版の出力。UiFlow2で読み込み・再生成を確認した実機検証対象。
- `results/roundtrip-port-a.m5f2`、`results/roundtrip-port-a.py`: PORT.A設定をUiFlow2で再保存し、再生成Pythonを採取した結果。後者をCore2のRAM上で実行して点灯を確認した。
- `results/edited-sleep3.m5f2`: 読み込み後、ブロック側だけで2秒→3秒に変更して再保存。

第三者ツール由来の生成物は独自コードと区別する。[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)参照。
