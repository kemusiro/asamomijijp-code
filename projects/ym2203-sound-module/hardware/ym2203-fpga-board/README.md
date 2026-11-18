# 次期音源基板：P2ベース＋交換式音源基板

2026-11-18。**ベースJ・4層＋音源K・2層＋開口なしシールドB・2層を主案として採用した。**
今回の発注入口は[主案：各5枚・部品1セット](primary-order-5pcb-1set/README.md)。
3基板の製造用Gerber、購入用CSV/Excel、調達先別一覧、数量とSHAをまとめた。PCBは計15枚、実装3枚、予備12枚。
P2実機受入・現物嵌合・部品確認事項は未完、PCB発注・部品購入・支払いは未実施。

[2層比較版K](clean-sheet-pcb-review-k/README.md)のベースは比較用として保存し、今回の発注には含めない。
[層構成の検討A](layer-study-review-a/README.md)、J/Iの旧CADと従来の製造・見積記録も保持する。
[製造・送料比較K](manufacturing-review-k/README.md)は両案の検証・見積の記録で、今回の選択は主案注文資料を正本とする。
G40・UNO・GPIO・HOST/USB-MIDI・停止仕様は維持する要件。新PCBでの実機合格は未確認。

| 資料 | 内容 |
| --- | --- |
| [今回の主案注文一式](primary-order-5pcb-1set/README.md) | J4/K2/B2、各5枚・部品1セット。選別済みGerber・90購入行・部品表Excel |
| [製造・送料比較K](manufacturing-review-k/README.md) | 4種類のCAM・個別ZIP、主案4/2と比較2/2の各5枚・部品1セット見積 |
| [2層比較版K](clean-sheet-pcb-review-k/README.md) | 新規2層PCB・13抵抗の配置変更・電気/積層照合。従来CADを保存 |
| [層構成の検討A](layer-study-review-a/README.md) | 主案4/2と比較案2/2。既存内層配線の読取監査、GND/USB/音声・電源・製造比較の方針。当時は新CAD未作成の保存記録 |
| [今回の購入表・PCB送料比較](manufacturing-review-j/procurement/order-5pcb-1set/README.md) | 基板各5枚・部品1セット。15枚中3枚実装、12枚予備。JLCPCB/PCBWay匿名送料見積、数量計算を更新 |
| [製造Gerber・購入用部品表](manufacturing-review-j/README.md) | 3枚のGerber/Excellon・新規ERC/DRC0、90購入行・274参照対応。未確定容量/嵌合条件あり |
| [review J PCB・BOM・検証](clean-sheet-pcb-review-j/README.md) | 配置配線済みCADと12電気契約＋18積層契約・6回帰試験 |
| [配置図](clean-sheet-pcb-review-j/layout.svg) / [組立・高さ](clean-sheet-pcb-review-j/ASSEMBLY.md) | 対向面間・ソケット・UNO・6か所のビア先埋め条件 |
| [電源・配線](clean-sheet-pcb-review-j/POWER-ROUTING.md) | GND参照面、電源補助面、USB/音声の記録と測定課題 |
| [H回路](clean-sheet-schematic-review-h/README.md) | 改変しない電気設計の参照元 |
| [G接点/GPIO](clean-sheet-interface-review-g/README.md) | G40/KEY6のpin配置元 |
| [P2構成](P2-MODULAR.md) / [接続I/F](P2-MODULE-INTERFACE.md) | 現主案への入口 |
| [音源比較](P2-SOUND-MODULES.md) | PSG・音声合成・ラジオ等の候補 |

既存HOST opn1・4MHz、USB-MIDI/所有権/STOP/lease、UNO外部機能を維持する要件。
base44/47 GPIO、予備35～37、source28/46 GPIO。旧base/cardの物理互換は要求しない。
P2 firmwareと実機回帰、実部品の嵌合、電源・USB・熱・音声の測定は未完。DRC0を製造/実機合格と扱わない。
[active-plan.json](active-plan.json)と[p2-modular-plan.json](p2-modular-plan.json)を正本入口とし、過去の設計・受入は保存する。

音色編集用の[UNOシールド review B](editor-shield-review-b/README.md)も設計した。
秋月調達優先の4ノブ・encoder・1.54インチLCD・64音色EEPROM保存・USB CDC JSON取得の仕様と接続済み回路図。
ERC0、32接点/159pad照合、保存等13モデル試験。購入小計3,160円（基板等別）。
回路図review A/Bと開口付きPCBは保存。review Bの[開口なし2層PCB](editor-shield-review-b/pcb-review-b/README.md)へ更新し、
ERC/DRC/未配線/回路図差分0、166padと32嵌合座標を照合。LCD・シールド形状とUNO座標は維持。
JではDIP・ベースSTOP/TESTを音源基板の右へ移し、音源から最小11.225mm。シールドの開口・切欠き0。
シールド下面のSMT空間4.5mm等は条件付きモデル。現物嵌合・P2 firmware・実機受入は未完。
旧[review I](clean-sheet-pcb-review-i/README.md)と、その上に載るシールドBの過去の検査記録も保存する。

## F1の実装・検証資産（保持）

[F1 FPGA単独案](FPGA-STANDALONE.md)と[RTL](../../fpga-standalone/README.md)は
再利用・比較資産として保持する。FPGAを使わないP2へ検証結果を流用しない。
F1のI2C／音声／可変clock／USB RTL、ULX3S 85Fの49padと3 seed通常P&R、
[165部品のキャリア回路図レビューA](carrier-f1/README.md)、
[Diamond準備](../../fpga-standalone/boards/ulx3s/diamond/README.md)の記録を残す。
F1のDiamond実行・PCB・実機受入も未完。

## 比較資料と過去の検討

旧案・実測値は、それぞれの条件での記録として残す。P2の資源や実機合格へ流用しない。
M1のJSON内statusは検討時点の記録であり、現在の主案P2はactive-plan.jsonで判断する。

| 資料 | 元の条件 |
| --- | --- |
| [M1](MODULE-HAND-SOLDERED.md) | Pico 2＋UP5Kモジュール、狭ピッチ手実装。31本の旧端子予算 |
| [旧直接実装案](INITIAL-DIRECT-MOUNT.md) | 裸UP5K、Picoからの構成ロード、業者SMT等 |
| [実装・小型化案](ASSEMBLY-AND-SIZE.md) | 直接実装と片面SMT・部分委託の比較 |
| [Economic BOM](ECONOMIC-BOM.md) | 5枚、業者SMT、2 mm以上の自前実装 |
| [H1](HAND-SOLDERED.md) | 1.27 mm以上、Si5351・DACもモジュール |
| [JT03音源内蔵RTL](../../fpga-jt03-minimal/README.md) | 実YMをFPGA内音源へ置換、固定4 MHz相当 |
| [旧算術検証一覧](verification/README.md) | 旧条件の入力・算術・資料整合性 |

Rev Cの承認済みGPIO・UF2・受入結果は維持する。
review Jと開口なしシールドの製造データ・購入候補を[製造準備資料](manufacturing-review-j/README.md)へ追加した。
現在の購入条件は[基板各5枚・部品1セット](manufacturing-review-j/procurement/order-5pcb-1set/README.md)。
従来の1/5セット比較と製造検証記録は保存し、今回の数量表・見積を別記録にした。
ADC結合容量の型番確定・ソケット等の現物合わせ・他店見積・部品購入・P2実機受入は未完了。

I2C制御部分の[実装・検証結果](../../fpga-standalone/SESSION.md)を追加した。

## P2 revision 2.1 回路図レビューA（保存履歴）

[carrier-p2](carrier-p2/README.md)にPGA2350実端子、UNO R3形状3.3Vヘッダー、
周辺回路の接続済みKiCad回路図と未配線配置確認データを追加した。
GPIO47本の周辺機能静的照合、全netlist一致、ERC違反0件。
既存HOSTは未変更。このA時点では配線済みPCBは未作成。一体型の配線候補は下記のレビューBを参照。P2ファームウェア移植・実機受入は未完。

## P2 revision 2.1 / PCBレビューB（分離前の保存履歴）

[レビューB](carrier-p2/pcb-review-b/README.md)に電源容量・ソケット高さの検討と、
164部品の回路図・配線済み4層PCB候補を追加した。DACとUNO 3V3供給を500mA AUX LDOへ分離し、
PGA2350内蔵300mA電源の設計予算を259.4mAとした。一般2列ソケット4個は端部が干渉するため、
64本の単端子ソケットを候補にし、実物の挿入・保持・高さ確認を残す。
47 GPIO、UNO接点座標、既存HOSTは変更しない。回路・DRCの結果はBの検査記録を参照。
P2専用ファームウェア、実組立、電流・温度・USBインピーダンスの確認、製造リリースは未完。
レビューAの回路図と検査記録は履歴として保存する。
