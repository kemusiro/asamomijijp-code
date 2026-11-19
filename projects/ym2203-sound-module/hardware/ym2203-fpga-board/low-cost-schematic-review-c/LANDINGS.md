# ランドと実装確認の残件

回路図の5参照でfootprint未割当：base UBASE/JUSB/JEDIT、module USOURCE、panel JUPLINK。
端子番号とnetは接続済み。新PCBを作成する工程で以下を確認してから割り当てる。

- Picossci2A：40端面端子1.27mm、26.67×15.24mm。メーカー寸法図を起点に、端面はんだランドの張出し・排他領域・RESET/USB位置を確認。
- Picossci2B：56端面端子1.27mm、36.83×17.8mm。J2.10のGND抜けを含むpin順、JP6/7、SWDとRESET追加線、R5/R6の作業領域を確認。
- USB-B5075BR：メーカーdrawingの接点番号1VBUS/2DM/3DP/4GND、shield2脚と実穴寸法・基板端からの位置を確認。既存USB-Cfootprintを流用しない。
- Grove110990037：2mm/4接点、L型、部品10×8.65×H5mm。資料が取付穴とtop/bottomviewを明確に定義していないため現物で照合。別型のverticalGroveを無断流用しない。
- NP入力cap：D5×H11mm、2mmリード。一般CP footprintの＋silkは最終PCBで除きNPと表示。sourceカード重なり領域へ置かない。
- CMOD5：22u16V X7R1210、Pico panelはModule:RaspberryPi_Pico_Common_THT。標準スルーホールソケットに合わせ、カード/パネルの裏面突起・USB plug・MCU buttonを確認。

ERC0・pin/netlist一致は上記の寸法/嵌合/層数/配線成功を保証しない。現時点ではGerber/PCB/DRCは作成・実行していない。
