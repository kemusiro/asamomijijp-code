# `.m5f2`構造調査メモ

## この文書の位置づけ

`.m5f2`の公式な完全スキーマは、確認したM5Stack公式
[`uiflow-micropython`](https://github.com/m5stack/uiflow-micropython)には含まれていない。
この文書は、次の資料から観察できた保存形式をまとめたものである。

- UiFlow2 V2.5.3でCore2用に保存した[`fixtures/*.m5f2`](../fixtures/)
- UiFlow2へ読み込み、再保存した[`results/roundtrip-port-a.m5f2`](../results/roundtrip-port-a.m5f2)
- M5Stack公式タグ[`2.5.3`](https://github.com/m5stack/uiflow-micropython/tree/2.5.3)の
  [`rgb_core.m5f2`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.m5f2)
- 公式リポジトリにある他機種・他バージョンの`.m5f2`例

以下では、実ファイルで確認できた事実を「確認済み」、複数例から導いた解釈を「推定」として区別する。

## ファイル全体

確認した`.m5f2`は、ZIPなどのコンテナーではなく、UTF-8で読める一つのJSONオブジェクトだった。
Core2／UiFlow2 V2.5.3の採取例には次のトップレベル項目がある。

```json
{
  "version": "V2.0",
  "versionNumber": "V2.5.3",
  "type": "core2",
  "components": [],
  "resources": [],
  "units": [],
  "hats": [],
  "caps": [],
  "chains": [],
  "bases": [],
  "plcmodules": [],
  "stamps": [],
  "tab5modules": [],
  "poep4modules": [],
  "i2cs": [],
  "chainBus": [],
  "blockly": "...XML断片...",
  "screen": [],
  "logicWhenNum": 0,
  "customList": []
}
```

この一覧はV2.5.3 Core2の観察結果であり、全機種・全UiFlow2版で必須とは限らない。
たとえば公式タグ2.5.3の`rgb_core.m5f2`には`versionNumber`がなく、別バージョンの公式例では
機種に応じて周辺機器用配列の構成が異なる。

## トップレベル項目

| 項目 | 確認した型 | 観察した役割 |
| --- | --- | --- |
| `version` | 文字列 | 保存形式の系列。確認例は`V2.0` |
| `versionNumber` | 文字列 | 保存したUiFlow2 IDEの版と推定。V2.5.3採取例は`V2.5.3`。公式例には欠ける場合がある |
| `type` | 文字列 | 対象本体。Core2では`core2` |
| `components` | 配列 | ページ、ラベル、ボタンなど画面部品の設計時情報 |
| `resources` | 配列 | 使用可能または使用中のハードウェア、Unitなどの分類別識別子 |
| `units` | 配列 | Unitのインスタンス、ポート、初期化ブロックとの対応 |
| `hats`～`chainBus` | 配列 | 各拡張方式に属する機器の設定。今回のCore2＋RGB Unit例では空 |
| `blockly` | 文字列 | Blocklyワークスペースを表すXML断片。プログラム本体 |
| `screen` | 配列 | 内蔵画面などの寸法、回転、シミュレーター表示設定 |
| `logicWhenNum` | 数値 | 確認例は`0`。正確な意味は未確認 |
| `customList` | 配列 | 確認例は空。正確な要素スキーマは未確認 |

`version`と`versionNumber`は別の値である。観察範囲では、前者は形式の大分類、後者はIDEの版に見える。
ただし、公式スキーマがないため互換性判定をこの解釈だけに依存させない。

## 画面情報: `components`と`screen`

今回の最小Core2例は、`components`にLVGLページを一つ持つ。

```json
{
  "name": "page0",
  "type": "lvgl_page",
  "layer": 0,
  "screenId": "builtin",
  "screenName": "",
  "id": "kS0qQwL%Oa0BAIH!",
  "createTime": 1790000358885,
  "backgroundColor": "#ffffff",
  "isLVGL": true,
  "isSelected": true
}
```

`screen`には対応する内蔵画面の設計時情報がある。

```json
{
  "simulationName": "Built-in",
  "type": "builtin",
  "width": 320,
  "height": 240,
  "scale": 0.77,
  "screenName": "",
  "blockId": "",
  "screenColorType": 0,
  "rotation": 1,
  "id": "builtin",
  "createTime": 1790000358882
}
```

確認できた関係は次の通り。

- `components[].screenId`と`screen[].id`はいずれも`builtin`で対応する。
- `components[].name`の`page0`は、Blockly側のページ読み込みブロックの`NAME`にも現れる。
- ページの背景色は`components[].backgroundColor`、画面回転は`screen[].rotation`に保存される。
- 複雑な公式例では子部品が`pageId`を持ち、親ページの`components[].id`を参照する。
- `layer`は描画または編集上の重なり順を表すと推定できる。
- `scale`はエディター上のシミュレーター表示倍率と推定でき、実機の画面寸法とは分けて扱う必要がある。

画面部品の属性は部品型ごとに異なる。位置、寸法、色、フォント、テキストなどは、対応する部品を
V2.5.3で一つずつ保存して差分を採取しない限り、一般化できない。

## リソースとUnit: `resources`と`units`

RGB Unitを追加した例では、`resources`が次の二要素を持つ。

```json
[
  {
    "hardware": [
      "hardware_button",
      "hardware_pin_button",
      "imu",
      "speaker",
      "touch",
      "sdcard",
      "mic"
    ]
  },
  { "unit": ["unit_rgb"] }
]
```

`resources`は分類名をキー、機能識別子の配列を値にするオブジェクトの並びである。
公式の他機種例では`cap`など別分類も現れる。これがパレットの有効化一覧、依存関係一覧、またはその両方かは未確定である。

今回の`units[0]`は次の構造を持つ。

```json
{
  "type": "unit_rgb",
  "name": "rgb_0",
  "portList": ["A", "B", "C", "Custom"],
  "portType": "A",
  "userPort": [22, 21],
  "id": "i+7Epf7!lKE^nrnq",
  "createTime": 1790003395835,
  "initBlockId": "e*J`pYa~OuH?$}($*$j|"
}
```

確認できた関係と挙動は次の通り。

- `type: unit_rgb`は`resources`の`unit_rgb`およびBlocklyの`unit_rgb_*`ブロック群と対応する。
- `name: rgb_0`はBlockly側の`<field name="NAME">rgb_0</field>`と、生成Pythonの変数名に対応する。
- `initBlockId`はBlockly XML内の`unit_rgb_init`ブロックの`id`を指す。
- `portType`を`B`から`A`へ変えてUiFlow2 V2.5.3へ読み込むと、生成Pythonは
  `RGBUnit((36, 26), 3)`から`RGBUnit((33, 32), 3)`へ変化した。
- この操作では`userPort`が`[22, 21]`のまま変化しなかった。このため、少なくとも標準ポートA/Bでは
  `portType`から機種別ピンを選び、`userPort`はCustom用として扱う可能性が高い。
- UiFlow2での読み込み・再保存により`createTime`が変わる場合がある。意味比較では時刻値を固定値として扱わない。

`id`や`createTime`の正式な生成規則は不明である。変換器は既知のV2.5.3テンプレートにある周辺メタデータを利用し、
新しく作るBlocklyブロックIDだけを重複しない値に置き換える。

## プログラム本体: `blockly`

`blockly`の値は、JSON内でエスケープされたXML文字列である。確認例にはXML宣言や単一のルート要素がなく、
`<variables>`や複数のトップレベル`<block>`を連結したXML断片が入る。
一般的なXMLパーサーへ渡す場合は、解析時だけ次のように仮のルートで囲む必要がある。

```python
root = ElementTree.fromstring("<xml>" + project["blockly"] + "</xml>")
```

V2.5.3 Core2の採取例では、トップレベルにSetupとLoopが一つずつある。

```xml
<block type="basic_on_setup" id="setup_block"
       deletable="false" x="50" y="50">
  <statement name="FUNC">
    <!-- Setupの処理列 -->
  </statement>
</block>

<block type="basic_on_loop" id="loop_block"
       deletable="false" x="450" y="50">
  <statement name="FUNC">
    <!-- Loopの処理列 -->
  </statement>
</block>
```

観察した主なXML要素は次の通り。

| 要素 | 役割 |
| --- | --- |
| `variables` / `variable` | ワークスペースの変数名と変数ID。変数を使う公式例で確認 |
| `block` | 実ブロック。`type`が機能、`id`がワークスペース内識別子 |
| `shadow` | 数値など入力欄の既定ブロック |
| `field` | Unit名、数値、色、選択肢などの直接値 |
| `value` | 値入力ソケット。中に`block`または`shadow`を持つ |
| `statement` | Setup、Loop、条件分岐などの文ブロック列を収める入力 |
| `next` | 次に実行する文ブロックを接続する |
| `mutation` | 標準XMLだけでは表せないブロック固有の形状・モード情報 |

文の実行順は、最初の`block`から`next/block`をたどる鎖で表現される。
引数は`value`内のブロックまたはshadowで表現される。たとえば整数秒の待機は概略次の形になる。

```xml
<block type="time_sleep_second" id="py2blocks_3">
  <value name="SECOND">
    <shadow type="math_number" id="py2blocks_4">
      <mutation max="Infinity" min="0" precision="0"></mutation>
      <field name="NUM">2</field>
    </shadow>
  </value>
</block>
```

RGB全灯色の設定は、処理ブロックと色ブロックの組で表現される。

```xml
<block type="unit_rgb_set_fill_color" id="py2blocks_1">
  <field name="NAME">rgb_0</field>
  <value name="COLOR">
    <block type="color_rgb_palette" id="py2blocks_2">
      <mutation mode="palette"></mutation>
      <field name="MODE">palette</field>
      <field name="COLOR">#ff0000</field>
    </block>
  </value>
</block>
```

`x`と`y`はトップレベルブロックのワークスペース座標である。実行順は`next`などの接続で決まるため、
この試作の完成条件では元座標を復元しない。元のブロック分割も復元せず、同じ動作になる標準的な鎖を生成する。

## JSON外枠とBlockly XMLの参照関係

`.m5f2`は、同じ対象を外側JSONとBlockly XMLの両方に持つ場合がある。
今回確認した主要な関係は次の通り。

```text
units[0].type = "unit_rgb"
 ├─ resources[].unit に "unit_rgb"
 └─ Blockly block type = "unit_rgb_init" / "unit_rgb_set_fill_color"

units[0].name = "rgb_0"
 └─ Blockly field NAME = "rgb_0"

units[0].initBlockId
 └─ Blocklyの unit_rgb_init block.id

components[0].name = "page0"
 └─ Blocklyの lvgl_page_screen_load field NAME = "page0"

components[0].screenId = "builtin"
 └─ screen[0].id = "builtin"
```

一方だけを書き換えると、読み込み時の欠落、再生成コードの不一致、Unit設定画面とブロックの不整合が起きる可能性がある。
変換ではJSONとXMLを別々の文書として扱わず、参照を含む一つのプロジェクトモデルとして生成する必要がある。

## 最小差分から分かったこと

V2.5.3 Web IDEで段階的に保存したfixtureの差分は次の通りだった。

| 操作 | 変化した場所 |
| --- | --- |
| 空プロジェクトへSleep 1秒を追加 | `blockly`のみ |
| Sleep 1秒を2秒へ変更 | `blockly`のみ |
| RGB Unitを追加 | `resources`、`units`、`blockly` |
| RGB全灯色ブロックを追加・色を変更 | `blockly`のみ |
| RGB UnitをPort BからPort Aへ変更 | `units[].portType`、`units[].createTime`、`blockly` |

この差分から、処理の大部分は`blockly`へ入り、接続機器の存在とポート設定は外側JSONにも入ることが分かる。
色や待機時間のような処理引数は、今回の例では外側JSONへ重複していない。

## 現在の変換器が維持する条件

現在の試作は既知のV2.5.3 Core2テンプレートを基礎にし、次を維持する。

- `version`、`versionNumber`、`type`を含む外側JSON
- `page0`、内蔵画面、rotation、背景色
- RGB Unitの型、名前、Port A、LED数3
- `units[].initBlockId`と初期化ブロックIDの一致
- SetupとLoopの区分
- 文の順序と整数引数
- ブロックIDの一意性

元の座標、元ID、元の分割、編集履歴、折り畳み状態、Pythonの書式は維持しない。

## 読み込み前に検査できる項目

`.m5f2`を機械生成するときは、少なくとも次を検査できる。

1. ファイル全体がJSONオブジェクトとして解析できる。
2. `version`、`versionNumber`、`type`が対象プロファイルと一致する。
3. `blockly`を仮ルートで囲むとXMLとして解析できる。
4. Blockly内の全`block`と`shadow`のIDが重複しない。
5. `units[].initBlockId`が対応する初期化ブロックを指す。
6. Unitと画面部品の`name`がBlocklyの`NAME`フィールドと一致する。
7. `resources`に、使用するUnit型が含まれる。
8. `components[].screenId`が対応する`screen[].id`を指す。
9. 対応外のブロック型、Unit型、画面部品型を黙って捨てない。

最終的な互換性は、UiFlow2 V2.5.3へのImport、ブロック編集、Python再生成で確認する。
JSON/XMLの構文検査だけでは、Web IDE内部の意味検査を代替できない。

## 未確定事項

現時点で次は仕様として断定できない。

- トップレベル各項目の必須・省略条件と既定値
- UiFlow2の版をまたぐ自動移行・後方互換性の規則
- `logicWhenNum`と`customList`の完全な意味と要素スキーマ
- 全画面部品、Unit、Hat、Cap、Module、Baseなどの属性スキーマ
- `id`と`createTime`の正式な生成規則、許容文字、安定性
- `resources`が表す範囲と、他の配列との厳密な整合条件
- `userPort`のCustom選択時の扱いと、機種別標準ポート解決の完全な表
- Blocklyの全ブロック型、`mutation`属性、値域、Python生成規則
- 未接続ブロック、無効ブロック、複数ページ、イベント、ユーザー関数、カスタムリストの保存規則

これらを埋めるには、M5Stackからバージョン付きJSON Schema、Blocklyブロック定義、Python生成器、
ポート解決表、移行規則が公開されるのが最も確実である。それまでは対象機種とUiFlow2版を固定し、
最小プロジェクトの差分採取とWeb IDEでの往復確認をUnit・機能ごとに積み重ねる。
