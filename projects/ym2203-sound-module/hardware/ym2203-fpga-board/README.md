# 次期音源基板：P2ベース＋交換式音源基板

2026-11-18。主案は[review J：220mm幅・右側操作部の配置配線済みPCB](clean-sheet-pcb-review-j/README.md)。
ベース220×142mm・音源100×100mm、4層。Hの全228参照・値・GPIO・pin/netを維持した。
両基板ERC/DRC/未配線/回路図差分0。40嵌合位置、947 pad、38 UNO接点、64 Core接点を照合した。

| 資料 | 内容 |
| --- | --- |
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

F1/JT03等の比較資料も保存するが、RTL・PCシミュレーターは今回のP2設計一式に含めない。
現行のCAD検証はreview Jと開口なしシールドBの手順を使用する。

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
| JT03音源内蔵RTL（別変更） | 実YMをFPGA内音源へ置換、固定4 MHz相当 |
| [旧算術検証一覧](verification/README.md) | 旧条件の入力・算術・資料整合性 |

Rev Cの承認済みGPIO・UF2・受入結果は維持する。
P2の回路図、製造用BOM、PCB、部品購入はまだ確定していない。


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
