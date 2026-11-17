# P2拡張：UNO R3ヘッダー・clock DIP・操作ボタン・6声表示・USB WYM1

2026-11-15。P2 revision 2.1の構成要件。ユーザーがUNO R3形状・3.3V信号を選択した。
FPGAなし、PGA2350＋実YM2203C＋Si5351Aを維持し、6項目を追加する。
[基本構成](PGA2350-STANDALONE.md)、[構成データ](pga2350-standalone-plan.json)、
[Arduino信号表](pga2350-arduino-header.csv)、[DIP表](pga2350-clock-switches.csv)、
[操作表示I/O表](pga2350-expander.csv)を対にする。

**回路図・GPIO割当ては[review A](carrier-p2/README.md)で具体化・静的検査済み。ファームウェア実装・実機受入は未完。**
新規USB転送のbyte仕様とP2ファームウェアは次段階。PCBレビューBは164×124mmの配線候補で、実物確認後に製造レビューする。既存HOSTのwire／player／Rev C GPIOは変更しない。

## 1. UNO R3形状の3.3V拡張ヘッダー

- UNO R3と同じ信号名・ヘッダー構成：digital 1x8＋1x10、power 1x8、analog 1x6。
  2x3 ICSP位置にはSPIの別名端子を追加する。旧UNO特有の4.064mm間隔とICSP位置を公式CADと照合し、配置確認用PCBへ反映した。
- D0..13とA0..5の20本はPGA2350へ直結する拡張専用signal枠。YM data／制御／FM／I2Sと共用しない。
  物理GP番号は[割当表](carrier-p2/pins.csv)を参照。P2専用で、既存Rev CのGP番号は変更しない。
- D0/D1はUART、D10/11/12/13はCS/COPI/CIPO/SCKのnative SPIを目標とする。
  PWMはD3/5/6/9/10/11を目標にpin muxを検証する。UNO用ArduinoスケッチのAPI互換を実装済みとはしない。
- **IOREF=3.3V、信号電圧3.3V。5V UNOシールドの無条件互換ではない。**
  各shieldのI/O、pull-up、消費電流、占有pinを確認する。特にGPIO40..47側ADCへ5Vを入れない。
- A4/SDA、A5/SCLとR3 digital側SDA/SCLは同じnet。
  MCUがcontrollerの周辺I2CをSi5351A(0x60)・MCP23017(初期0x20)・拡張機器で共用する。
  外部操作側PicoがcontrollerのHOST I2C target(0x42)は別バスで、shieldへ出さない。
- 共有busでは0x20と0x60を予約する。shieldの5V pull-up・同一address・別controller駆動は適合確認なしに接続しない。
  Si5351/MCP23017を含む内部枝を外せるlinkを設け、A4/A5を純粋なADCとして使う場合は内部I2C動作を停止して枝を切り離す。
  通常演奏構成でA4/A5をADCとI2Cに同時使用することはできない。
  内部枝を切り離すADC利用は音源停止中の実験用途とし、その間はpanel操作・clock監視も停止する。通常演奏中の自由なADC枠はA0..3。
- A0..5は3.3V範囲のADCを目標にする。AREFはNC、外部基準電圧入力を提供しない。VINもNCで7..12V入力にはしない。
- POWERの3V3は予算内の出力、5Vは給電許可jumperを初期OPEN。外部からの逆給電を許容する意味ではない。
  ICSP/SPIのVCCは3.3Vと表示し、AVR書込み端子にはしない。RESETは3.3V RUN、5Vを駆動しない。

主信号の本数は20だが、I2C別名やSPI別名は追加GPIOを消費しない。
配線図・mechanical footprint・header向きはreview Aで照合。UNO領域外へPGA2350を置くが、
各shieldの張出し・裏面高さと購入ソケットの実物干渉は未確認。

## 2. GPIO不足を解消する操作表示エキスパンダ

全追加機能をGPIO直結すると、旧P2の30本＋Arduino追加18本＋DIP4本＋STOP/TEST2本＋声LED6本=60本。
48本（GP47をPSRAM用に予約すれば47本）に収まらない。
そこで**MCP23017を1個だけ追加し、低速操作・表示13bitをまとめる**。
YM bus、FM receiver、I2S、Arduinoの20signalはMCU直結のままにする。

| エキスパンダbit | 用途 |
| --- | --- |
| GPA0..3 | DIP SW1..4、ONでGND、pull-up付きinput |
| GPA4/GPA5 | STOP／TESTボタン、active LOW |
| GPA6 | 予備input（必要ならbuffer後のYM IRQ） |
| GPA7 | RX LED、active LOW sink |
| GPB0..5 | FM1/FM2/FM3/SSGA/SSGB/SSGC LED、active LOW sink |
| GPB6/GPB7 | 予備。GPB7はoutput用のみ |

MCP23017-E/SO（SOIC28、1.27mm pitch）を手実装候補にする。
**現行datasheetではGPA7/GPB7はoutput only**なので、DIP／ボタンに使わない。
3.3V、100kHz周辺I2Cを初期値とし、INT線は使わず10ms周期poll。LED更新は20ms周期にまとめる。
LEDは各3.3V→1kΩ候補→LED→port、1灯2mA以下を目標とし、port／package電流も確認する。
OLATを消灯値HIGHにしてからoutput方向へ変更し、起動時の点灯を防ぐ。

pollは短く有界、I2C transaction timeout目標2ms。YM演奏と音声DMAを優先し、
長いshield転送やログ出力で再生締切を妨げない。エキスパンダ／周辺bus不応答時は検出して消音する。
MCU内部watchdogまで停止した場合の独立強制消音は引き続き初期要件に含めない。

GPIO再計算：旧30本からRX LED直結1本を外して29本。
Arduino20本のうちSDA/SCL2本は既存周辺I2Cと共用なので追加18本、**計47本**。
GP47予約後の47本を使い切る。別GPIOのIRQや5V ADC観測はこの構成へ無条件には追加しない。
これは本数の検査であり、SPI/UART/PWM/ADC/PIO windowを満たす実pin muxの合格ではない。
pin muxはreview Aで成立。UART0、SPI1、6つの異なるPWM channel、A0..3専用ADCを確保し、
HOSTはI2C0 GP20/21、基板・拡張はI2C1 GP42/43へ分離した。実時間の同時動作は移植後に検証する。

## 3. クロック選択DIP

4極DIP、SW1をLSB、ON=GNDをsoftwareで1へ正規化し、表はSW4..SW1で表示する。
全OFF=0000で4MHz。**電源投入またはhard/watchdog reset時だけ取り込み**、途中操作では変更しない。
CDC statusにはrequested DIP／active profile／公称Hz／変更保留を表示する。
設定未対応・reserved・I2C不応答では無音でerrorとし、黙って4MHzへfallbackしない。
DIP取込み後もclock設定・音声prime完了を確認し、明示PLAY/Note On/TESTまでは無音。

| SW4..1 | 公称Hz | 用途例と境界 |
| --- | ---: | --- |
| 0000 | 4,000,000 | Rev C既存WYM1互換。MAME上海モデルも16MHz/4 |
| 0001 | 3,579,545 | Black Tigerのclock例。元基板はYM2203×2 |
| 0010 | 3,993,600 | 評価用。特定音源ボードとの対応は確定前 |
| 0011 | 3,000,000 | Combat Schoolのclock例。元基板にはuPD7759もある |
| 0100 | 2,000,000 | MZ-2500音源のclock例。別beepもある |
| 0101 | 1,500,000 | Ghosts'n Goblinsのclock例。元基板はYM2203×2 |
| 0110 | 2,500,000 | 評価用 |
| 0111 | 3,500,000 | 評価用 |
| 1000..1111 | — | 予約・無音 |

ゲーム例はMAME製作者のdriver内clock設定を出典にした選択候補で、P2実測値ではない。
**周波数を合わせても、複数YMや別音源を含む元基板全体を再現できるという意味ではない。**
4MHz以外は可変SRC・音程計算・各buffer/timeoutの実装と検証が必要で、現C版が既に対応しているとはしない。
MIDI/TESTはactive clockから周波数値を計算し、TESTは小音量の短い独自パターンとする。

既存HOST I2C v2は4MHzのまま。DIP非4MHzで4MHz BEGINはDATA拒否し、HOST libraryを書き換えない。
非4MHzのWYM1は新USB経路の能力通知とfile clock検査を通すことを初期拡張先にする。
DIPとfile headerのclockが一致しなければ再生せず、勝手なclock変更やtimestampの引伸ばしをしない。

既存Si5351生成器で25MHz水晶・8公称周波数の生成／逆算を再確認した。
生成器はF1用にCLK1=49.152MHzも設定するため、出力ROMをP2 firmwareへそのまま組み込まない。
P2では未使用CLK1/2をdisableし、SRCはPIO用の実装へ移植する。
算術一致は水晶偏差・波形・音質・P2実動を保証しない。

## 4. ハードリセット、STOP、TEST

| ボタン | 動作 |
| --- | --- |
| HARD RESET | PGA2350 RUNを直接GNDへ落とす。firmwareやエキスパンダを経由しない。USB再列挙と全演奏破棄、DIP再取込み |
| STOP | エキスパンダ経由のsoftware global STOP。I2C/USB/MIDI/TESTすべてを止め、FIFO・所有権・LEDをclear |
| TEST | 無所有・停止中だけ、独自FM3単独音、SSG3単独音、6声和音の短い診断を1回再生して無音終了 |

3個の独立ボタンとする。STOPとTESTが同時ならSTOP優先、押し続けてもTESTを繰り返さない。
STOP/TESTは10ms poll＋20ms debounceを目標にし、厳密な応答上限やMCU停止時の動作保証にはしない。
エキスパンダRESETも3.3V RUN nodeへ接続する案とし、manual resetでLEDを消す。
watchdog resetが外部RUNへ伝わるとは仮定せず、boot初期化でも必ずエキスパンダ状態を消去する。

RUN中はYM reset・OE無効・DAC/LINE muteとなるdefault回路を保持する。
5VのYM RESETをRUNへ直接結線しない。GPIOがHi-Zになった際のreset/muteを別の電圧適合回路で成立させる。
RESET、STOP、TESTの解除後に前曲・前MIDIノートを自動復活させない。

## 5. 6声の発音状態表示

FM1/FM2/FM3、SSGA/SSGB/SSGCのLED6個を追加し、RX LEDとは区別する。
各声の**実行済みレジスタ状態＋出力許可**を表示し、キューへ入っただけでは点灯しない。

- FM：0x28のchannelごとに4operatorのkey bitを保持し、いずれかONかつDAC/LINE許可なら点灯。
- SSG：0x07でtoneまたはnoiseが有効、0x08..0x0Aで固定音量が非zeroまたはenvelope選択、かつLINE許可なら点灯。
- MIDIもWYM1も同じbus適用経路でshadowを更新する。noise発音や途中のkey-offも反映する。
- 短い発音を見やすくする30ms最短点灯を目標にするが、STOP/reset/fault/muteの消灯を優先する。
- LED更新は20ms周期にまとめ、各レジスタ書込みごとにI2Cへ転送しない。

音圧／VUメーターではない。FM releaseの残響、TLで消えた音、SSG envelopeが一時的にzeroの音量までは
この表示だけでは測定できない。DAC muteではFM側、LINE muteでは全声を消灯させる。

## 6. USB経由のWYM1再生

同じUSB-CのCDCを使い、PC用送信ツールからWYM1をstreamingする。外部操作側Picoは不要。
USB-MIDI deviceは同時に列挙するが、演奏所有者はNONE/I2C/USB-WYM1/MIDI/TESTの一つにする。
外部HOST I2C v2は変更しない。WebLab側の変更や統合は本作業に含めず、将来共通APIのUSB backendとする。

- PCはfile header・件数・CRCを検査して、明示操作でBEGIN/補充/PLAY/SEAL相当を送る。
- whole fileをRAMへ置かず、1024 event FIFOと空き枠通知でbackpressureをかける。
  受信時刻ではなくWYM1 timestampを基準にし、値・順序・時刻・最終CRCを保持する。
- version、有限長、sequence、CRC、ACK、同一要求再送の非二重実行を持つ転送frameを定義する。
  stream modeは明示的に出入りし、binary中にCDC console文字列やstatus自動印字を混ぜない。
  具体的byte配置・PC APIは実装前に別仕様として確定する。I2C v2への未定義opcode追加では実現しない。
- USB owner中も物理STOPは受理し、USB切断/reset/suspend、CDC stream終了、補充lease 1000ms失効で全音停止。
  単なるstatus readをlease更新にしない。再接続・再送で曲を自動再開しない。
- I2C owner中はUSB切断でもI2C演奏を維持。USB/MIDI側の開始要求は拒否し、あとで再生しない。
  global STOPだけは所有者に関係なく優先する。
- non-4MHz転送は、DIP clockとfile clockの一致・可変SRC対応の能力通知を必須にし、非対応なら拒否する。
  最初の移植確認はDIP=0000、既存4MHzのWYM1を使う。

## 追加部品と次の検証

追加の主部品はMCP23017×1、4極DIP×1、STOP/TESTボタン×2、声LED×6＋抵抗×6、
UNO R3ヘッダー4列、ICSP/SPI 2x3、分離link／電源jumper、必要decoupling。
HARD RESETとRX LEDはP2に予定済みだった部品を具体化し、二重計上しない。
MCP23017を追加してもRev CのHC5個を削除する方針は維持するが、総点数純減は新BOM後に確定する。

pin mux・実寸header配置・回路図・GPIO表は[review A](carrier-p2/README.md)へ具体化した。
次は部品実物と電源容量・USB配線条件の確認、配線済みPCBとP2専用C版移植を進める。
その後、ボタン／DIP／レジスタshadow／LED／USB streamを実装し、旧HOST無変更で回帰する。
試験には全16 DIP code、演奏中のDIP変更、reset時無音、STOP優先、I2C bus不応答、
全6声・mute、USB再送／CRC／queue不足／切断／所有権、4MHz既存全曲と非4MHz拒否を含める。
GPIO 47本の算術・資料検査をもって、配線・音質・USBやMIDIの実機合格とはしない。

## 一次資料

- [Arduino UNO R3 pinout](https://docs.arduino.cc/resources/pinouts/A000066-full-pinout.pdf)：signal名・aliasとheader構成。図やCADは本変更で複製しない。
- [MCP23017 datasheet DS20001952D](https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP23017-Data-Sheet-DS20001952.pdf)：3.3V動作候補、GPA7/GPB7のinput制約、reset／方向／電流。
- [PGA2350](https://shop.pimoroni.com/en-us/products/pga2350)：48 GPIO／GP47 PSRAM CS。
- MAME製作者driver：[Shanghai](https://github.com/mamedev/mame/blob/master/src/mame/sunelectronics/shanghai.cpp)、
  [Black Tiger](https://github.com/mamedev/mame/blob/master/src/mame/capcom/blktiger.cpp)、
  [Combat School](https://github.com/mamedev/mame/blob/master/src/mame/konami/combatsc.cpp)、
  [MZ-2500](https://github.com/mamedev/mame/blob/master/src/mame/sharp/mz2500.cpp)、
  [Ghosts'n Goblins](https://github.com/mamedev/mame/blob/master/src/mame/capcom/gng.cpp)。

独自仕様・比較表はMIT。外部コード・楽曲・図面・USB識別子を新規導入していない。

## P2 revision 2.1 / PCBレビューB

[レビューB](carrier-p2/pcb-review-b/README.md)に電源容量・ソケット高さの検討と、
164部品の回路図・配線済み4層PCB候補を追加した。DACとUNO 3V3供給を500mA AUX LDOへ分離し、
PGA2350内蔵300mA電源の設計予算を259.4mAとした。一般2列ソケット4個は端部が干渉するため、
64本の単端子ソケットを候補にし、実物の挿入・保持・高さ確認を残す。
47 GPIO、UNO接点座標、既存HOSTは変更しない。回路・DRCの結果はBの検査記録を参照。
P2専用ファームウェア、実組立、電流・温度・USBインピーダンスの確認、製造リリースは未完。
レビューAの回路図と検査記録は履歴として保存する。
