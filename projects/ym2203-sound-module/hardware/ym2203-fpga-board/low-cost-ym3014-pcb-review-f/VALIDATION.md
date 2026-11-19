# 検証手順と適用範囲

KiCad10.0.5 native CLI、KiCad同梱Python3.9.13/pcbnew、生成/独立検証のPython3.15.2を使用。外部ルーターはFreerouting2.1.0、局所配線は本プロジェクトのグリッド探索と、ネイティブ銅箔形状による接触/クリアランス判定を使用する。JAR・実行ファイル・メーカーPDFは配布しない。

## 正本

最終`.kicad_pcb`が配線の正本。`generate.py`は接続済み回路図とcircuit.json、BOMをEから再生成する。`tools/build_pcb.py`は初期配置であり、**完成PCBに実行すると配線を置換する**ため、再検討用の別コピーだけで使う。最終配線を初期配置ジェネレーターだけから再現できるとは案内しない。

`tools/footprints.py`はメーカー寸法に基づく独自ランド。標準KiCadライブラリを検索できる環境で実行する。配線探索の一時データや外部ルーターは配布対象外。完成PCBとネイティブ検証結果を保存する。

## ネイティブ検査

`python3 tools/native_checks.py --pcb-python <pcbnewを読み込めるPython>`で全3枚を検査できる。回路図を再生成するが、配線済みPCBを初期配置に置換しない。

個別には各基板のフォルダで、対応するPCBと回路図に対して実施する。

```sh
kicad-cli pcb drc --refill-zones --save-board --schematic-parity \
  --format json --severity-all --exit-code-violations \
  -o drc.json p2-base-lc-f.kicad_pcb
```

音源は`p2-ym2203-lc-f.kicad_pcb`、パネルは`p2-panel-lc-f.kicad_pcb`に置換する。違反、未接続、回路図との差分を別々に数える。単にDRCコマンドの起動成功を接続合格と扱わない。

回路図は`generate.py --check`でnative ERCとXML netlistを生成・照合する。検証済みPCBの`.kicad_pro`は設計規則を持つため、回路図再生成で上書きしない。プロジェクトの安全停止契約/GPIOを変更せず、既存Review Eの全277部品の値と全端子を照合する。

`tools/verify_pcb.py`をKiCadのPython環境で実行し、次を独立に確認する。

- ネイティブERC/DRCの有効な検査、回路図差分、未接続。
- 277参照のすべての端子番号とネット。NCはunconnectedネットであること。
- G40の全40端子の実装XYと表裏。originと端子1だけの比較ではない。
- 外形/層数、全ビアの0.6mm径/0.3mm穴、0.2mm以上の線幅。
- review Eと保存済みC/L/K/ファームウェア等のハッシュ。

## 残る確認

DRCは電気的・機構的動作の保証ではない。現物の1:1ランド合わせ、G40ソケットの接触長、MCU下面のテストパッドと配線、SWD/RUNの手配線、LCD裏面リード/ケーブル、支柱高さを仮組みする。USBはFull-Speed用の短配線としており、指定スタックアップで90Ω差動を計算/保証した基板ではない。

電源温度、Si5351A/YMクロック、YM3014B-FのCLK/SD/LOAD波形、ADCレベル/クリップ、DAC左右出力、STOP/リース/USB切断時の実ミュートはP2ファームウェア移植後に実測する。Rev Cでの受入結果をP2の実機合格として流用しない。支持材と新Gerberの送料込みCAM見積も発注前に確認する。

## DRC規則の範囲

個別違反の除外リストは空に保つ。既存プロジェクトから引き継ぐ非適用の検査（フットプリント属性/フィルター、未定義courtyard、ビア中心と配線端点の一致、tuning profile）は`verification.json`の`ignored_checks`へ列挙する。クリアランス、短絡、未接続、穴間隔、courtyardの重なり、シルク、回路図差分は有効のまま検査する。未定義courtyardを含む部品は寸法図と投影図でも確認する。

ベースIn1はGNDゾーンを主とし、停止制御`L_MOD_CTL1`の局所的な迂回配線だけを許す。内層全面を無配線の連続GNDと案内しない。再充填後のGND接続とクリアランスをネイティブDRCで確認し、内層迂回の総長も検証JSONへ記録する。

## 結果（2026-11-19）

3枚すべてnative ERC=0、native DRC違反=0・未接続=0・回路図差分=0。個別DRC除外は0。全277参照の端子とネット、G40全40端子の表裏/XY、保存版のハッシュを`verification.json`に記録する。これは製造後の実機受入記録ではない。

5V共有幹線は細い信号用配線だけに頼らず、ベースIn2に`V5_CARRIER`電源ゾーンを追加して補強する。In2の既存信号はクリアランス付きで併用する。In1のGNDを基本帰路とする。USB配線はFS用で、90Ω差動の製造保証は行っていない。
