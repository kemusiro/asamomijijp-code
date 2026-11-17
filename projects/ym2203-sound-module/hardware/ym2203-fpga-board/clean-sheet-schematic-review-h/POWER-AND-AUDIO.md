# Hの電源・音声入力・出力

2026-11-18。これは回路値と条件付き計算のレビュー。電流・温度・波形の実測結果ではない。
一次資料は[sources.json](sources.json)、再計算値は[verification.json](verification.json)に記録する。

## 電源容量

[power-plan.json](power-plan.json)の設計予算は以下。IC消費電流の保証最大値を表すものではない。

| 系統 | 予算 / 限度 | 供給先 |
| --- | --- | --- |
| PGA内蔵3.3V | 265 / 300mA | MCU175、Si5351A40、panel/LED15、ADC IO15、DAC digital15、logic5 |
| AUX 3.3V | 350 / 設計500mA | ADC analog/PLL50、DAC analog/CP50、UNO150、任意card AUX100 |
| 音源5V | 最大500mA | 今回の例Core250＋YM/変換100＝350mA |
| UNO 5V | 最大100mA | JP5Vは通常開放。外部電源付きshield禁止 |
| 5Vその他余裕 | 25mA | 静的予算余裕 |

拡張上限を同時に使う入力予算は1.240A。外部5.1V/2A安定化電源を候補とし、YM端子で4.75～5.25Vを確認する。
ケーブル・PTC・コネクタ・銅箔での電圧降下と突入はPCB/実機確認が必要。
F1はMF-MSMF200/16X-2候補、40℃時の保持電流表1.75Aと比較した。
これは短絡が起きれば即座に電流を遮断する保証ではない。

AUXはTLV1117LV33DCYR/SOT-223。IN3、OUT2＋TAB2、GND1、入出力10µFセラミック。
Vin5.25/Vout3.2Vの計算用境界・350mAでは0.718W。
JEDEC参照RθJA=62.9℃/Wを当てた接合温度は周囲40℃で約85℃だが、実基板の保証値ではない。
放熱タブの銅箔、実効容量、負荷試験で確認する。SOT-23の小さなLDOへ無条件に置換しない。

PGAのV3V3、AUX、CoreのMCU_3V3は互いに直結しない。
ADC AVDDとDAC AVDD/CPVDDはAUXのferrite後、ADC DVDDはAUX、ADC IOVDDとDAC DVDDはPGA電源。
デジタル端子を受信側電源にそろえ、STOPでADC電源を切り替える回路を省いた。
USB VBUSは既存の絶縁された検出用。base5VやCore VBUSへ給電しない。
モジュール・shieldを別電源で先行給電せず、共通5Vから起動する。hotplug不可。

## 共通ADC入力

各L/Rは以下の順。ADCのVINL1=3/VINR1=4、AD=0で0x4A、BCK PLLのslave、SCKI/XIはGND。

`analog → 6.81k → 分圧点（10kでGND）→ 10µF AC → 2.2k → ADC入力`

ADC入力には470pFとBAT54Sの上下rail clamp。BAT54Sの1=GND、2=AV3V3、3=ADC入力。
入力のDC biasはADC側へ任せ、VREFへ外部音声を注入しない。
PCM1863のanalog入力絶対範囲−1.7～5Vを、正常使用時の推奨入力振幅と混同しない。
20kΩは入力抵抗のtyp値で、保証最小値ではない。

1%抵抗の無負荷最大分圧比は約0.600。5.25Vの全入力ステップ＋保持bias1.8Vを
そのまま最小直列抵抗2.178kへ加える保守的な計算では約3.24mA。
TIの設計上の入力clamp電流指針5mAより小さくする。任意電圧の誤接続・surge・hotplugを保証する保護ではない。
入力はラインレベル1Vrms目安/2Vrms設計上限。生SSGのDC分はACで除く。

YMカードは各SSGに1.33k負荷と10k mix抵抗。3出力を並列に見た保守的出力抵抗上限は約3.82kΩ。
これを受けるためHはsource impedance目標4.7kΩ以下へ変更した。
source約3.78k、ADC入力20k typを仮定した受動RCの1kHz利得は約0.355。
20kHzの相対変化は約−0.42dB。ADC/ICの実特性・SSG出力の非線形やgain/filterは含まない。
その分SSGのdigital gainとFM/ADCの遅延を校正する。Rev Cの「FM100%」を無測定で同一係数にしない。
初期はADC PGA0dB、AGC無効、L1/R1選択、mono Lを左右へ複製、二重加算を避ける。

実効AC容量4.7～15µF、ADC入力抵抗10～40kΩを**検証用仮定**とすると5τ最大約3.57秒。
電源投入時は最終muteのまま少なくとも4秒の安定待ちを設ける候補。
この入力抵抗範囲はメーカー保証値ではなく、実機のDC・立上りで確認する。
通常STOP/BEGINでADC電源は維持し、毎回4秒待つ仕様にはしない。

## 最終DAC・停止

PCM5102Aのground-centred出力を470Ω/2.2nF LPF、外付け左右10k log volume、100Ωを介してlineへ出す。
外付けopampや2.5V bias、4053、出力AC結合を省く。負荷10kΩ以上のアンプを基本とし、headphone直結は想定しない。

XSMTはSN74LVC1G08でDAC許可AND LINE許可。各GPIOとXSMTは10k pull-down。
全ADC/I2S音声は同じ最終DACを通り、analog bypassは設けない。
FM-only muteはsoftware mixのFM枝だけを0にし、最終XSMTと区別する。

データシートの150sample＋0.2msから48kHzで3.325ms。
計画的なmodule reset/clock停止はmute要求後**4ms以上**あける候補。STOP中も通常はaudio clockを継続する。
STOP ACKはqueue無効化とmute開始を示し、瞬時のanalog切断を示さない。
電源急断・brownoutやMCU hang時の無音、無popは未保証。試作範囲として独立watchdogは付けない。
最終的な消音時間、DC、起動/STOP/USB切断のpop、clock周波数ごとのFM/SSGバランスは実機で確認する。
