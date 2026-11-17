# P2 共通コネクタ仕様

2026-11-18。主案は[review I配置・配線済みPCB](clean-sheet-pcb-review-i/README.md)。Hの回路・40接点を変更しない。
Gの新規40接点・連続GPIO配置を維持。旧基板のpin/KEY/GPIO互換は撤廃し両基板を新規設計する。

- 2×20/2.54mm、KEY6。[電気接続付きCSV](clean-sheet-schematic-review-h/connector.csv)/[pin配置SVG](clean-sheet-interface-review-g/pinout.svg)。
- data GP0～7 / control GP8～11。SPI0とparallelは排他、内部I2C1は別線。
- analog L/GND=37/38、R/GND=39/40、35/36 GND guard。clock25～30、任意I2S31～34。
- ADC共通、48kHz I2S base master。Hはanalog source impedance目標<=4.7kΩへ調整し、電気仕様5.1-draftとした。
- base44 GPIO/予備3、source28 GPIO。UNO外部機能・HOST/USB/停止契約を保持する要件。

[H電源・音声](clean-sheet-schematic-review-h/POWER-AND-AUDIO.md)、[制御・停止](clean-sheet-schematic-review-h/CONTROL-AND-STOP.md)、
[base GPIO](clean-sheet-interface-review-g/gpio-proposal.json)、[source GPIO](clean-sheet-schematic-review-h/source-pins.json)。
Iでは全40接点の嵌合座標を照合し、両基板DRC/未配線/回路図差分0。
[組立高さ](clean-sheet-pcb-review-i/ASSEMBLY.md)は条件付きモデル。新firmware・実機受入・実物嵌合は未実施。
