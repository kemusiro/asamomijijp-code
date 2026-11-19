# LC audio review D：YM3014B-F＋共通ADC・I2S入力の維持

2026-11-19。ユーザー決定を記録した構成方針。LC-BのMCU・承認済みGPIO・G40配列を維持し、YM2203基板は入手済みYM3014B-Fを採用する。ベースのPCM1863共通ADC、I2S入力、PCM5102A出力DACは削除しない。費用目標は送料・予備枠込み約30,000円へ戻す。基板3種類を各5枚、部品1セット、YM2203C流用、YM3014B-F追加購入0円、手実装の条件。

本資料は新しい音声経路の設計契約であり、review Cの回路図・BOM・ERC結果はその時点のまま保存する。YM3014B-F追加後の回路図/ERC、PCB/DRC、ファームウェア・実機受入は未完。Rev CのUF2をそのまま新基板へ使用できるという意味ではない。

## 採用する経路

```text
YM2203 FM → YM3014B-F → バッファ・レベル整合 → G40 AUDIO_L → ベースADC L ┐
YM2203 SSG → 3声の抵抗合成・レベル整合    → G40 AUDIO_R → ベースADC R ┴→ RP2350 → PCM5102A → L/R

将来の音源のデジタル出力 → 音源側MCUでPCM化・レート整合 → G40 I2S ───────→ RP2350
将来の音源のアナログ出力 → バッファ・レベル整合 → G40 AUDIO_L/R → 共通ADC → RP2350
```

YM2203ではアナログ2線をFM/SSGの独立入力として使い、ベースで合成して左右同じ信号へ出す。L/Rという端子名をFMの左右定位と解釈しない。YM3014B-FのFMはモノラルである。FMとSSGを音源基板で永久に混合すると後段で分離できないため、この版では分離を優先する。

FM受信・PCM展開・サンプルレート変換をYM2203の通常音声経路から外す。source MCUはSPI受信・YMバス制御・停止処理用として維持し、将来基板でのI2S送信用途も残す。MCU削除・Pico 2への置換・GPIO再配分は今回の採用内容に含めない。

## 音源ごとの3プロファイル

| プロファイル | アナログ2入力 | I2S | ベース側処理 |
| --- | --- | --- | --- |
| split-analog（YM2203） | L=FM、R=SSG | 未使用 | 各gain/mute→合成→dual mono |
| analog-stereo | L/R=合成済み全音声 | 未使用 | ADC L/Rをステレオのまま出力 |
| hybrid | SSG等の補助アナログ音声 | デジタル主音声L/R | 両経路のgain/delay整合→合成 |

I2S-onlyもhybridのADC寄与0として扱える。プロファイルは基板設定で決め、波形の有無から自動切替しない。全音声入りanalog-stereoと同じ全音声のI2Sを同時加算しない。未接続入力は寄与0とし、無信号や時計喪失を他経路への自動復帰・再発音の契機にしない。

## コネクタ・電圧・時計

G40の31=BCK、33=LRCK、34=DATA、37=AUDIO_L、39=AUDIO_R、各既存GNDを維持する。base GP15/16が音声BCK/LRCKを生成し、GP17で共通ADC、GP18で音源I2S DATAを受信、GP14で出力DACへ送信する。YM2203版は34の送信を無効にしてI2S寄与を0にするが、ベースの受信配線・バッファは残す。

将来のI2S契約候補は48kHz、左右各32bit slot、24bit有効、通常I2S（1bit遅延）、BCK=3.072MHz、3.3V。baseをBCK/LRCK master、sourceをslaveとする。これは配線を利用するための実装目標で、現時点で稼働検証されたモードではない。専用MCLK信号の新規追加は行わない。MCLK必須の候補は各音源基板内で用意する。

YMの独自シリアル出力はI2Sではない。別音源基板のMCUで書式・左右タイミングを復号し、YMの可変クロックとbase時計とのレート差をFIFO/適切な再サンプリングで吸収する。Rev Cの125:108固定比をすべての音源へ流用しない。I2S出力済みのモジュールでも、base slave契約へ適合できることを確認する。アナログ入力は既存review CのADC結合・減衰・bias条件を満たすように音源側の振幅を設計する。

YM3014B-Fは16pin SOP。YM2203の5V系SD/SH/シリアル時計からDACへ接続し、Si5351AのYMマスター時計をDAC CLOCKへ直結しない。RB/MPの基準バッファ、出力バッファ、電源decoupling、DC結合/フィルターをメーカー基本回路から具体化する。MCUのGPIOへ5V信号を直結しない。実装済みの通常品オペアンプ候補は5V単電源・必要な入出力範囲・帯域・負荷を満たすものから選び、個別品番と価格は次の回路/BOMで確認する。

## 他のFM音源への適用範囲

YM2608/YM2610はYM3016系専用DACに対応し、デジタル主音声とアナログSSGが分かれる。専用DACを入手できない場合は、音源側MCUで主音声をPCM/I2Sにし、SSGをbase ADCで取り込むhybridが候補。必要なら音源基板側で全音声を合成したI2Sを返すこともできるが、ADCの重複搭載を必須にはしない。

専用DACがなくても「RP2350自身のアナログ出力」が必要になるわけではなく、MCUでデータ変換し、共通PCM5102Aでアナログ化できる。ただし全ICの受信速度・PIO/DMA・左右形式への対応を保証したものではない。ADPCM用メモリ、追加アドレス/データ端子、WYM1/チップ識別/複数ポート・複数IC対応は各音源基板と将来APIの別検討。既存opn1 HOSTの互換だけで別ICの全曲が再生できるとは案内しない。

## 音質・gain・停止互換

YM2203でも最終的にはYM3014B-F→ADC→PCM5102Aとなる。前段DAC、バッファ、ADCの歪み・雑音・遅延を含み、純アナログ直出しの最短経路とは異なる。MCUのFM復号負荷が軽くなることを、変換段数や測定音質の改善と読み替えない。音質はRev Cとの音量整合試聴と実測で再受入する。

split-analogならFM/SSG独立gainとFMのみのソフトmuteをベース合成前に残せる。ADC入力段で飽和した波形は後段gainで修復できないので、入力ヘッドルームを先に確保する。hybridはADCとデジタル音声の遅延差を校正する。

既存HOSTのI2C0x42/protocol-v2/WYM1/opn1、USB CDC/MIDI、3.3V I2Cパネル、Si5351A可変時計は維持要件。新規HOST操作をYM2203再生の必須条件にしない。STOP/lease/所有権変更ではADC/I2S全寄与とPCM queueを破棄し、既存UMUTE→PCM5102A XSMTで最終全出力を消音し、source ENABLEも落とす。CのUMUTEは2許可信号のANDであり、片方LOWで最終全出力が止まる。FMだけを消すソフトmuteと、この最終ハードmuteを混同しない。

USB切断はUSB/MIDI/LOCAL_EDIT所有者を停止し、有効なI2C lease所有者は外部5Vで継続する。status読取り・USB再接続・入力時計復帰・panel再接続だけで再発音しない。source/入力形式の切替は停止状態で実施し、buffer/epochを破棄してから明示再生を要求する。

## 価格の扱い

比較基準は保存したreview Cの29,751円（各5枚/部品1セット）。このうちADC約1,236円、出力DAC約686円、source MCU2,310円は今回削除しない。2万円案の削減額を適用して3万円の達成を宣言しない。

YM3014B-Fは入手済みなので追加購入0円だが、バッファ・基準・RC・FM入力整合は別途必要。source FM受信用の変換IC/受動部品を減らせる可能性はあるが、source MCUの電源順序・バス・停止用の変換/ゲートを一括削除しない。価格目標は約3万円、増分は既存2,500円予備枠を含めて再算定する。ADC/DAC/SPI/パネル/可変clockを残す条件で、普通の0805/THT・標準via/HASL・同梱調達を継続する。新しい総額・新Gerber送料・注文時在庫は未確定。将来のYM2608/YM2610やADPCMメモリの購入費はこのYM2203一式予算に含めない。

## 次の回路化と検証

1. 保存Cから別版を作り、YM3014B-F 16SOP、RB/MP・出力バッファ、FM/SSG分離アナログ出力を追加。base ADCの両入力とI2Sは保持。
2. 電圧・バイアス・入力上限・DACシリアル時計/可変YM範囲・停止default、接点・GPIO維持を照合し、新版に対してnative ERCを実行する。
3. バッファ/フィルターの通常流通品を確定し、購入表とPCB面積/電源・放熱・送料を再見積。
4. ADC/I2Sの二重加算防止、rate差、消音・入力断・復帰・HOST/MIDI排他のモデル/実機試験。過去のRev C合格を新版合格へ転記しない。

本決定の記録ではCAD/GPIO/firmware/HOSTを変更していない。Cの静的検査と旧404ファイルの保存照合、文書diff検査を行う。Dの新回路・新ERC・実機合格の報告ではない。

## 一次仕様と参照

- [Yamaha YM3014B/F original catalog (1994-03)](https://bitsavers.trailing-edge.com/components/yamaha/YM3014B_199403.pdf)：端子、基本バッファ、タイミング、電圧・DAC仕様。
- [Yamaha YM2608 manual scan](https://manualmachine.com/yamaha/ym2608/5410883-user-manual/)：専用YM3016、デジタル主音声とSSG。
- [Yamaha YM2610 application manual / translation with original pages](https://ajworld.net/neogeodev/ym2610am_en.html)：専用YM3016、SSG/ADPCM。翻訳のピン方向表記は実設計時に原本で再確認する。
- [TI PCM1863](https://www.ti.com/lit/ds/symlink/pcm1863.pdf)、[TI PCM5102A](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)：ADC/DAC音声形式・時計・入力仕様。
- [保存Cの回路図・検証](../low-cost-schematic-review-c/README.md)、[保存C購入基準](../low-cost-schematic-review-c/COST.md)。
