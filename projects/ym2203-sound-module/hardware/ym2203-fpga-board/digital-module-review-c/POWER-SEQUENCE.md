# 電源順序・ADC入力保護レビューC

2026-11-16。接続済み回路とメーカー資料を照合した静的レビュー。
**入力範囲/電流制限/RC放電と論理条件の確認であり、SPICEのsilicon model、実電流・過渡波形・音質の実測ではない。**
根拠は[sources.json](sources.json)、数値は[verification.json](verification.json)。

## 電源と独立した停止

共通外部5V系から、base PGA3V3、base AUX3V3、Core2350B0のMCU3V3、ADC3V3を個別生成する。
各regulatorの出力を結ばず、GNDは共通。USB VBUSはbaseで検出専用、5V供給へ接続しない。
Core2350B0のFPC USB adapterもmodule VBUSへ直結するため、carrier給電中は接続しない。
最初の書込みはmoduleを取り外して単体で行うか、電源を重複させないSWD手順を別途検証する。
基板差替えは外部5VとUSBを切る。hotplugには対応しない。

base GP34のMODULE_ENABLE、GP38 DAC_ALLOW、GP39 LINE_ALLOWは、それぞれRUN_NとのANDを通す。
リセットボタン/MCU RUNがLなら、GPIOがまだHでもmodule許可と最終出力を閉じる。
baseのADC/USB/HOSTのソフトウェア応答やSPI ACKを待って音を止める回路にはしない。

音源側ではL_MOD_ENABLEの10k pulldownと、MCU3V3動作のUENABLE Schmittによりdefault禁止とする。
UENABLE出力は次へ接続する。

- URUNODのopen-drain出力でCore RUNをLへ。外部10k pullupを備え、RESETボタンとpush-pull出力が衝突しない。
- ADC用TLV755 ENへ。LならADCを無給電にし、regulator内部のdischargeと680Ωの常設bleederで放電する。
- UYMALLOWの入力へ。local GP34 YM_RESET_RELEASEとAND、さらにCore RUNともANDしたYM_RELEASE_SAFEで5V側のQ1/Q2 clampを解除する。

YM側reset clampのbiasは**音源5V**で供給するので、MCU3V3だけ消えてもYMが生きたまま解除されない。
Core RESETボタンもUYMRUNでYM resetへ直接反映される。MCUのGPIO初期化完了だけには頼らない。
SPI/OE・local WR/RD/CSのpullup/Hi-Zも残し、STOP後は古いbuffer/commandsを無効化する実装要件とする。
独立外付けwatchdog/latchは追加しないprototypeの条件であり、同時多重故障まで保証した回路ではない。

| 条件 | 回路で要求する状態 |
| --- | --- |
| 初回5V ON、base reset中 | module ENABLE=L、DAC/LINE mute、YM reset。Core/ADCの起動順に依存して発音しない |
| ENABLE=H、Core初期化中 | Core起動、ADC rail起動。local YM解除=0、入力switch OFF、最終gate閉 |
| ADC電源/PLL/設定確認後 | GPIO3をARM可能にする。YM_RELEASE_SAFEもHになった時だけ入力switch ON。整定/無音bufferを確認して最後にbase gateを開く |
| STOP/lease/owner交代 | base最終gate閉、ENABLE=L、Core RUN/YM reset、ADC給電OFF。sessionと遅延bufferを無効化 |
| baseだけ3V3喪失 | ENABLE線はmodule側でL、Ioff/default pullに従い停止。USB側への逆流を防ぐ |
| module MCU3V3喪失 | RUNの許可が消え、5V reset clampがYMを止める。ADC EN/入力enableはpulldownで閉じる |
| ADC railだけ喪失 | ADC側Ioff bufferとTMUXで隔離、baseはclock/音声faultを検出して閉じる実装が必要 |
| Core RESETボタン | open-drain RUN回路をLにし、YM resetと入力switchを閉じる。再起動だけで再発音しない |

256通りのBoolean組合せを検査した。これは電源の連続的な立上り、半端な電圧、GPIO回復時間の電気シミュレーションではない。
mid-rail brownout、最終LINEのクリック・通電過渡は実測して判断する。

## ADC railを消した時のデジタル信号

BCK/LRCKはADC3V3給電のSN74LV4T125で受ける。ADC DOUTはMCU3V3給電のSN74LVC1G125で受ける。
各receiverのVCC=0時に出力を遮断するIoff仕様を選び、plain SN74LVC125Aに同じ保証があると推測しない。
ADC VREF(pin6)とinternal LDO(pin11)はそれぞれdecouplingのみ。外部3.3Vをpin11へ入れない。
AVDD/DVDD/IOVDDは同じADC3V3。AGND/DGNDは共通GND面へ戻し、間に切れたgroundを作らない。

ADC制御はlocal I2C0 GP20/21、7bit address0x4A（AD=0、資料の8bit write0x94）を使う。
pullupはADC railだけに4.7k。**MCU internal pullupを無効にし、open-drain/releaseのみ、push-pull HIGH禁止**がfirmware条件。
ADC OFF時にMCUからHIGHを出してよい回路とはしていない。これを外部bus isolator不要の成立条件として検査/受入する。
逆向きにはCore RP2350BのGP20/21がFT端子で、無給電時3.63V条件に対しADC railは3.3V級。
ADC/GPIOやregulatorの実際の上限、OFF漏れと電源順序は実測でも確認する。

GPIO3(pin19)は新しいMCU GPIOを使わず、入力switch用ARMに使う。
初期化ではpage0 reg0x11のbits6..4をGPIO機能0へ、reg0x13 bits6..4をoutput4へ設定し、reg0x14 bit7は最初0。
電源flags/PLL/48kHz/無音bufferを確認してbit7=1へ。ほかのbit・予約値はread-modify-writeで維持する。
GPIO3のreset時INT機能だけでは入力許可とせず、**YM_RELEASE_SAFEとのhardware AND**も通す。
GPIO1/DMINは100k pulldownとし、GPIO出力やdigital input mixを有効にしない。未使用analog入力はNC、MUXは選ばない。

## SSG入力の保護と負荷

各声の実接続：

`SSG -> 3.01k:1k分圧 -> TMUX1511 -> 2.2uF AC結合 -> 4.7k -> ADC VIN`

元SSG端子に1.33k負荷、TMUX出力に100k bleeder、ADC pin直近に470pFとBAT54Sのrail clampを置く。
分圧枝を含むDC負荷は約999Ω（switch ONでは100kも含む）。旧1k負荷との違いを小さくする設計。
入力switchはAC結合**前**に置き、TMUXの信号を0〜約1.33Vに収める。負側へ振れるAC後のsignalを無条件にTMUXへ通さない。

- 5.25V rail stepと分圧抵抗1%のworst比では、TMUX入力は約1.329V。無給電時保護0〜3.6V条件内。
- ADC側はbias0〜1.8Vと単線stepの単純区間で約−1.329〜3.129V。メーカー絶対最大−1.7〜5.0V内だが、絶対最大を通常動作の許容帯域と扱わない。
- 外付けBAT54Sはpin1=GND、pin2=ADC3V3、pin3=ADC VIN。負側はGND→VIN、正側はVIN→ADC railに流す。BAT54A/C等に置き換えない。
- 4.7kΩの1%下限に対して5.25V＋bias1.8Vを全て置いた保守的電流は約1.52mA。TIが示す内部ESD電流約5mAを下回る電流制限の算術。
  外付けclampの温度依存・接合容量・注入先rail上昇は別途測る。抵抗断線/短絡など多重故障を合格範囲に含めない。
- TMUXがOFFの時に定常SSGを遮断し、AC capacitorが保持した有限のchargeはclamp/bleeder/dischargeへ逃がす。
  全ての瞬間で注入電流が厳密に0になるという説明はしない。

ADC input impedanceの**typ20kΩ**を使う受動RC計算では、SSG→ADCのgainは1kHzで約0.196。
1kHz基準で20Hz約−0.086dB、20kHz約−0.269dB。typ入力抵抗と理想部品を使った計算で、音声passbandの保証ではない。
ADC filter・switch・diode・SSG出力impedanceの実モデルによるSPICE/測定は残る。
TIの一般例100Ω/10nFから電流制限優先で値を変更しており、TI推奨回路そのものの性能とは称しない。
3声はADCのleft MUX field0x07で加算、rightはmute。reg0x06 bit6を保ち、field0x07をregister byteに直書きしない。
FM100%をFM枝のunityとして保ち、SSG側はこのADC伝達を含めて校正する。音量比の実機受入は再実施する。

## OFF待ち時間と再起動

ADC外付けcapacitor・reference/internal LDO側のcharge・AC couplingを含む設計上限を80µF、
680Ωの1%上限とOFF時流入50µA以下を条件にする。**TLV755のtyp120Ω active dischargeを上限計算には使わない。**

`V(t) = I_leak R + (V0 - I_leak R) exp(-t/(RC))`

V0=3.6V、t=250msなら約0.072Vで0.1V未満。従って**OFFを最低250ms**維持してから再初期化する案。
capacitanceと50µAは最終部品・全pinで確認すべき設計条件で、測定済み最大値ではない。
TPADC3で0.1V未満を確認し、外れれば待ち時間/bleeder/漏れ対策を変更する。
実際は内部dischargeも働く見込みだが、typ値だけでリセット成立としない。

STOP ACKはgate閉・session破棄を確認して返す。quiet restartはbackgroundで行い、再発音には明示BEGIN/PLAY/Note Onが必要。
直後にBEGINが届いた時も、既存HOSTへ非公開待ち命令や新しいwireを要求しない。
I2C status応答を保った準備待ちを実装し、HOSTのtimeout内にACKを返せるか検証する。未準備を成功扱いしない。
この待機のfirmware実装・実機時間は未検証。250msのOFF計算だけでHOST互換を実機合格にはしない。

## 残す実測

TPM3、TPADC3、TPADCEN、TPARM、TPRESETを用意した。
5V ON/OFF、USBだけ接続、Core reset、base reset、ADC clock停止、STOP直後BEGIN、lease復帰を測る。
電流・LDO/接点温度、YM端子4.75〜5.25V、ADC VIN/railの過渡・漏れ、clamp電流とクリック、最大late/underrunを記録する。
source受信/SRC/ADC遅延合わせ・I2S slave実装と、MIDI/USB切断・I2C所有継続はfirmware移植後に旧HOSTで回帰する。
