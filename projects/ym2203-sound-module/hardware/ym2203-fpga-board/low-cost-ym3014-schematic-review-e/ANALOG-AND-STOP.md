# アナログ・電源・時計・停止の具体化

## ピンと基本回路

YM3014B-Fの16SOPは1=VDD、2=TO_BUFF、4=LOAD、7=SD、10=CLOCK、12=GND、14=RB、16=MP。3/5/6/8/9/11/13/15はNC。8DIPの端子番号を流用しない。全NCを明示し、GPIOへ5Vを直結しない。

メーカー基本回路（Yamaha1994 catalog p3）のRB→10µF/GNDと電圧フォロワ→MP、TO_BUFF→フォロワを採用。MCP6002-E/PはA側1OUT/2IN-/3IN+で基準、B側5IN+/6IN-/7OUTでFM、4GND/8VDD。RBとMPを直結せず、10µFをフォロワの出力へ移さない。CRBは1番+をRB、2番−をGND。RBの高インピーダンス配線を短くし、デジタルclockを近づけない。

MCP6002は1.8～6V RRIO・unity stable、typ1MHz/0.6V/µsの通常品。5V単電源で扱い、非RRIOのLM358や±電源前提TL072へ無検討で差替えない。100Ω RFMOUTはフォロワ帰還の外に置いて容量性負荷から分離する。MPの負荷・音声負荷に対する位相余裕、発振・settling・THDは実測が必要。

FMは100Ω→G40 37→base6.8k/10k分圧→10µF無極性AC結合→2.2k→ADC L。SSGは各1.33k負荷と10k合成を保持し、G40 39→同じbase右入力へ。追加の出力電解は不要（baseに既存AC結合がある）。FMの2.5V近傍DC biasとSSGのDCをADCへ直結しない。baseの入力clamp・RCを削除しない。これはライン用の基板間接続でありヘッドホン直結用ではない。

## 振幅・音質・ADC条件

5Vを±5%と仮定し、Yamahaの最大振幅±VDD/4を保守的上限、2段分offset余裕9mVとして、前段ピークは1.3215V。100Ω＋base6.8k/10kを1%ばらつき込みで計算した無負荷分圧は0.5869～0.5965、ADC点での上限推定は約0.788Vpeak。ADCのbiasを仮に1.65Vと置けば0.862～2.438Vとなる。これはADC入力負荷による追加減衰を無視した上限の静的計算で、PGA設定・全温度・実機振幅の保証ではない。

PCM1863の入力インピーダンスはtyp20kΩのため、実通過gainはこの分圧だけで決まらない。SSG合成のソース抵抗も含め、ADC PGAを0dBで開始し、FM/SSGの実振幅を測って合成係数を校正する。ADC入力が飽和してからソフトで下げても復元できない。gainを補う場合は先に入力ヘッドルームと最終合成のclippingを確認する。

20kHz/1.3125Vpeakの正弦波に必要なslewは約0.165V/µsでMCP6002 typ0.6V/µsより小さいが、typ値だけで全温度の歪みやDAC stepのsettlingを保証しない。既存base470p RCとADCの内部filterを維持し、DAC image・高域・ノイズ・低域を実測する。SPICEやTHD/SNR測定を実施したという記録ではない。

経路はYM3014B-F→buffer→ADC→baseMCU→PCM5102A。MCUによるFM復号/固定比再サンプリングが不要になっても、変換段は増えるので音質向上と断定しない。pure analog直出しの遅延とは異なる。FM/SSGの左右出力はbase内で合成したdual mono。37/39の役割は基板プロファイルで固定し、L/R名称から自動定位しない。

## 電源・配置

UDACとUAFはV5_MODULE/GNDから供給し、100nを各ICへ、10uX7Rを近傍bulkへ追加する。UDACは4.75V以上が必要なので、安易な直列抵抗フィルターで電圧を落とさない。供給端・配線・PTC込みの最悪電圧をUDAC1/12で確認する。DAC電流max6mAとopamp/負荷を考慮して、Cの5V予算へ追加10mAの設計枠を置く（実測値ではない）。MCUの3V3/AUXの供給先は増やさず、各レギュレータ出力は並列接続しない。

CRBは50PX10MEFC5X11、D5×H11mm・P2mm。YM40DIPソケット、source MCU、支持材と干渉しない位置を次のPCBで確保する。DAC本体5.3×10.2mm、leadspan7.8mm、1.27mm pitchからEのランドを作成。MCU等の5未確定ランドはCのまま残る。目標source100×80mm2層、base100×100mm4層、panel100×76mm2層。配置/配線前であり、この外形に収まることや機構高さの合格を主張しない。過密ならサイズと総価格を再比較する。

接点/音声GNDは既存G40を維持し、基板交換は電源OFF。power-up/down・base3V3とsource5Vの立上り差・CRB/結合Cの充放電を確認し、最終muteを閉じてから時計・ADCを初期化する。起動待ち時間は波形で決める。無根拠な固定待ちでclick-freeと宣言しない。

## 時計とI2S維持

YM2203 23SD/39CLK/22SHから各33Ωを介してUDAC 7SD/10CLOCK/4LOADへ接続する。UDACにはSi5351AのYMマスター時計を直接入力しない。YMの39番CLKと38番PHI_Mを混同しない。元の3V3 FM receiverにも分岐するので、総入力容量・反射・SD/SH setupとCLOCK edgeを実機で確認する。

YM3014BのCLOCK推奨範囲は0.65～3.2MHz、HIGH最小100ns、rise/fall最大50ns、データsetup条件もある。YM2203 masterとprescalerの設定から生じる実CLKを測り、可変clockの使用範囲を両ICの仕様の共通範囲へ制限する。最初の受入は4MHzの既存opn1を基準にする。Si5351A自体が出力できる全周波数、他IC向けDIPプリセットやprescalerの全設定を、YM3014でも使用可能と保証しない。制御側の周波数拒否/設定契約と各プリセットの波形検証は移植時の残件。

G40 31BCK/33LRCK/34DATAとbuffer・pull・OEは維持。base GP15/16 clock master、GP18 digital音声入力、GP17 ADC入力、GP14 DAC出力。source GP24DATA/25BCK/26LRCK/27TX_DISABLEは変更しない。Eの通常再生ではTX_DISABLE HIGHでI2S送信を止め、baseはI2S寄与0にする。将来のhybridの48kHz/32bit slot/24bit有効等はreview Dの設計目標で、Eで稼働確認したI2S機能ではない。

## 停止・復帰

YM3014にreset/mute端子はなく、時計を止めるだけでは最後のDAC値を保持し得る。YM resetやsource MCU resetだけを最終消音にしない。baseの直接STOP GP23、M_DAC_ALLOW/LINE_ALLOWのpull-down、UMUTE AND→PCM5102A XSMT、source ENABLE→RUN線をそのまま残す。

STOP/lease失効/所有者の切断時は、最終出力muteを優先し、ADC/I2S寄与と全PCM/DMA queue・イベント・owner epochを破棄、source ENABLEを下げる。sourceの後続ACK、ADCの過渡、USB再接続、時計復帰だけで再発音しない。clear後の明示BEGIN/PLAY/新NoteOnを要求する。各入力のzeroは最終ハードmuteの代わりではない。FM-only muteはADC L寄与を0にする処理であり、片方LOWで全出力を止めるUMUTEの動作とは区別する。

base CPU自体のhangに対する独立watchdogを新設した回路ではない。既存の起動Hi-Z/default muteとsource reset、ユーザー向けhard RESETを維持する試作要件である。
