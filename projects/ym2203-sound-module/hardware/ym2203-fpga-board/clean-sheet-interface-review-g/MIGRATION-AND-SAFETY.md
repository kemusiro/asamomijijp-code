# review G：互換境界と新規設計への移行

## 撤廃する制約と維持する契約

旧カード/旧base/旧GPIO配分を維持する制約は、今回のユーザー指示により撤廃した。
40接点の位置、KEY、bus名、UNO内部GPIO、音声GPIO、MOD_ENABLE/ALERTを新設計へ再配分する。
旧C/Dのファイル自体を上書きせず、Fも検討経緯として保存する。
新connectorは旧32/40pinや他製品の40pin headerとの互換が無く、部分挿し/変換なし接続を禁止する。
source側の5V IC/MCU/ADC回路も新設計対象で、旧カードから必要な固有回路だけを再利用する。

維持するのは外部動作の契約。opn1・4MHzのYM22S002、WYM1 event6byte、status64byte、
PUSH32、FIFO1024、1000ms lease、sequence/CRC/実chip書込み完了でexecutedを進める意味を変えない。
HOSTはGP20/21のI2C0=0x42/100kHzのまま。source connector23/24は内部I2C1であり、別bus。
既存HOST playerを基板内部GPIOの違いへ依存させない。既存HOSTでのP2実機合格はまだ無い。

USB-MIDI中BEGIN拒否、I2C中MIDI破棄、USB-MIDI切断停止、外部給電下I2C中USB切断継続、
status/再接続だけでは再演奏しない契約を保持。直接PSGがYM WYM1を解釈できるとはしない。
UNO外形/IOREF3.3V/ADC6/PWM6/SPI1/UART0/A4/A5 I2Cを保持し、MCU pin番号は移す。

## モード切替・PIO停止

切替は停止・所有者なし・最終gate閉でだけ行う。MOD_ENABLE L、世代更新、event/PCM破棄、
SM/DMA/SPIを停止し、共用data/controlをHi-Zとしてからprofileのinactive SIO値を準備する。
pin functionをSPI/PIOへ移す際、PIOのstale latchを露出させない。新PLAY/Note Onまで最終gateを開かない。

STOPはbus/READY/PIO FIFO待ちの前にGPIO38/39の最終許可を落とす。
その後にSM/DMAを停止し、SIOへinactive値で引継ぎ、dataをHi-Z化する。
SMをdisableしただけではactive strobeの出力値が残り得るため、それだけを停止完了としない。
未完了eventを取消し、以後read-only再接続/USB列挙で発音を復元しない。
カードにRESETが無い場合も、base最終gateを閉じたまま期限付き消音初期化を行う。

PIO候補ではPULL/FIFO stallはstrobe非活性時のみ。AY active pulseをhost/DMA補給待ちで伸ばさない。
SN READY待ちはclock依存の最低待ちと期限付きpollを使い、無期限WAITで停止しない。
sample/data/controlの方向はprofileで設定し、write-only PSGにはread用回路を必須化しない。

すべてのdigital connector pinは3.3V。必要な5V変換はcard側に残す。
アナログ負荷/mix/AC結合・電源decoupling・初期pull抵抗と最終gateは残すが、
独立watchdog/電源監視/冗長停止ラッチ/電源絶縁は追加必須にしない。CPU hangの独立検出保証は無い。

## driver実装時の手順

1. GPIO/connectorをGの新規設計表から回路/PCBへ反映。旧pinmap headerを流用しない。
2. opn1 sourceのSPI/clock/任意I2S/SSG Lを新pinへ接続。sourceローカルGPIOは別途決定する。
3. PIO0 parallel engineとPIO1 audioを実装し、instruction memory/DMA/USBとの競合を検証。
4. 無音起動、全音停止、clock/READY欠落、MODE拒否、旧sample FIFO排出を確認。
5. Rev C診断/全曲/STOP・lease・再開とUSB所有権の受入をP2新基板で改めて行う。

現段階は配置条件/contractの検討。新しいPIO binary、UF2、回路図、製造データは作成していない。
