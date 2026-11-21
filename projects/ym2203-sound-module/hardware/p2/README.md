# P2 採用設計 — base T / YM2203 module T / editor N、FAB U

編集可能なCADは`cad/`、発注に使ったCAMは`artifacts/*/gerbers/`。
ベース100×100mm・4層、音源100×80mm・2層、編集100×76mm・2層。基板各5枚、実装1セットを想定。
KiCad10.0.5。**発注済み・P2 HAL未移植・実機未受入**。Rev CのUF2をP2へ書かない。

[組立](ASSEMBLY.md)／[音声・機構](ASSEMBLY-AUDIO.md)／[互換性要件](COMPATIBILITY.md)／[発注条件](ORDER.md)／[一般BOM](procurement/README.md)。
[実装BOM](assembly/design-bom-1set.csv)は302参照、[G40](assembly/g40-pinout.csv)、[追加配線](assembly/module-wire-map.csv)、[GPIO](interfaces/gpio-map.csv)を併用する。

採用CAD/CAM、配線済み形状、原本の受入記録は変更していない。
`requirements/approved-topology.json`は採用した現在の全端子・値・フットプリントを固定する。旧レビューや購入カートを読む検査は不要。
`provenance/`は元の製造記録であり、移設後の検査入力ではない。元レポートの日時・ハッシュを更新して合格を装わない。

[ベース1枚図](readable/base/schematic.svg)／[音源1枚図](readable/module/schematic.svg)／[編集1枚図](readable/panel/schematic.svg)。

## 再現・検証

Python3とGerbonara1.6.3を使う。`<pcb-python>`は`pcbnew`をimportできるKiCad付属Python。
`<cam-python>`はGerbonaraを入れたPython。どちらも作業ディレクトリは本書の場所。

```sh
python3 tools/contract.py
python3 tools/test_contract.py
<pcb-python> tools/check_native.py
<cam-python> tools/verify_cam.py . --no-previews
<cam-python> tools/test_cam.py .
python3 tools/package.py
```

ZIPは`local-output/gerbers/`に再生成する。3件とも発注時ZIPとSHA-256が一致することを`expected-archives.json`で検査する。
新しいKiCad出力の検査は`tools/regenerate.py`を使う。正本を直接変更せず別の作業コピーへ再出力し、ERC/DRC・回路図整合、全銅形状・穴・層構成を検査する。
Gerber再出力では作成時刻コメントだけ変わり得るため、発注ZIPの完全一致とCAD再出力の一致を区別する。

```sh
python3 tools/regenerate.py --work /tmp/p2-native-check --pcb-python <pcb-python> --cam-python <cam-python>
python3 readable/tools/generate.py base module panel
python3 readable/tools/check.py --boards base module panel
```

読図用の再生成コマンドは別の作業コピーで実行する。生成後のレポートは日時等が変わるため、配布時のソースハッシュ検査とは区別する。
旧配線試行や旧購入資料を用意する必要はない。読図用回路図は基板ごと1枚に再生成し、実際のネイティブ接続と照合する。
静的検査とモデル試験は電源・USB・音声・機構の実機試験を代替しない。
