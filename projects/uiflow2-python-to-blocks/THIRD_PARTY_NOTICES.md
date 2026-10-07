# 第三者要素

UiFlow2はM5StackのWeb IDE。Blockly由来のXML構造、ブロック識別子、生成コードを観察している。
M5Stack/Blockly本体のソース、画像、フォント、ライブラリは同梱していない。

fixtures/*.m5f2とresultsの.m5f2・roundtrip.pyは、今回UIで作成した最小実験設定とUiFlow2による生成物である。
UiFlow2生成部分までリポジトリ既定BSD-2-Clauseが適用されるとは主張しない。
公開前に生成物の配布条件・必要な表示を確認する。それまではローカル検証用・未公開として扱う。
公式sticks3音声サンプルは一時領域で静的に解析し、全文を本プロジェクトへ複製していない。

M5Stack公式`uiflow-micropython`はMIT Licenseで公開されている。タグ`2.5.3`（コミット`50e440780492aa847378c7d3477ab912f7063bac`）のRGBドライバー、文書、`.m5f2`／Pythonサンプル対を参照した。第三者コード本文は複製せず、固定参照、SHA-256、抽出した仕様を`profile.json`と`docs/official-uiflow-micropython-2.5.3.md`へ記録している。

公式資料:
- https://uiflow2.m5stack.com/
- https://github.com/m5stack/uiflow-micropython/tree/2.5.3
- https://github.com/m5stack/uiflow-micropython/blob/2.5.3/LICENSE
- https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/unit/rgb.py
- https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.py
- https://github.com/m5stack/uiflow-micropython/blob/2.5.3/examples/unit/rgb/rgb_core.m5f2
- https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/unit/rgb.rst
