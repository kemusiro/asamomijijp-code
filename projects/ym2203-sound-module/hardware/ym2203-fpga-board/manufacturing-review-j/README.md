# review J：製造データと購入用部品表

2026-11-18。対象は[review Jベース・音源](../clean-sheet-pcb-review-j/README.md)と
[開口なしシールドB](../editor-shield-review-b/pcb-review-b/README.md)。
回路・GPIO・配線を変更せず、3枚のGerber X2／Excellonを作成した。
**試作の発注検討用データ。P2実機受入・ソケット現物合わせ・ADC結合容量の確定は未完了**。
この資料は新しい製造準備記録であり、過去のDRC・受入記録を更新しない。

| 基板 | 外形の中心線寸法 | 層数 / 厚み | 最小実配線幅 | PTH穴・長穴数 | NPTH穴・長穴数 |
| --- | --- | --- | --- | ---: | ---: |
| base / p2-base-j | 220×142mm | 4 / 1.6mm | 0.17mm | 433（長穴4） | 14 |
| module / p2-ym2203-i | 100×100mm | 4 / 1.6mm | 0.18mm | 299 | 4 |
| shield / p2-editor-b | 76×100mm | 2 / 1.6mm | 0.25mm | 174（長穴8） | 9（長穴1） |

音源基板はJで変更しないIの設計をそのまま製造するため、ファイル名・シルクのI表記を維持する。
シールドは矩形4辺で大きな開口・外周切欠きなし。取付穴・端子穴・encoder位置決め穴は残す。
KiCadのjobにある外形サイズは幅0.10mmのEdge.Cuts線幅を含むため上表より各0.10mm大きい。
**切削はEdge.Cuts線の中心で行い、jobの線幅込み寸法へ拡大しない。**

## 配布内容

- `gerbers/base/`、`gerbers/module/`、`gerbers/shield/`：銅箔・マスク・シルク・外形・PTH/NPTH・job。
- `inspection/`：ドリルマップSVGとCAM再読込による表裏プレビューSVG。発注データとは分離。
  ドリルマップの行末空白だけを正規化し、加工用Gerber/Excellonの内容は編集しない。
- `verification/`：新規ERC/DRC、CAM幾何照合、元データのSHA-256と出力一式のmanifest。
- [購入表](procurement/README.md)：90購入行、基板ごとの数量、1/5セット、販売単位、調達先、残る確認事項。
- `tools/`：履歴CADを変更しない再出力・検査・数量表再生成スクリプト。

Gerberは今回明示的に必要となった製造用のテキスト成果物として管理する。
発注用の3つのZIP、まとめZIP、Excel、PNGはプロジェクトのGit管理外
`outputs/p2-review-j-fabrication-20261118/`へ置く。ZIPは**各基板を個別に**アップロードする。
まとめZIPには3基板と説明・購入表を入れるため、製造業者への単一基板アップロードには使わない。
ZIPとExcelのハッシュは同出力先の`SHA256SUMS.txt`に記録する。発注・決済・公開Releaseは行っていない。

## 製造指定

| 項目 | 指定 |
| --- | --- |
| 材料・板厚 | FR-4、1.6mm公称。3枚とも同じ厚み |
| 層順（base/module） | F.Cu → In1.Cu → In2.Cu → B.Cu |
| 層順（shield） | F.Cu → B.Cu |
| 銅厚 | 各層35µm公称。job内の0.48mm×3誘電層はモデル値。業者標準4層構成を見積時照合 |
| 表面 | 両面ソルダーマスク、両面シルク。手実装しやすい平坦なENIGを第一候補に見積 |
| 穴 | Excellonをmm・絶対原点、PTHとNPTHを分離。長穴はroute表記を維持 |
| 最小via | base/module：穴0.20mm・ランド0.45mm。shield：穴0.30mm。業者の対応能力で見積 |
| クリアランス | base/moduleのプロジェクト設定0.15mm。shieldの設定はnativeプロジェクト参照 |
| 外形 | 1枚単位、4直線の矩形。Vカット・ミシン目・パネライズ指定なし |
| ペースト・実装 | 今回は手実装。ペースト層・ステンシル・PCBA発注は含めない |
| 原点・裏面 | 3枚ともPCB絶対原点。裏面Gerberも反転せず、製造業者の通常処理へ渡す |

1枚分のデータを複製して5枚に並べない。数量は発注画面で各基板に指定する。
4層のIn1はGND参照、In2は主に電源の補助面。層入れ替えは不可。
USB等のインピーダンスを実測・保証したデータではなく、別の管理インピーダンス指定は加えていない。
発注先で0.20mm穴・長穴・細線・板寸法の追加費用とCAMプレビューを確認する。

## 組立時に守る寸法

詳細は[review J組立条件](../clean-sheet-pcb-review-j/ASSEMBLY.md)を正本とする。

- 基板間G40：SSW-120-02-G-D＋TSW-120-07-G-D。雌の6番を塞ぎ、雄の6番を抜去。
  音源側JMODは裏面実装。面間11.05mm公称、10.5mm以上。32接点版や高さ違いは不可。
- UNO：SSWの指定高さ8.51mm＋シールドオスの樹脂2.5mmを基本に面間11.01mm公称。
  シールド側32接点は裏面。ICSPには挿入せず、H9/H10/H12の3点で支持する。H11にネジを入れない。
- MCU：独立レセプタクル64個ずつ、計128個。MCU下面9.5mmの治具で合わせる。
  4辺の汎用ソケットストリップでは隅の樹脂が干渉する。初回少数で嵌合・挿入3.5～4.5mmを確認する。
- base上SMTは高さ3mm以下、音源下面突出4mm以下、シールド裏面リード3mm以下。
  音源下3.5mm・シールド下4.5mmの空間はこれらの条件を満たした場合の値。
- LCDは現行1.54inch M154-240240-RGB、M2支柱12mm×4。ボリューム4個とS-42を維持。
  LCD部品下面突出3.5mm以下、下の部品4mm以下を前提とする。古い1.3inch図面と混用しない。
- M3支柱は10mm＋ワッシャー/シムで面間に合わせ、コネクタ高さを実測して締める。
  支柱で基板を曲げて高さを合わせない。底脚は8mm以上（購入候補10mm）。

手はんだ時に先埋めして平らにする6か所は次のとおり（各基板左上基準、mm）。
工場での樹脂充填指定を自動追加したものではない。実装前に穴のはんだ吸い込みと平坦性を確認する。

| 基板 | pad | net | via座標 | 穴mm |
| --- | --- | --- | --- | ---: |
| base | RBSCK/2 | GND | 94.2125,15.5 | 0.30 |
| base | RADCDATAPD/2 | GND | 100.7125,34 | 0.30 |
| base | UESD/2 | GND | 133,12.5625 | 0.30 |
| module | ULINK0/10 | GND | 22.0625,27.65 | 0.30 |
| module | UALERT/3 | GND | 30.1625,57.95 | 0.30 |
| module | U8/7 | YM_D4 | 51.1375,47.3 | 0.20 |

## 検証結果と限界

KiCad10.0.5で3枚を作業コピーへ読み込み、zoneを再充填して保存後、ERC/DRC/未配線/回路図差分がすべて0。
baseのtitle/revisionだけは、履歴に残るI表記を**出力コピー内だけ**J/3.7-Jへ直した。
音源・シールドと元の全CAD/回路図/レポートは変更していない。

Gerbonara1.6.3（Apache-2.0、検査ツールとして使用・ソースは同梱しない）で全Gerber/Excellonを読込。
層セットとjob、4辺の外形、933個の穴/長穴をnative形状へ1対1照合し、表裏6プレビューを確認した。
Excellonの丸めは最大0.0005mmで、許容0.0006mm以内。銅箔全プリミティブをnativeへ数学的に逆照合した意味ではない。
G90ヘッダー位置、KiCad RoundRectの余剰パラメータ、未出力paste層についての既知パーサーメッセージのみ許容し記録した。

欠落穴、0.1mm穴ずれ、内層欠落、job層数違い、未配線レポート混入の5変異を拒否した。
既存Jの12契約/12拒否変異・積層18契約/18拒否変異・6回帰試験、シールドの4機械試験も再実行した。
納品する再出力スクリプトも別の空ディレクトリで通し実行し、native形状とCAM検査結果の一致を確認した。
購入表は274参照を一度ずつ対応付け、3つの銅箔ジャンパーを購入品から除外。
Excelは数量・手持ち・販売単位の変更と空欄/0を再計算し、数式エラー0、両タブの表示を確認した。
生成・再計算にはartifact-tool2.8.129を使用し、保存XLSXのZIP CRCとエラーセルなしも検査した。
Excelアプリでの再計算・発注先CAM審査・現物嵌合・新基板での音声/USB試験はまだ実施していない。

既存HOSTのopn1/4MHz・0x42/100kHz・YM22S002・64byte STATUS・PUSH32・FIFO1024・1000ms lease、
USB-MIDI/CDCの制御権とSTOP処理は変更しない設計要件。
**Rev Cでの実機受入をP2へ転記しない。P2用firmware移植とHOST/MIDI/停止回帰は今後の工程**。

## 再出力と再検査

プロジェクトルートから実行。KiCad10.0.5をPATHへ置き、pcbnewを使えるPythonと
Gerbonara1.6.3を入れたPythonを指定する。`--work`は未作成のディレクトリを使う。

```sh
python3 hardware/ym2203-fpga-board/manufacturing-review-j/tools/verify.py
python3 hardware/ym2203-fpga-board/manufacturing-review-j/tools/export_cam.py \
  --hardware-root hardware/ym2203-fpga-board \
  --work outputs/review-j-cam-rebuild \
  --kicad-python python-with-pcbnew \
  --cam-python python-with-gerbonara
python-with-gerbonara hardware/ym2203-fpga-board/manufacturing-review-j/tools/test_cam.py \
  outputs/review-j-cam-rebuild
```

`source-manifest.json`は入力、`manifest.json`は配布テキスト成果物のSHA-256。
再出力時の日時は変わるため、新しい出力のSHAは新しい記録へ保存する。
既存manifestを更新して古いデータに見せかけない。
`tools/build_catalog.py <repository-root> <new-output-directory>`で購入CSV/JSON/参照表を再生成できる。
価格再調査は明示して行い、`procurement/supplier-observations.json`の確認日を伴う別の記録として残す。

参照：[KiCad CLI](https://docs.kicad.org/10.0/en/cli/cli.html)、
[Gerbonara](https://gerbolyze.gitlab.io/gerbonara/api-concepts.html)。
