# P2 ベース＋交換式音源基板の主案

2026-11-18 / revision3.7-pcb-review-j。
[review J](clean-sheet-pcb-review-j/README.md)で[H回路](clean-sheet-schematic-review-h/README.md)を配置・配線した。
base220×142mm、source100×100mm、4層。全228参照、947物理pad、ERC/DRC/未配線/回路図差分0。

PGA2350、Si5351A、base共通PCM1863/PCM5102A、source Core2350B0＋実YM2203Cを維持。
FMのみ同期I2S、SSG受動mixはanalog L、最終muteはDAC許可AND LINE許可。
Hの40接点/KEY6、base GP0～7 data/8～11 control/14～18 audio、source28 GPIOは変更しない。
既存HOST opn1・4MHz、USB-MIDI/CDCと所有権、UNO R3外部機能、RX/6声LED、DIP/RUN/STOP/TESTを維持する要件。

[組立・高さ](clean-sheet-pcb-review-j/ASSEMBLY.md)：UNO予約範囲とsource間は7mm、対向面間下限10.5mm、
base部品<=3mm/source裏面<=4mmなら3.5mmの余裕。128個の単端子MCUソケットと実嵌合の確認が必要。
6か所のSMT近傍ビアは先埋め・平坦化する条件。[電源・配線](clean-sheet-pcb-review-j/POWER-ROUTING.md)も参照。

DIP・STOP・TESTを(203,50)/(203,82)/(203,105)mmへ移動。UNOと音源の座標は不変。
開口なし76×100mmシールドとの32接点・支持3点を照合し、右操作部と音源の間隔は最小11.225mm。
音源はIのCADをそのまま再利用し、ベースの6入力net以外のtrack/viaは維持する。

## 保存履歴と未実施項目

[I](clean-sheet-pcb-review-i/README.md)は194mm幅ベースの保存履歴。
[H](clean-sheet-schematic-review-h/README.md)は変更しない電気設計、[G](clean-sheet-interface-review-g/README.md)はpin配置元。
[F](parallel-module-interface-review-f/README.md)/[E](analog-module-interface-review-e/README.md)/[D](digital-module-pcb-review-d/README.md)/[C](digital-module-review-c/README.md)、
[一体型2.1](PGA2350-STANDALONE.md)/[P1](PGA2350-PROTOTYPE.md)/[F1](FPGA-STANDALONE.md)も保存する。
旧PCB/cardはG40/KEY6非互換。部分挿入も行わない。
JはCAD候補。実物嵌合、負荷電圧・温度・USB・音声測定、PGA/Core firmware移植、実機受入、製造リリースは未実施。
