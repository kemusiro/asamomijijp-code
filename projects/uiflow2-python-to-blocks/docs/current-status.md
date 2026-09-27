# 現在仕様・対応状況

最終更新: 2026-09-28

## 完成条件

本試作は、対応プロファイルを明示し、MicroPythonから**動作が同等な編集可能UiFlow2プロジェクト**を生成する。
元のBlock ID、座標、分割方法、コメント、整形は復元しない。変換できない処理は拒否するか、最善努力変換では
公式のPythonコードBlockへ保持し、意味や動作が変わり得る箇所を注記レポートへ出す。

固定プロファイルは次の通り。

| 項目 | 値 |
| --- | --- |
| Profile ID | `core2-v1.3-uiflow2-v2.5.3` |
| 本体 | M5Stack Core2 v1.3 |
| UiFlow2 IDE | V2.5.3 |
| ファームウェア | `v2.5.3-CORE2` |
| Unit | RGB LED Unit（SK6812、M5STACK-U003、3 LED） |
| 接続 | Core2側面PORT.A、GPIO `(33, 32)` |
| 画面 | LVGLページ一つ。入力の`M5Page`で名前と背景色を変更可能 |

M5STACK-U003の公式例はPORT.B、`RGBUnit((36, 26), 3)`を使う。本プロファイルのPORT.Aは、
UiFlow2 V2.5.3での往復とCore2実機で確認した別条件である。

## 変換器

| 入口 | 方針 | 対応外の処理 | 主な用途 |
| --- | --- | --- | --- |
| `convert.py` | 対応文法を厳密に検査 | エラーにして停止 | RGB／Sleepの再現性を優先する変換 |
| `best_effort.py` | ASTから既知処理を通常Blockへ分解 | 公式`execute_code`／`execute_code_import`へ保持し注記 | 一般的なMicroPythonの近似変換 |
| `workflow.py` | 保存時に最善努力変換を実行 | 直前の成功出力を残しエラー記録 | VS CodeなどからUiFlow2へ渡す作業の自動化 |

厳密変換は、短縮入力とUiFlow2 V2.5.3生成Python全文の二形式を受け付ける。最善努力変換は
`setup()`／`loop()`を中心に、制御構文を入れ子2段までBlock化する。3段目の制御構文は子孫を含めて
一つの`execute_code` Blockへ格納する。構文解析できないPythonは変換しない。

最善努力変換の戦略名は次の意味を持つ。

| 戦略 | 意味 |
| --- | --- |
| `strict-native` | 厳密変換だけで通常Blockを生成 |
| `best-effort-native` | 最善努力変換で、コードBlockを使わず生成 |
| `hybrid-native-and-raw` | 通常BlockとコードBlockを混在 |
| `whole-module-raw` | モジュール全体を`execute_code_import`へ保持 |

## 対応状況

ここで「実装」は変換器と自動テストが存在することを示す。「Web確認」はUiFlow2 V2.5.3でBlockまたは
部品と生成Pythonを確認したこと、「実機」はCore2 v1.3で動作を確認したことを示す。三つは同義ではない。

| 機能 | 実装 | Web確認 | 実機 | 現在の境界 |
| --- | --- | --- | --- | --- |
| `time.sleep`、RGB `fill_color` | 済 | 済 | 済 | 厳密変換の完成条件を満たす。確認色と時間値は検証例の範囲 |
| `if`／`for`／`while`、変数、比較・論理・算術・文字列 | 済 | 未 | 未 | 制御構文は2段まで。複雑な式や3段目はコードBlockへ退避し得る |
| `BtnA/B/C.wasPressed()` | 済 | 未 | 未 | 公式サンプル対でBlock型を確認。三つの`NAME`を自動テスト済み |
| `Speaker.begin`／`setVolumePercentage`／`tone` | 済 | 未 | 未 | 公式サンプル対を根拠にXML生成を自動テスト済み |
| `M5Page`、`M5TextArea`の配置 | 済 | 部分 | 未 | 公式例から部品構造を確認。変換済みカウント例全体のImportは未実施 |
| TextArea `set_one_line`／`set_text` | 済 | 未 | 未 | 通常Block化と参照整合性を自動テスト済み |
| TextArea `set_text_color` | 済 | 済 | 未 | 最小BlockのXMLと生成PythonをWeb IDEで確認。変換済み全体は未確認 |
| `global`、トップレベル変数宣言 | 済 | 根拠あり | 未 | `<variables>`と部品参照へ正規化。公式サンプル対で生成規則を確認 |
| 固定import、色定数、docstring | 済 | 未 | 未 | importはプロファイルへ、定数は値へ展開、docstringは注記へ移す |
| `execute_code`フォールバック | 済 | Block存在確認 | 未 | Web IDEのカテゴリに存在。変換器出力のImport往復は未確認 |

`Web確認: 部分`は、部品または最小Blockの形を確認したが、変換器が生成した複合プロジェクト全体では
確認していないことを表す。

## カウント例

[`examples/count-three.py`](../examples/count-three.py)は、BtnAを押すたびに値を増やし、3の倍数または
数字の3を含むときにTextAreaを赤くしてtoneを鳴らす自然なMicroPython例である。変換結果は
[`results/count-three.m5f2`](../results/count-three.m5f2)、差分注記は
[`results/count-three.notes.md`](../results/count-three.notes.md)に保存した。

現在の変換結果は`best-effort-native`で、UI部品2個、通常Block 8個、構造化制御Block 2個、
コードBlock 0個である。固定import、色定数、トップレベル宣言、関数内`global`、main guardはUiFlow2の
プロジェクト構造へ正規化した。Block ID、部品ID、main guardの例外処理、定数という名前は元コードと一致しない。

この`.m5f2`全体のUiFlow2 Import、編集、Python再生成と、ボタン・表示・スピーカーを組み合わせた実機動作は
まだ確認していない。

## `.m5f2`について分かったこと

`.m5f2`は単純なBlockly XMLではなく、JSON外枠の`blockly`文字列へ複数のトップレベルXML要素を格納する。
主な関係は次の通り。

- `components`: ページやTextAreaなどの設計時属性を持つ。
- `screen`: rotationなど画面全体の設定を持つ。
- `units`: Unit名、種類、ポート、初期化Block IDを持つ。
- `resources`: 対象機種で利用するハードウェアやBlockカテゴリを示す。
- `blockly`: Setup、Loop、変数、値式、文の接続をXML断片として持つ。
- `components[].id`、`units[].initBlockId`、Blockly内のfieldやblock IDが層をまたいで参照し合う。

公式`uiflow-micropython`リポジトリにはランタイム、文書、`.m5f2`とPythonの例がある。一方、Web IDEの
Blockly定義、Python生成器、V2.5.3の完全な`.m5f2`スキーマは見つかっていない。このため、公式タグ2.5.3を
APIと既存Blockの根拠にし、保存形式の詳細はV2.5.3 Web IDEから採取したfixtureで補っている。

## 検証履歴

| 日付 | 確認内容 |
| --- | --- |
| 2026-09-21 | Core2空プロジェクトからSleep、RGB初期化、RGB色変更までのfixtureを段階採取 |
| 2026-09-22 | PORT.A版をImport・再保存し、`RGBUnit((33, 32), 3)`を再生成。Core2実機で赤2秒、緑1秒、消灯1秒を確認 |
| 2026-09-26 | UiFlow2生成Python全文を変換・Importし、編集可能Blockと再生成を確認。実測は赤2002ms、緑・消灯1001～1002ms |
| 2026-09-28 | TextArea文字色BlockのXMLと生成PythonをWeb IDEで確認。最善努力変換をUI、変数、BtnA/B/C、Speakerへ拡張 |

自動テストは33件（厳密変換13、最善努力変換16、ワークフロー4）である。保存したfixtureに対する回帰検査であり、
Web IDEと実機を毎回操作する試験ではない。

## 残る作業

1. 最新の`results/count-three.m5f2`をUiFlow2 V2.5.3へImportし、各BlockとUI部品の編集、Python再生成を確認する。
2. 再生成PythonをCore2 v1.3で実行し、BtnA、TextArea、文字色、Speakerの組み合わせを確認する。
3. BtnBとBtnCを含む最小プロジェクトをWeb IDEと実機で確認する。
4. Label、Line、Canvas、ボタンの他の状態、Speakerの停止、IMU、Touch、Mic、SDカードを同じ完成条件で追加する。
5. M5Stackへ、`.m5f2`スキーマ、Blockly定義、Python生成規則、版ごとの互換性の公開を提案する。

## 文書案内

| 文書 | 内容 |
| --- | --- |
| [入力仕様](input-python-spec.md) | `convert.py`の厳密な受理条件 |
| [最善努力変換](best-effort-conversion.md) | `best_effort.py`の変換規則と意味差 |
| [`.m5f2`構造](m5f2-structure.md) | JSON、Blockly XML、参照関係の調査結果 |
| [公式ソース参照記録](official-uiflow-micropython-2.5.3.md) | 固定した一次資料と採用した仕様 |
| [Core2拡張計画](core2-builtins-extension.md) | UI部品・内蔵デバイスの対象と完成条件 |
| [自動化](automation-workflow.md) | エディター保存からUiFlow2 Importまでの手順 |
| [調査・検証記録](../results/research-2026-09-21.md) | 日付順の採取・往復・実機ログ |
