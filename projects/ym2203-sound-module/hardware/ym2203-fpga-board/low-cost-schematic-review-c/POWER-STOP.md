# 電源・停止・信号・機構

## 電源順序と接続

外部5V→PTC→V5_CARRIERから、base Picossciの入力VBUS（J2.19）、AUX LDO、G40経由音源へ給電。USB-Bの1番VBUSはUSB_VBUS_RAWだけにつなぎ、5V電源系へ並列接続しない。2番D-、3番D+、4番GND。従来のUSBLC6-2と47k/68k分圧・Ioff SchmittによるVBUS検出を保持する。

各MCUの3.3V出力は別レール。baseはV3V3、sourceはMCU_3V3、panelはPANEL_3V3。AUX=V3_AUXとAV3V3は既存回路どおり。新module名のVBUSは外部5Vレギュレータ入力であり、PCのRAW VBUSではない。

panelはGroveピン3 AUX3V3→1N5819→Pico VSYS39。Picoのbuck-boostからPANEL_3V3を生成しLCD・EEPROM・MUX・knobへ給電。Pico36番3V3をAUXへ戻さない。panel USBで更新するときはGroveを外す。逆流diodeだけでSDA/SCL経由の逆給電まで防げるとはしない。

baseモジュール175mA、source250mA、AUXはpanel入力150mAを含め440/500mAの設計予算を据置。実測ではない。base/sourceのLDO損失・AUX銅箔放熱・panelバックライト最大輝度での電流・5V降下を確認する。電源監視ICや独立watchdogを追加して部品数を増やす方針ではない。

## STOPとreset

base GP23→BASE_STOP_N→SWSTOP/GND、RP4=10k pull-up。旧MCP23017 GPA4はNCにする。STOP受付はservice I2C lockを取得せず、GP19 DAC許可・GP22 LINE許可をLOW、GP12 ENABLEをLOWへ進められること。許可2本のANDがPCM5102A XSMTの最終共通消音となる。queue/PCM破棄とowner/session世代更新、遅延完了の取消しはfirmware条件。

音源ENABLE低はURUNOD→CORE_RUN_N→Picossci2B SW1非GND端子の追加線へ接続。Hi-Z時にはtranslator OE無効・YM reset保持。既存SN74LVC1G07/ゲートdefault pullを残す。baseハードRESETはRUNへ直結、Picossci2A J1.18へ接続。ソフトSTOPを独立したCPU hang対策と称さない。

service busがSDA LOWでも、直接STOPとハードRESETの信号経路はI2C依存ではない。実際のソフト応答時間、音声DMAとI2Cの並列動作は移植時に測る。パネルSTOPはuplink受信依存なので、独立ハードSTOPではない。

## I2C・GPIO

HOSTはI2C0 GP20/21、0x42/100kHz。R45/R46の2.2k pull-upを維持。service I2C1はGP26/27、R37/R38=4.7k一組、MCP0x20/panel0x30/ADC0x4A/Si5351A0x60。G40のserviceピン23/24の論理機能も維持し、base内部ラベルだけPANEL_SDA/SCLからSERVICE_SDA/SCLに改名した。

panel uplink GPIO0/1（I2C0 slave）は追加pull-upなし。EEPROM専用GPIO2/3（I2C1 master）に4.7k一組。EEPROMのwrite-cycleや描画でuplinkを長時間stretchしない。32byte20ms poll、5ms transaction期限と300ms local期限はLC-Bの設計契約を継承し、まだfirmwareへ実装したものではない。

Picossci2BはJ2.10がGND、GPIO40..47はJ2.11..18。native symbolと独立検証で48 GPIOを確認した。GP24/25にはLED負荷があるためR5/R6を外してからI2Sへ使う。USB/BOOTSELはbaseの既存firmware commandと各モジュール上buttonを利用する。端面へ出ていない信号を架空のピンへ割り当てない。

## 部品を汎用化した範囲

- 0805厚膜1%、E24/E96値。ADCの6.81kを6.8kへ変更。10kとの分圧比の差は約0.06%で、1%抵抗の公差内の変更。USB VBUS分圧は1%で検討、入力4.4V時の分圧下限約2.58Vを確認する。Schmitt閾値と切断時は実測する。
- URXDATAはTC7SZ125F（SMV/SOT25）、1OE/2A/3GND/4Y/5VCC、5.5V入力・power-down protection。SC70のFUへ無確認で代用しない。
- ADC rail clampはBAT54S-QR（SOT23）、1A1/2K2/3midpoint。旧BAT54Sの接続を保持。
- CACL/CACRは10u50Vの**無極性**Rubycon NXA。通常有極性10uへの置換は認めない。20%公差の定格下限8uは旧有効4.7u条件以上だが、漏れ・低周波・THDと過渡を実測する。旧MLCC選定資料は保存する。
- source5V bulkは22u16V X7Rの1210へ拡大。電源decouplingのX7R/C0Gを安価なY5V/F特性へ置換しない。TLV1117LVのceramic-stability条件も維持。

## 機構・基板費

MCU単端子128本の高価なソケットは廃止し、Picossci2A/2Bは直接はんだ付け。Picoパネルだけ普通の1×20ソケット2本。実YMは600mil DIP40丸ピンソケット1個110円。DIP ICピン用であり、角ピンMCUを丸ピンソケットに差し込む使い方はしない。

G40は普通の2×20メス/オス、pin6の絶縁ブロック＋対向male6除去を条件とする。高価な特殊キーアクセサリーの予算を外したが、逆挿し対策自体を省略したわけではない。実嵌合と支持高さは未確認。

LCDと4ノブの操作面積は保ち、パネルはbase上に重ねない。CACL/CACR（D5×H11）はカード下面でない露出帯へ置く。source下は低背0805/ICを優先。標準M3支持材とM2 LCD支持材を使い、精密シム・特殊スペーサーを前提にしない。合計1,000円を仮枠とし、最終高さBOMは新PCBで確定する。

Picossci2枚、USB-B、Grove2個の5参照はランド未割当。回路端子は確定したが、図面/現物照合前に類似品ランドで代用しない。次工程で標準0.3mmビア、HASL、100mm外形へ無理なく配線できるかを確認する。120mmへの拡大は同条件の参考差額約3,904円で比較し、部品を数十円安くするために板代を数千円増やす判断はしない。
