# MCU・コネクタ・電源・端子の検討

## ベース

RP2350BからRP2350Aへの変更はGPIO数とパッケージの変更であり、RP2040へ音声処理を移す案ではない。HOST、USB CDC/MIDI、PCM合成、I2S、FIFO、STOP/leaseの責務をベースに残す。現在のP2 HALは未完成なので、既存Rev C UF2の流用可否をGPIO表だけで判断しない。PIO命令領域・DMA・割込み負荷は実装時に確認する。

| 信号 | Picossci 2Aの提案GPIO | 保存する境界 |
| --- | --- | --- |
| G40 D0..7 / CTL0..3 | 0..7 / 8..11 | 連続並列バス、SPI profileと選択利用 |
| MOD_ENABLE / ALERT_N | 12 / 13 | 既定disable・音源RUN停止経路 |
| DAC DATA / BCK / LRCK / ADC RX / MOD RX | 14 / 15 / 16 / 17 / 18 | 従来PIO向け隣接関係 |
| DAC_ALLOW / LINE_ALLOW | 19 / 22 | LOW消音、I2Cの完了を待たない |
| HOST SDA/SCL | 20 / 21 | I2C0 slave0x42 /100kHz |
| ベースSTOP_N | 23 | GPIO直結＋外部pull-up。旧MCP23017 GPA4から移す提案 |
| service SDA/SCL | 26 / 27 | I2C1 master、パネル0x30＋既存周辺 |
| USB VBUS sense | 28 | 外部USB-CのRAW VBUSを分圧、5V直結不可 |
| 予備 | 24 / 29 | GP25は基板LEDに予約 |

メーカー回路図を表示して、GP0..29の端子、RESET=J1.18、3V3=J1.1/J2.20、GND=J1.19/J2.2、入力VBUS=J2.19を照合した。GP25はR5/LEDを残す。2AはRUNが端面へ出ているので、LC-Aの2B用RESET追加線をベース側まで要求しない。音源の2Bは従来どおりRESET線とGP24/25 LED負荷の処置が必要。

商品ページの32Mbitと公開図のW25Q16表記に差があり、flash JEDEC・搭載シリコン版を現物で確認してからboard設定を固定する。Picossciの入力VBUSはレギュレータ入力の名称であり、PCのRAW VBUS検出と結線を混同しない。外部5Vから給電し、USB-CはD+/D-とRAW VBUS分圧検出を維持。二つのモジュールとAUXの3.3V出力を並列接続しない。

比較のPico 2は同じ信号のうちSTOPをGP28、VBUS検出を基板内GP24にする。GP23はSMPS制御なのでSTOPに使わない。外部26本に予備なし、micro-Bを使う場合はUSB-C入力を残したまま同時接続しない。USBからMCUだけ給電され外部回路へ逆給電する状態を避けるため、VBUS→VSYSのD1を含む給電の見直しが必要で、200円の仮枠を費用に入れた。方式・USBコネクタ削減額は未確定。base2B維持案はGP24/25のLEDを残して46 GPIO中27本使用、19本予備。

## パネル

Pico RP2040は26外部GPIO、ADC入力はGP26/27/28の3本。GP29は基板内VSYS分圧であり4つめのつまみへ直結しない。4つともCD74HC4051EのCH0..3へ入れ、共通端子をGP26へ接続する。VCC=PANEL_3V3、VEE/GND/INH/C=GND、A/B=GP18/19。未使用CH4..7はGNDへ。10kノブと既存RCを保ち、選択後250µs待ち、初回変換を捨てる初期値で100Hz/ノブを目標にする。最終のsettling・pickup精度は実測する。4入力を1入力に多重化するための1 ICで、音声経路へは挿入しない。

パネル端子はgpio-proposal.json。I2C0 GP0/1=ベース向けslave、I2C1 GP2/3=24FC256向けmaster。LCDはSPI0 GP6/7、CS5/DC4/RST8。操作子9..17、MUX18/19、ADC26で21本、予備20/21/22/27/28の5本。baseとpanelのGPIO番号が同じでも別MCUのため衝突ではない。

LCD画素はローカルSPIで転送する。I2C経由で全画面を毎フレーム送らず、baseはpatch値、parameter focus、所有者/再生状態を送る。SAVE/LOADと64slotの24FC256・record CRC・JSON仕様を保存し、EEPROMはパネルのローカルバスへ移す。CDC経由のJSON取出しはbaseから小分けに中継し、base音声処理中にEEPROM完了待ちを行わない。

## 3.3V Grove

| ピン | 信号 | ケーブル色 |
| --- | --- | --- |
| 1 | SCL | 黄 |
| 2 | SDA | 白 |
| 3 | AUX_3V3 | 赤 |
| 4 | GND | 黒 |

110990037 L型THTをbase/panelに1個ずつ。袋10個150円＋150mmコード110円で購入260円、余り8個。5V Grove機器を混在させず、基板へ「I2C 3V3 ONLY」を表示。QwiicはGND/3V3/SDA/SCLで順序が違うため直結の置換ではない。比較用は116800 5個200円＋115884コード150円=350円、寸法と結線の最終確認後に採用する。両方を常設して部品数を増やす必要はない。

初期100kHz、base側一組だけ3.3V pull-up（4.7kΩ初期値）、パネルのuplink側追加pull-upはDNP。EEPROM側は独立したpull-upを残す。base既存service pull-upを含めた合成抵抗と150mm配線の立上がりを確認する。hot-plug保証は付けず、通常の挿抜は停止・電源断で行う。

## 電源・実装範囲

AUX_3V3→逆流防止Schottky→Pico VSYS（39番）で給電。3.3Vから降下してもPicoのbuck-boost入力1.8..5.5V内を狙える。Pico 3V3出力（36番）はPANEL_3V3専用とし、LCD・EEPROM・MUX・ノブへ給電。AUX_3V3へ出力を直結しない。パネルUSBは更新用で、使用時はGroveを外し、USB給電中のSDA/SCL経由の逆給電も避ける。通常はbaseのUSB CDCからJSONを中継する。

150mAはパネル入力での暫定予算であり実測値ではない。LCD BLとMCUを含み、輝度・描画頻度を制限して確認する。LC-AのAUX440/500mAを保守的に据え置き（旧パネル150mA枠の置換、加算ではない）、baseモジュール175mA・音源250mAの別レール予算も据え置く。必要ならAUXのLCD輝度制限を優先する。実部品電流、3.3V降下、LDO温度は未検証。新高機能電源監視やI2Cアイソレータは追加しない。

base100×100 4L/source100×80 2L/panel100×76 2L目標、0.3mm drill/0.6mm via pad、鉛フリーHASLを継承。ノブとLCDの外形を維持したまま、パネル背面へPico 51×21mmとDIP16の領域を確保する。ベースと重ねずケーブル接続し、裏面端子絶縁と支持高さを新配置で確認する。26.67×15.24mmのbaseモジュールは2Bの36.83×17.8mmから面積約38%減だが、キャリア外形も38%減る意味ではない。回路図・配置・DRC・干渉確認・発注は次の工程。

## 一次資料

- [Picossci 2製品・回路図入口](https://www.switch-science.com/products/9795)
- [Picoデータシート](https://datasheets.raspberrypi.com/pico/pico-datasheet.pdf)、[Pico 2データシート](https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf)
- [TI CD74HC4051・データシート入口](https://www.ti.com/product/CD74HC4051)（ACTIVE、HCの2..6V仕様。HCTの5V電源品で代用しない）
- [Seeed Grove pinout](https://wiki.seeedstudio.com/Grove_System/)

購入価格・販売単位・在庫観測とURLはpart-observations.json。第三者回路図/PDFの複製は配布しない。
