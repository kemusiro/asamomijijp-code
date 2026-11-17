# P2 review G：新規設計の40接点と連続GPIO

2026-11-17 / revision3.4-interface-review-g / interface5.0-draft。
旧音源基板・旧ベース・旧GPIOとの互換を要求せず、両基板を新規設計する。
GPIO/コネクタの設計変更は今回のユーザー指示の範囲。**回路/PCB/firmwareは未反映、実機未検証**。
旧C/D/E/Fの採用表・検証記録やRev C firmwareは書き換えない。

## Fから改善する点

| 項目 | F：旧配列を維持した40接点 | G：新規設計 |
| --- | --- | --- |
| parallel data | GP0～3＋GP30～33、SIO2bank | **GP0～7連続**、PIO OUT8/IN8の配置条件を満たす |
| parallel control | GP6/7/17/18 | **GP8～11連続**、PIO SET4で扱える |
| module許可/通知 | GP34/4 | GP12/13、bus12本の隣で独立制御 |
| I2S＋ADC | GP26/27/28＋5/16 | GP14～18、TX＋2RXを同じPIO windowへ集約 |
| connector analog | L/Rと内部I2Cが隣接 | **末端37/39をL/R、38/40をGND、35/36をGND guard** |
| dataの物理配置 | 低4bitと高4bitが遠い | low/high各4bitの間にGND2接点を置いてまとめる |
| 旧基板 | SPI時に一部pin維持 | **互換なし**、誤接続を許可しない |

SIOの2bank更新とCPU割込みでpulseが延びるFの制約を避け、PIOによる定時間pulseを実装しやすくする。
ただしPIOプログラム/DMA/timeoutは未実装で、配置条件が成立することと実時間動作の合格は分ける。
元から単純だったSPI/I2Cカードに、余分なMCU・ADC・FPGAを追加しない。

## コネクタ

[全接点CSV](connector.csv)、[JSON](connector.json)、[配置図SVG](pinout.svg)を正本の補助資料とする。
2×20/2.54mm、接点列48.26mm。base嵌合面A=奇数/B=偶数、sourceの裏面視は鏡像。
SSW-120-02-G-D / TSW-120-07-G-Dを候補とし、**KEYは6へ移す**（穴塞ぎ/抜きピン加工が必要）。
旧32/40接点カードを挿さない。Pi/IDE等の同じ40pin connectorとも互換はない。

| 領域 | pin | 内容 |
| --- | --- | --- |
| 電源 | 1～6 | 5V×2、GND×2、任意補助3.3V、KEY |
| 許可・通知 | 7/8 | MOD_ENABLE / MOD_ALERT_N |
| bus下位 | 9～12 | D0～3、SPI時MISO/CS0/SCK/MOSI |
| bus用GND | 13/14 | common GND |
| bus上位 | 15～18 | D4～7 |
| bus制御 | 19～22 | CTL0～3、generic A0/CS/WR/RD |
| 内部I2C | 23/24 | service SDA/SCL。HOSTの別busと短絡しない |
| 音源clock | 25～30 | CLK0/GND、CLK1/GND、CLK2/GND |
| 任意I2S | 31～34 | BCK/GND、LRCK/DATA |
| 音声guard | 35/36 | common GND |
| アナログ音声 | 37～40 | L/GND、R/GND |

全GNDは同じground planeへつなぐ。ADC用とdigital用に別電源/別GNDを作る意味ではない。
analog入口とADCを端部へ寄せ、clock/SPIがanalog配線を横切らない部品配置にする。
12 GNDと信号の近接を整えた構成案で、ノイズ低下を測定済みという意味ではない。

## ベースGPIO全体

[GPIO JSON](gpio-proposal.json)、[CSV](gpio.csv)、[旧候補との差分](gpio-delta.csv)に44本を列挙。

| 用途 | GPIO |
| --- | --- |
| data D0～7 / SPI0共用 | **0～7**（SPI0は0～3） |
| CTL0～3 | **8～11**（SPI時CS2=8/CS1=9） |
| ENABLE / ALERT | 12 / 13 |
| DAC data / BCK / LRCK | **14 / 15 / 16** |
| ADC data / 任意module I2S data | **17 / 18** |
| HOST I2C0 | 20 / 21 |
| UNO UART0 TX/RX | 28 / 29 |
| UNO SPI1 MISO/CS/SCK/MOSI | 24 / 25 / 26 / 27 |
| UNO A0/A1/A2/A3/A4/A5 | 40 / 41 / 44 / 45 / 42 / 43 |
| 内部I2C1（UNO A4/A5共用） | 42 / 43 |
| 最終DAC/LINE許可 | 38 / 39 |
| USB VBUS検出 | 46 |
| 予備 / PSRAM予約 | 35～37 / 47 |

UNO D2/D3/D4/D5/D6/D7/D8/D9=GP19/22/23/30/31/32/33/34。
A4/A5は内部I2C1と共用するため、analog入力との同時利用はしない。service jumperを開いてanalogに使う間は、clock/ADC制御を必要とする再生を禁止する。
UNO外形・信号の役割・3.3V IOREFを保持し、内部GPIOだけを再配分する。
D3/D5/D6/D9/D10/D11のPWM6出力は異なるchannelで、D5/D6は同じsliceの周波数を共有する。
USB DP/DM、RUN/BOOTSEL/SWDはPGA固定端子を使用。clock DIP/STOP/TEST/RX/6声LEDは内部panel経由を維持。
47本中44本を割当て、GP35/36/37を空け、GP47のonboard PSRAM配線を切らない。

## PIOとモード

PIO0 GPIO_BASE=0へdata0～7、SET8～11を割当てる。**OUT8とSET4を分け、OUT12でENABLE12へ書き込まない**。
SN READY inputに使うCTL3=GP11は、そのprofileでpindirsをinputにする。
FIFO不足はstrobe inactiveで待ち、AY write最大pulse内へblocking PULLを入れない。
SN READYは無期限WAITではなく期限付きにする。STOPでSM/DMAを止めてSIOのinactive値へ取り戻す。
PIO1 GPIO_BASE=0へI2S TX(14～16)＋ADC RX17＋module RX18を置く。候補3SM、parallel1SM、PIO2は予備。
SM数とwindowのみ静的検査し、instruction memory配置・DMA負荷・実pulse測定は今後の実装で確認する。

SPI/parallelは排他、I2Cは内部ADC/Si5351/panelのため並行して使用可能。
切替は停止・所有者なし・最終mute閉でだけ行い、data/controlをHi-Zへ戻してから初期化する。
GPIOの再配置を許可しても、発音中の誤モード切替や5V信号の直結を許す意味ではない。

## 音声・部品点数・互換性

アナログL/R＋base共通PCM1863、任意48kHz I2S、mono L→左右複製、共通DAC/最終muteは継続。
native parallel PSGではSPI変換latch/bridge MCUを省き、必要な5V bufferとanalog負荷/mixを残す。
opn1のFM decode用Coreは残す。MCUが必要なカードでもconnector番号と個々のローカルGPIOを混同しない。
補助3.3V100mA/5V500mAは設計枠候補で、電源計算は新回路で再実施する。
電源OFF交換、共通電源/GND、手動profileとし、独立watchdog/絶縁/冗長停止を必須にしない。

旧基板との物理互換は撤廃するが、**既存HOST playerのopn1・4MHz通信互換は維持**する。
USB-MIDI/I2Cの所有権、STOP/lease、USB切断中I2C続行、再接続だけでは発音しない契約も維持。
新PSG用driver/曲形式/MIDI mappingは未実装。詳細は[移行・停止契約](MIGRATION-AND-SAFETY.md)。

## 検査

```sh
python3 export_pinout.py --check
python3 verify.py
python3 -m unittest -v test_contract.py
```

GPIOの一意性、vendor pad identity、固定SDK mux表、UNO機能、PIO連続範囲/SM数、analog GND隣接、
全256byte mapping、禁止設定とHOST wire定数をPC上で確認する。[verification.json](verification.json)を参照。
CSV/SVGはJSONからexport_pinout.pyで生成して管理する。直接編集しない。
新回路/ERC/PCB/DRC、firmware/PIO assembly、電源/嵌合/音声/実時間timingは未実施。
プロジェクトMITを継承。一次資料は[sources.json](sources.json)。
