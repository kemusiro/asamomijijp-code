# 操作とP2 firmwareの実装契約

設計仕様。現在のfirmwareへ組み込んだコードではない。

## 操作子

OP1～4で編集対象を選択。encoderを回してpage/項目、短押しでpageとfine editを切り替える。
NOTEはmomentary、押下で新key-on、離してkey-off。トグル発音は初版で無効。
STOPはどの画面でもglobal STOPを呼び、mute/queue取消し/所有権解放を最初に行う。
encoder長押し1秒でSAVE画面、回転でslot0～63、短押しで保存確定。STOPでキャンセル。
PRESET画面の選択だけではloadしない。短押しの確認でloadし、無音を維持する。

| page | knob1 | knob2 | knob3 | knob4 |
| --- | --- | --- | --- | --- |
| OP LEVEL | TL0～127 | MUL0～15 | DT code0～7 | KS0～3 |
| OP ENVELOPE | AR0～31 | DR0～31 | SR0～31 | RR0～15 |
| OP SHAPE | SL0～15 | SSG-EG enable/shape0～15 | OP enable0/1 | 未割当 |
| COMMON | ALG0～7 | FB0～7 | NOTE0～127 | velocity1～127 |

DTはraw codeを保存し、画面に符号付き変位も併記する。MUL0は×0.5、TLは小さいほど大きい音。
SRはYMのD2Rに対応する。OP1..4はalgorithmの論理順で、register offsetは**0/8/4/12**。
UIのOP2/OP3を単純に4ずつずらして入れ替えない。
YM2203にないLFO/パン/AM感度は表示しない。clockはメタデータで、プリセットloadからSi5351Aを書き換えない。

起動・OP切替・page切替・load/import・USB側編集で、4つのknobは毎回pickup待ちへ戻す。
12bit正規化値の±32以内への到達または前回値との交差でcatchし、それまではpatchを変更しない。
encoder fine editで変更したときもそのknobをrearmする。待機矢印とpatchの実値を表示する。
ADCは1k/100nFを設ける。各channelの初回を捨て、4ch各1kHz以下でsample→IIR→20ms更新を初期候補とする。
ADCの実settling/量子化は現物で確認する。接点は5～10ms debounce、encoderは合法Gray遷移だけを数え、
15pulse/30detent製品を「1detent=4edge」と決め打ちしない。半周期detentと回転方向を現物で校正する。

## 表示とスケジューラ

240×240 RGB565、上部にslot/name/dirty/owner、中央にOPとpage、下部に4値・pickup矢印。
envelope図はパラメーターの概念図とし、YM実測時間や音量計と偽らない。
20cm候補ケーブルの初期SPIは2MHz、128byte以下の差分chunk（転送約0.512ms）で処理を返す。全画面115200byteの一括同期送信はしない。
EEPROMの100kHzは16byte以下のchunkで共有schedulerへ返し、clock/ADC/panel/STOPを飢餓にしない。
service I2Cはchunk単位のtimeoutを設け、故障したEEPROMを無限待ちしない。STOP GPIOの処理遅延は実装後に測定する。
EEPROM内部program完了はACK polling、page分割・10ms期限はSTORAGE.mdに従う。
保存・importは停止状態に限定。回し続けるたびの自動保存はしない。

## 制御権と安全停止

既存HOST wire ABIを変えず、内部にLOCAL_EDIT sessionを加える設計。
起動はBROWSE/無音。UIを表示・操作するだけでは音源を取得せず、HOST/MIDIの既存動作を継続する。
別所有者の再生中はpatch変更をRAMへstageするだけで、YM書込みとNOTEを拒否しBUSYを表示する。
新たにLOCAL_EDITへ入るには他所有者がない状態で明示的にENTER EDITを確定する。
一律STOPを押した後も自動で編集音を再開しない。再ENTERと新NOTE/Note Onが必要。

LOCAL_EDIT中はI2C BEGINを既存BUSY結果で拒否し、I2C global STOPは常に有効。
USB-MIDI CH1の新Note On/Offを編集用FM1へ同じsession内で入力する。CH2～6は初版ではreject/破棄し後から再生しない。
一般のMIDIモードへ戻るときはSTOP→明示EXIT。既存MIDI所有者へ無断でpanel書込みを混在させない。
NOTEが押されたままの起動/STOP/再接続では、一度releaseするまで再発音を禁止する。

全patch適用ではkey-off後に29設定writeを分割し、完了世代tokenが一致するときだけ新key-onを許可する。
TL等をlive反映する場合も最新値をcoalesceし、<=50updates/sの初期上限、writerの実完了を確認する。
ALG/FB・preset全体など音量が跳ねる変更はkey-off/短いmute/適用/新試聴で行い、無断retriggerをしない。
STOPはLCD/EEPROM/内部SPI完了を待たず最終gateを閉じ、世代更新、event/PCM flush、4ms guardの順序を守る。
物理STOPはGPIO入力でfirmware処理する。独立ハード停止やwatchdogではない。

USB切断はLOCAL_EDITで全音停止、session解放、キー状態破棄。USB再接続で再発音しない。
USB未接続で起動した物理NOTE試聴は可能。I2C所有中のUSB切断は既存HOST leaseが続けば再生維持する。
RUN/reset/clock変更/faultはH/Iの停止条件を引き継ぐ。profile/clockを演奏中に変更しない。

追加firmwareの受入は、HOST YsII全曲/STOP/lease/USB-MIDI/所有権/USB切断回帰に加え、
LCD連続更新中の音切れなし、pickup、全OP register/readback、SAVE中STOP、電源断保存、JSON再importまで行う。
