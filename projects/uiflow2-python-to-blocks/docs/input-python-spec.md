# Blockを生成できるMicroPython入力仕様

## 適用範囲

この文書は、現在の試作変換器[`convert.py`](../convert.py)が、編集可能なUiFlow2 `.m5f2`プロジェクトへ
変換できるPython入力を定義する。

対応プロファイルは次に固定する。

| 項目 | 対応値 |
| --- | --- |
| 本体 | M5Stack Core2 v1.3 |
| UiFlow2 IDE | V2.5.3 |
| ファームウェア | `v2.5.3-CORE2` |
| Unit | M5STACK-U003 RGB LED Unit、SK6812、LED 3個 |
| 接続 | Port A、GPIO `(33, 32)` |
| 画面 | `page0`一つ |
| 対応命令 | `time.sleep(整数)`、`rgb_0.fill_color(整数)` |

変換器は入力Pythonを実行しない。コメントを`tokenize`、プログラムをPythonの`ast`で静的に解析する。
未知の文や呼び出しを無視せず、対応外として変換を中止する。

## 入力形式

入力は次のどちらかとする。

1. **短縮入力**: SetupとLoopの処理だけを書く変換専用形式
2. **UiFlow2生成Python全文**: V2.5.3が生成した定型コード全文へ、変換用コメントを追加する形式

短縮入力は単独では実機用MicroPythonプログラムにならない。M5初期化、画面、Unit初期化、メインループは
検証済み`.m5f2`テンプレートから補う。全文形式は元のUiFlow2生成Pythonとして実行できる形を保つ。

## 共通の処理命令

SetupとLoopのうち、ユーザー処理として変換できる文は次の二種類だけである。

| Python | 引数 | 生成するBlocklyブロック |
| --- | --- | --- |
| `time.sleep(seconds)` | `0`～`86400`の整数リテラル | `time_sleep_second` |
| `rgb_0.fill_color(color)` | `0x000000`～`0xffffff`の整数リテラル | `unit_rgb_set_fill_color`＋`color_rgb_palette` |

引数には、ちょうど一つの位置引数が必要である。次は使用できない。

- 変数、定数名、属性参照
- 加減算などの式
- 負数、浮動小数、真偽値
- キーワード引数
- `*args`や`**kwargs`
- 引数の省略、複数引数

整数の表記は10進数でも16進数でもよい。たとえば`16711680`と`0xff0000`は同じ赤として解析され、
出力 `.m5f2` の色は小文字6桁の`#ff0000`になる。

処理は記述順にBlocklyの`next`接続へ変換する。SetupとLoopの区分も維持する。

## 短縮入力

### 全体構造

コメントと空行を除き、モジュール直下は次の三要素だけとする。

1. `import time`
2. 引数なしの`setup`関数
3. 引数なしの`loop`関数

標準的な記述例は次の通り。

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

実装上は`setup`と`loop`の定義順を入れ替えても名前で識別できるが、可読性とUiFlow2生成形との対応のため、
`setup`、`loop`の順を推奨する。

### importの条件

`import time`は完全に一致する必要がある。

```python
# 対応
import time

# 非対応
import time as t
from time import sleep
import os, time
```

他のimport、代入、クラス、追加関数、関数呼び出しなどをモジュール直下へ置くことはできない。
モジュールdocstringもAST上の文になるため、現在は使用できない。

### `setup`と`loop`

両方の関数が一つずつ必要である。次は使用できない。

- 関数の引数、既定値、`*args`、`**kwargs`
- 戻り値や引数の型注釈
- デコレーター
- `async def`
- 同名関数の重複
- `return`、`yield`
- 関数docstring

関数本体は、対応する呼び出しを0個以上、直列に並べる。空にする場合は`pass`を一つだけ書く。

```python
def setup():
    pass
```

`pass`と別の文を同じ関数へ置くことはできない。

### 短縮入力の形式

概略文法は次のように表せる。

```text
program       := "import time" (function_setup function_loop
                              | function_loop function_setup)
function_setup := "def setup():" operation_list_or_pass
function_loop  := "def loop():"  operation_list_or_pass
operation_list_or_pass := operation* | "pass"
operation     := "time.sleep(" integer_literal ")"
             | "rgb_0.fill_color(" integer_literal ")"
```

これは説明用の概略である。実際の字句・構文解析にはPython ASTを使うため、空白、改行、整数の進数など、
意味に影響しない表記差は許容される。

## UiFlow2生成Python全文

### 用途

UiFlow2 V2.5.3が生成したCore2用Pythonを、その定型部分も含めて入力する形式である。
元の生成Pythonの先頭へ、対象機器と画面属性を示すコメントを追加する。

完全な入力例は[`examples/blink-uiflow2-generated.py`](../examples/blink-uiflow2-generated.py)に置く。

### 必須コメント

次の三種類を、それぞれちょうど一つずつ指定する。

```python
# uiflow2-convert: {"schema":1,"profile":"core2-v1.3-uiflow2-v2.5.3","firmware":"v2.5.3-CORE2"}
# uiflow2-unit: {"name":"rgb_0","type":"rgb","port":"A","leds":3}
# uiflow2-page: {"name":"page0","rotation":1,"background":"#ffffff"}
```

コメントのコロン以降はJSONオブジェクトである。各オブジェクトは指定されたフィールドを過不足なく持つ必要があり、
未知のフィールドも許可しない。

#### `uiflow2-convert`

| フィールド | 必須値 |
| --- | --- |
| `schema` | 整数`1` |
| `profile` | `core2-v1.3-uiflow2-v2.5.3` |
| `firmware` | `v2.5.3-CORE2` |

#### `uiflow2-unit`

現在は次のオブジェクトとの完全一致を要求する。

```json
{"name":"rgb_0","type":"rgb","port":"A","leds":3}
```

Unit名、種類、ポート、LED数のいずれも変更できない。

#### `uiflow2-page`

| フィールド | 条件 |
| --- | --- |
| `name` | `page0` |
| `rotation` | 整数`0`～`3` |
| `background` | `#RRGGBB`形式の文字列 |

背景色は大文字・小文字のどちらでも入力でき、`.m5f2`には小文字で保存する。
`rotation`と`background`は、後述するSetup内の値と一致しなければならない。

変換用コメントはPythonの通常コメントなので、UiFlow2がブロックからPythonを再生成したときに残る保証はない。
再生成Pythonを再び変換する場合は、三つのコメントを追加し直す。

### import前置部

次のimportが同じ順序、同じ意味のASTで必要である。

```python
import os, sys, io
import M5
from M5 import *
import m5ui
import lvgl as lv
from unit import RGBUnit
import time
```

別名、分割、順序変更、追加importは認めない。

### グローバル宣言

importの後に、次の代入が同じ順序で必要である。

```python
page0 = None
rgb_0 = None
```

### `setup()`の定型前置部

`setup()`は引数、注釈、デコレーターを持たず、先頭に次の文を同じ順序で置く。

```python
def setup():
    global page0, rgb_0
    M5.begin()
    Widgets.setRotation(1)
    m5ui.init()
    page0 = m5ui.M5Page(bg_c=0xffffff)
    rgb_0 = RGBUnit((33, 32), 3)
    page0.screen_load()
```

`Widgets.setRotation(...)`と`M5Page(bg_c=...)`には、`uiflow2-page`コメントで指定した値を使う。
GPIO `(33, 32)`とLED数`3`は現在のプロファイル固定値である。

この定型前置部に続けて、対応する`time.sleep(...)`と`rgb_0.fill_color(...)`を0個以上置ける。

### `loop()`の定型前置部

`loop()`も引数、注釈、デコレーターを持たず、先頭に次を置く。

```python
def loop():
    global page0, rgb_0
    M5.update()
```

この後へ、対応する二種類の呼び出しを0個以上置ける。

### メインループと例外処理

モジュール末尾は、V2.5.3生成形と同じ意味のASTである必要がある。

```python
if __name__ == '__main__':
    try:
        setup()
        while True:
            loop()
    except (Exception, KeyboardInterrupt) as e:
        try:
            m5ui.deinit()
            from utility import print_error_msg
            print_error_msg(e)
        except ImportError:
            print("please update to latest firmware")
```

例外処理の省略、変更、文の追加は認めない。

### 表記と意味の一致

全文形式は文字列としての完全一致ではなく、Python ASTとして比較する。そのため、次の差は通常許容される。

- インデント幅や空行
- 一重引用符と二重引用符
- `0xffffff`と`16777215`のような同じ整数値の表記
- 通常コメントの追加

一方、importの分割、文の順序変更、別名使用など、ASTが変わる修正は拒否する。

## 対応しないPython構文

現在は、次をBlockへ変換しない。

- 変数への代入と参照
- `if`、`match`などの条件分岐
- `for`、`while`などのユーザー記述の反復
- ユーザー定義関数の呼び出し
- `try`、`with`、`raise`、`assert`
- リスト、辞書、集合、タプルを使う処理
- 算術、比較、論理演算
- lambda、内包表記
- ファイル、ネットワーク、スレッド、非同期処理
- RGB Unit以外のUnit
- `set_brightness`、`set_color`を含む未検証のRGB API
- Port A以外、LED数3以外、`rgb_0`以外のUnit名
- 複数ページ、追加UI部品、イベントハンドラー

画面部品とCore2内蔵デバイスは今後の拡張対象である。対象API、必要になるPython構文、実装順、
Web IDE／実機での完成条件は[Core2内蔵デバイスと画面部品への対応計画](core2-builtins-extension.md)に記載する。

対応外の処理を含む入力から、一部だけを選んで変換することはしない。全体をエラーにする。

## 生成結果

対応命令は、検証済み[`fixtures/06-port-a.m5f2`](../fixtures/06-port-a.m5f2)を基礎に次の位置へ追加する。

- `setup()`の処理: `page0.screen_load()`に対応するブロックの後
- `loop()`の処理: `M5.update()`に対応するブロックの後

各生成ブロックへ`py2blocks_1`から始まる新しいIDを割り当て、テンプレート内のIDと重複しないことを検査する。
出力は同じ動作になる標準的な直列ブロックへ正規化し、入力元のブロックID、座標、分割方法は復元しない。

全文形式の`rotation`と背景色だけは、外側JSONの`screen`と`components`にも反映する。
短縮形式ではテンプレートのrotation `1`、背景色`#ffffff`を使う。

## エラーと安全性

構文エラー、未対応文、値域外の引数、定型コードとの不一致は`ConversionError`にする。
ASTノードに位置情報がある場合は行番号と桁番号を表示する。

コマンドライン実行では変換エラー時に終了コード`2`を返す。出力は排他的な新規作成で開くため、
同名ファイルが既にある場合は上書きしない。

入力に対して`exec`、`eval`、import実行を行わないため、変換時に入力プログラムがホスト上で動作することはない。

## 実行例

プロジェクトディレクトリで次を実行する。

```sh
python3 convert.py examples/blink.py /tmp/blink-short.m5f2
python3 convert.py examples/blink-uiflow2-generated.py /tmp/blink-full.m5f2
```

生成した`.m5f2`はUiFlow2 V2.5.3の「Import project from local file」で読み込み、
ブロックの編集とPython再生成を確認する。

## 現在の保証範囲

自動テストでは、対応入力のブロック順・引数・一意なID、メタデータ反映、未知コードの拒否、
テンプレートのSHA-256照合、UiFlow2で再保存した`.m5f2`との一致を確認している。

Core2 v1.3とM5STACK-U003をPort Aへ接続した実機では、往復変換後のPythonが
赤2秒、緑1秒、消灯1秒の動作を繰り返すことを確認した。直近の実測は赤2002ms、
緑・消灯が1001～1002msだった。

全文形式でrotationや背景色を既定値以外へ変更する処理は自動テスト済みだが、変更後の`.m5f2`を
Web IDEへ読み込む確認と実機確認はまだ行っていない。

対応範囲を増やす場合は、Python構文だけを追加するのではなく、対象ブロックをUiFlow2 V2.5.3で保存し、
`.m5f2`構造、再生成Python、編集可能性、実機動作を確認してからプロファイルへ加える。
