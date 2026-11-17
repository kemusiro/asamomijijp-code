# review F：bus手順・PSG配線・5V変換

本書は候補仕様。新しいGPIO driver・回路図・実機検証は未実施。

## 直接制御とレベル変換の分担

直接parallelではPGA2350が8bit値とstrobeを出すため、SPI→parallel変換を不要にできる。
connector側の電圧は3.3Vのまま。5V音源の入力VIH/VIL、出力VOH/VOL/絶対最大と電源順序は別途成立させる。
まず5Vカード側にdata8bitと必要controlのbufferを置く。書込み専用なら固定方向AHCT系buffer候補等で足り、
自動方向検出型変換や独立MCUを一律に追加しない。ICが3.3V入力を許す経路の省略可否は定格/負荷確認後に判断する。
仕様段階で特定AHCT品の実装点数・駆動能力を確定したとは扱わない。

READY等の戻り線を5V push-pullのままPGA2350へ接続しない。
SN76489ANのREADYは一次資料上open collectorなので、当該品では3.3V pull-upで追加変換を省ける候補。
派生品・互換品で同じ出力方式とは限らず、型番ごとの確認を必要とする。
全アナログ出力は音声負荷/レベル/AC結合を通す。digitalのレベル変換とanalogの整合を混同しない。

## generic4制御線

CTL0=A0、CTL1=CS_N、CTL2=WR_N、CTL3=RD_Nがgeneric候補。
これはすべてのPSGが同じ端子を持つという意味ではなく、以下のprofileで読み替える。
moduleごとにstrobeのinactive/Hi-Z時biasを3.3V側で設定し、connectorへ5V pull-upしない。
MOD_ENABLEは既定Lの許可/RESET信号。全音源に物理RESETがあると仮定しない。
SPI時にはCS1=CTL1、CS2=CTL0を追加可能。CSは計3本で、それ以上なら局所decode等を要する。

将来readbackするカードには双方向transceiverを用意する。SN74LVC8T245のA=3.3V/B=5Vが候補。
generic RD_NをDIR、CS_NをOE_Nに使う省部品案は、CS非活性時にのみDIRを変え、
base dataを入力へ切替えてからcard→baseへ転送する条件付き。戻すときもCSで切ってからDIR変更。
chipのCS/read output timingに合わなければこの直結案を採用しない。write-only AY/SNにはこのread回路を必須にしない。

## AY-3-8910/12：readを発生させないwrite-only案

対象はBC2を外へ出せる品種。BC1を音源基板上でLに固定し、CTL1→BC2、CTL2→BDIR。
CTL0/CTL3はNC。DA0～7はconnector D0～7へ同じbit番号で配線する。
A8/A9等の選択strapは使用品種に合わせ、address byteの上位bitもその選択と照合する。

| BDIR | BC2 | BC1 | 動作 |
| --- | --- | --- | --- |
| 0 | 0 | 0 | inactive |
| 0 | 1 | 0 | inactive |
| 1 | 0 | 0 | address latch |
| 1 | 1 | 0 | register write |

BC1=0を固定して、read状態011へ入れない。手順はBDIR=0中にBC2を決め、dataを更新し、
setup後にBDIRをpulse、hold後に次cycleへ進む。レジスタ操作はaddress latch→data writeの2cycle。
書込みだけならカード上のdata bufferは一方向でよい。

候補はclock2MHz、setup/hold各1µs、address/write pulse各2µs。
GI資料のAY-3-8910/12にはwrite pulse最大10µsがあるので、割込みで長く延びたpulseは許容しない。
active strobe中を短いcritical section等で上限管理し、音声/USBを阻害しないことを実装時に確認する。
高速化やclock変更は採用品種のデータシートを再確認してから行う。
AY-3-8913やYM2149をこの候補値で無条件に扱わず、それぞれのprofileを作る。

## SN76489AN：命名上のbit反転とREADY

TIの当該資料は**D0をMSB**と呼ぶ。connectorのBUS_D0はソフトウェアbyteのLSBと定義するため、
データ線の名前を同じ番号同士で接続しない。

| 論理bit/connector | TI SN76489AN名 | DIP pin |
| --- | --- | --- |
| D0（LSB） | D7 | 10 |
| D1 | D6 | 11 |
| D2 | D5 | 12 |
| D3 | D4 | 13 |
| D4 | D3 | 15 |
| D5 | D2 | 1 |
| D6 | D1 | 2 |
| D7（MSB） | D0 | 3 |

CTL1→CE_N、CTL2→WE_N、CTL3←READY、CTL0=NC。clock候補3.579545MHz。
データsetup後CE/WEをactiveにし、約32clockの転送時間＋2µs guardを待ってREADY Hを確認してから完了とする。
式はceil(32×10^6/実clockHz)+2µs。候補clockでは11µs、READY待ちは100µs deadline候補。
assert直後の古いREADY Hだけで完了させない。待ちの間もdataを保持し、timeoutなら最終gateを閉じて明示再開を要求する。
clockはprofileで検証し、欠落clockを時間待ちだけで正常扱いしない。
この候補波形は実機/採用品のtimingで再確認し、派生品に流用しない。

SN76489ANにRESET端子を仮定しない。MOD_ENABLEは未接続でもよく、
baseがCE/WEをinactiveにし、最終muteを閉じ、再開前に全attenuatorを消音初期化する。
独立のcard側強制gateを追加必須にしない。

## SIOと排他

dataの下位4bitはGP0～3、上位4bitはGP30～33。2つのSIO output bankに分かれる。
一度に8bitが切り替わる保証を要求せず、strobe非活性中に全bitを更新し、setupを置いてからstrobeを出す。
active中に別core/IRQがdata/controlを書かないようbus writerを一つにする。
現mapは単一PIOの32pin windowに収まらず、単純なPIO OUT8の性能保証はしない。
音声PIO・DMA・USBの既存資源との実行時間検証は未実施。
