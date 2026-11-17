# PCB review I：電源・音声・USB配線

2026-11-18。Hの[電源・音声設計](../clean-sheet-schematic-review-h/POWER-AND-AUDIO.md)を変更せず配線した。
接続一致とDRCは確認済み。IR drop、熱、音質、USB信号品質は実測前。

## 層と電源

4層。In1.Cuは連続GNDの参照面で、signal配線は0本。
signalはF.Cu/In2.Cu/B.Cu。5VのIn2補助面、各MCU 3.3VのB面、AUX regulatorの表面放熱銅箔を設けた。
GNDにアナログ用の分断スリットは入れない。全GND接点の接続もnative未配線検査で確認する。

5V配線の最小幅は0.35mm、一般signal0.18mm、EXT_A5の局所0.17mm、宣言した最小は0.15mm。
viaは0.60/0.30mmまたは0.45/0.20mmが基本。パッド内の例外は[組立](ASSEMBLY.md)に明示する。
面による補強があるため、分岐を含む配線長の合計をそのまま一本の給電抵抗へ換算しない。

Hの予算はPGA3.3V265mA/300mA、AUX350mA/設計500mA、全拡張込み入力1.240A。
給電sourceは外部安定化5.1V/2A候補。USB VBUSは検出だけで5V電源に直結しない。
PGA/Core/AUXの3.3V出力も直結しない。AUXのSOT-223 OUT/TABを放熱銅箔へ接続したが、
HのJEDEC参照熱抵抗による約85℃の計算値を、このPCBの実温度の保証へ流用しない。
基板・PTC・コネクタ・ケーブルの負荷降下、突入、温度を測り、YM端子4.75～5.25Vを確認する。

## 音声

ベースのanalog L/Rから最初の抵抗までを表面の短い配線にし、GPIO/clock領域と共通ADC周辺を分けた。
Hの6.81k/10k、10µF AC、2.2k、470pF、BAT54Sの接続を維持する。
native配線合計：AUDIO_L約8.48mm、AUDIO_R約9.09mm（base入力）、ADC_L約21.28mm、ADC_R約29.92mm。
これらは分岐を含む合計。ADC pinでのノイズや過渡、FMとSSGの音量・遅延校正は未実施。

sourceのY_SD約16.17mm、Y_SH約17.92mm、Y_CLK約59.90mm、Y_PHI_M約28.85mm。
返送I2S・共有clockもHと同じ接続。長さの記録はタイミング/波形の合格を意味しない。
Si5351A周波数ごとのedge、Core受信の余裕、I2Sの立上りとdata setupを初回波形で確認する。
全netの長さ・層・viaは[routing-review.json](routing-review.json)。

## USBと停止

USB D+/D−のnative配線合計は約32.76/30.53mm。D+はvia2個、D−はvia0個。
12Mbps full-speed用の短い配線候補で、90Ωインピーダンス計算・TDR・eye測定は未実施。
PGAモジュール上の経路とコネクタ分岐も含め、実物でCDC/MIDI列挙・連続通信を検証する。
DRC0をUSB PHY合格とは記載しない。

HのDAC許可AND LINE許可→XSMT、MOD_ENABLE→source RUN、source TX禁止→MISO/I2S無効、
default pullの接続をそのまま保持した。停止前の4ms guard、lease、所有権、切断/再接続時の扱いは
[Hの制御条件](../clean-sheet-schematic-review-h/CONTROL-AND-STOP.md)を継承する。
これらのP2 firmwareと実機回帰は未実装・未確認。独立watchdogや追加の冗長ゲートを増設した変更ではない。
