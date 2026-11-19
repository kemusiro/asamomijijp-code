# review K/L 公開前検証

2026-11-20。review KのCAD、製造・購入資料L、およびその検証に必要な未コミットの前段資料をまとめて公開する。

保存用のSHA一覧にmacOSの`.DS_Store`とKiCadの個人設定`.kicad_prl`が含まれていたため、これらを公開検証の必須入力から除いた。回路図・PCB・Gerber・購入数量や価格・firmwareは変更していない。元の一覧は`original-manifests/`へそのまま保存し、公開版で変わった依存ハッシュと除外項目を`publication-adjustments.json`に記録する。個人設定ファイル自体は公開しない。

| 保存対象 | 元の一覧件数 | 公開版件数 |
| --- | ---: | ---: |
| 回路図E | 306 | 303 |
| PCB F | 81 | 78 |
| PCB K | 265 | 263 |
| 製造L | 217 | 213 |

過去の`verification.json`等は当時の検証記録として保持したため、上記件数はその記録と異なる。今回の再検証は公開版SHA一覧と個人設定を除いた作業コピーを使う。CADとCAMの内容、276参照、85購入行、送料・予備枠込み27,358.48円の概算は従来どおり。見積は最終カート・確保済み在庫・発注価格を意味しない。

ハッシュの検証（標準Pythonのみ）:

```sh
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/publication-review-kl/verify.py
```

ERC/DRCはKiCad 10.0.5と対応するpcbnew Python、CAM検証はGerbonara 1.6.3を使い、各K/Lの手順に従う。再生成は作業コピーで行い、保存した納品ソースと過去の結果を上書きしない。ZIP・XLSXはGit管理外のローカル生成物とし、再生成ツールとテキストのGerber/CSVを管理する。実物嵌合・製造業者のCAM審査・P2 firmwareと実機受入は未実施。

公開用作業コピーでのERC/DRC・端子/G40・CAM・負例7件・購入表の再検証結果は`revalidation.json`に記録する。PCBハッシュは保存済み入力と一時的な再充填出力を区別している。
