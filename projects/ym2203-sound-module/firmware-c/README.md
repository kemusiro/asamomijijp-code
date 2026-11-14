# Rev C C SDK版 0.5.0-alpha.3 — USB-MIDI＋I2C WYM1

alpha.3は、ユーザーのalpha.1ログで確認した`audio_ready=0 fault=16`に対応する修正版。
MIDI発音準備で繰り返す音声再起動に対し、RP2350-E5に従って全連鎖DMAを無効化してからabortする。
PIO FIFOと転送記述子の初期化後にDREQ要求カウンタを更新し、DMAを再有効化する。
実際のaudio.cループによる再起動・要求残存モデル試験を追加し、起動失敗時のTXSTART/TXDMA診断も残す。
`fault=16`の1msタイムアウトは維持する。実機の内部DMA状態は旧ログにないため、詳細な発生経路は未確定。
[音声再起動の更新・再確認手順](AUDIO-DMA-RESTART-README.txt)。alpha.3で6つの単独音と和音保持、
`audio_ready=1 fault=0`、左右正常・歪み/音切れなしをユーザー実機で確認済み。
今回の報告にCDC生ログは含まれない。
[再確認の実機記録](verification/c05-alpha3-restart-hardware-acceptance.json)。制御権切替も実機受入済み（下記）。

alpha.2は、通常のNote Off後にもSTOP用の200ms入力破棄を追加していた不具合を修正する。
135msの解放待ちと合計335msになり、MIDI画面が300ms後に送る次の単独音や和音を落としうる。
実際のmain.cと同じイベント間隔で再現し、通常解放に限って余分な破棄を除いた。
STOP/panic/USB喪失の安全停止後は従来どおり入力破棄する。USB記述子、GPIO、音声経路、I2C v2は維持する。
[修正内容と再確認手順](MIDI-RELEASE-FIX-README.txt)。alpha.2の通常Note Off修正もalpha.3へ含める。

受入済み0.4.0-alpha.2へUSB-MIDI1.0（FM3声＋SSG3声）を追加したC版。
CDCのログ/操作画面と100kHz I2C v2を併用し、先に演奏を始めた側の制御権を守る。
I2C STOP/CDC STOPは全体停止、MIDI panicはMIDIだけを停止する。
FM受信・PCM変換・I2S・承認済みGPIOと既存のI2CホストAPIは変更していない。

**0.5版のUSB-MIDI基本動作はユーザー実機で合格。** 認識、FM/SSG音階、6声同時発音、
全音停止、左右正常、歪み・音切れなしを確認した。今回の報告にCDC生ログ・OS名は含まれない。
[基本動作の実機記録](verification/c05-alpha1-basic-hardware-acceptance.json)。
**alpha.3のMIDI/I2C制御権切替も実機受入済み。** MIDI中のBEGIN拒否、I2C STOP、
I2C中のMIDI不発音、終了後の無音と明示的MIDI復帰を確認した。HOSTは診断191件とCRCを検査し、
最終Rev Cは`audio_ready=1 fault=0 gates=0`、I2C実行191/191、MIDI owned=0。
拒否されたNote Onは7件で、プローブ18音全件の送信完了までは未確認。
[切替受入記録](verification/c05-alpha3-handover-hardware-acceptance.json)。
**USB切断・復帰もユーザー実機で受入済み。** HOST v1.1とRev CのログでUSB切断中の
I2C診断191件完走・CRC一致・fault=0・gates=0・クリップ0を確認した。最大書込み開始遅延4,751µs。
再接続後の無音とMIDIへの明示復帰はユーザーの音声確認。提示されたSTATUSはMIDI復帰前のI2C完了時点。
[実機受入記録](verification/c05-alpha3-usb-disconnect-hardware-acceptance.json)。
正常終了直後のKEEP競合はHOST修正済み。現行UF2と修正版HOSTを[常用セット](DAILY-USE-README.txt)へまとめた。
**現行0.5.0-alpha.3でも、操作側PicoからのYs II全曲再生を実機受入済み（ユーザー報告）。**
`events=123137/123137`、HOST PASS・DONE、`fault=0 gates=0`をユーザーが確認した。
FM100%で良好な音量バランス、左右正常・歪み/音切れなし。今回のHOST/Rev C生ログは未提示のため、
詳細な遅延・キュー・CRC・クリップの数値を新たに照合したとは扱わない。
[現行版の全曲受入記録](verification/c05-alpha3-fullscore-hardware-acceptance.json)。
既に使用中のUF2とライブラリの再転送は不要。過去の配布ZIPと受入記録は作成時点のまま保持する。
[修正と検証記録](verification/c05-alpha3-usb-disconnect-keep-done-fix.json)。
MIDI1～3=FM、MIDI4～6=SSG、各チャンネル1音・固定音色/固定音量。
音色編集、Program Change、Pitch Bend、SysEx、MIDI送信、MicroPython REPLは含めない。
物理USB切断と実際の可聴遅延はモデル試験から保証しない。

## 受入済み0.4.0-alpha.2のI2C全曲再生


**alpha.2のI2C全曲再生は、HOSTとRev C双方のログを照合して実機受入を完了した。**
操作側PicoのMicroPythonから100kHzで123,137件を転送し、298,218msの演奏を完走。
HOSTのCRC32=ae592289・再送0と、Rev Cの全件受信/実行・fault=0・gates=0を確認した。
FM100%で音量バランス良好、歪み・音切れなしとのユーザー報告。

Rev Cログには2回の完了記録がある。先のHOSTログと一致する1回目の最大書込み開始遅延は
4,475µs。その後の再演奏もDONE I2Cまで完走し、最大遅延4,480µsだった。
双方ともクリップ0、音声キュー1～2ブロック。2回目の演奏中のイベントキュー最小値は768件で、
終了時のmin_queue=0は全件適用後の正常な空を含む。RX除外観測3/4回はパルス数ではない。
2回目のHOSTログは未提示のため、先のHOST集計と混同しない。
[両側ログの実機受入記録](verification/c04-alpha2-hardware-acceptance.json)。

alpha.2はI2S起動直後のDMA/FIFO競合を修正した版。
alpha.1ではI2C v2識別とSTOPの後、BEGINがcode4で拒否され、Rev Cは2音声ブロック時点で
fault3（I2S TXSTALL）、楽曲0件と報告された。旧コードはDMA開始直後にI2S SMを有効にし、
最初のDMA転送が届く前の空待ちも実行中の送信異常として扱っていた。
SMを無効にしたままDMAで結合TX FIFO（8ワード）を満たし、開始時のフラグを一度クリアしてから有効化する。
1ms以内に満たせなければSMを開始せずfault16で消音停止する。開始後のTXSTALLは従来どおりfault3。
従来の転送モデルはこのDMA開始遅延を扱っていなかったため、実際の起動ヘルパーを使う回帰試験を追加した。
BEGINの準備失敗も、音声側の異常はcode12/AUDIO、USB所有中の拒否はcode4/STATEと区別する。
ホストの例外にはコマンド名・状態・audio_okを含める。パケット形式やBINに変更はない。
再確認は新UF2を書き込み、操作側の`/lib/ym2203_revc_stream.py`を更新する。
既存`/music/song.bin`と`host/main.py`はそのまま使える。


操作側Pico/Pico2のMicroPythonから、同じYs II BINをI2C経由で全曲再生する実装を追加した。
音源側に全曲を展開せず、1024件の先読みリングと32件/要求のv2パケットを使う。
100kHzで開始し、WYM1の時刻・順序・値、CRC32と連番、1秒リース、STOPを検査する。
音声のPIO/DMA・125→108変換・4.5ms蓄積は受入済みalpha.7から維持する。GPIOの再割当はない。
**I2C全曲完走と終了時消音を両側ログで確認済み。** 旧v1と署名・要求が異なるため、v2ホストを使う。

- まず読む：[結線・操作側へのファイル配置・実行手順](I2C-YSII-README.txt)
- 仕様：[I2C protocol v2](protocol-v2.md)
- 受入済み手順：[I2C停止・通信休止・再開の総合確認](I2C-RECOVERY-README.txt)

総合確認v1はalpha.2のUF2を維持し、操作側の`host/recovery_check.py`だけを追加する。
`tools/build_recovery_check.py`でHOST専用ZIPを生成できる。既存の13秒診断データを用い、
STOP後の4秒無音、全演奏、I2C無効化と1800ms休止・再接続後の4秒無音、再演奏を検査する。
通信休止では意図的なセッション`error=8`を期待し、音声`fault=0`と区別する。
0.4.0-alpha.2の総合確認はユーザー実機で4区間とも合格。STOP/通信休止/再接続後の4秒無音、再演奏、fault=0を確認した。
[停止・復帰の実機記録](verification/c04-alpha2-recovery-hardware-acceptance.json)。
再現：`python3 tools/verify_host_micropython.py --micropython /path/to/micropython --recovery`。
これはソフトウェアによる通信休止・再接続であり、物理ケーブル抜去や断線試験ではない。
- 操作側：[main.py](host/main.py)、[v2ライブラリ](host/lib/ym2203_revc_stream.py)

実機確認ZIPの`revc-c.uf2`は音声経路のテスト音階のみを内蔵する。
Ys IIはZIP内`host/music/song.bin`から操作側Picoへコピーし、Thonnyで`host/main.py`を実行する。
C版はUSB CDCでの内蔵BIN再生も保持する。I2C所有中はUSBのplay/test/capture/bus変更を拒否し、
USB STOPは全体停止。I2C演奏中のUSB切断はI2Cセッションを停止せず、I2Cのリースで監視する。
0.4版にないUSB-MIDIを0.5版で追加した。MicroPython REPLは提供しない。従来版の成果物は維持する。


**alpha.7でYs II内蔵BINの全曲再生を1回完走し、FM100%で良好なバランス、歪み・音切れなしをユーザー実機で確認した。**
添付ログは`events=123137/123137`、`state=2`、`fault=0`、`gates=0`、`DONE`。
クリップ0、最大変換213µs、キュー1～3、書込み開始遅延最大4,353µs、ログ欠落0。
遅延集計123,065件が1ms未満、残り72件が5ms未満で、全123,137件と一致する。
`BUS writes=123143`は楽曲123,137件と完了後の消音6件を含む。
`reject_observations=5`は除外フラグの観測回数で、クロックのパルス数や物理的なノイズ原因の確定ではない。
これにより「Rev Cで同じYs IIを全曲再生する」ローカル再生の受入を完了した。
I2C経由の全曲転送はC0.4 alpha.2に加え現行C0.5 alpha.3でも実機受入済み。
USB-MIDIの基本動作・制御権切替・USB切断復帰も0.5版で実機受入済み。長時間連続運転は別途未検証。
[実機受入の数値記録](verification/alpha7-hardware-acceptance.json)。

**以前のalpha.6では46.8秒・19,470/123,137イベントでfault=9、受信コードの指数0で消音停止した。**
`RXFAULT reason=1 flags=1 index=51 word=0fd60000`、ゲインQ10は1024（100%）。
13ビットのコードは0x1FA、指数0、仮数506。ゲインの入力異常ではないことまで確認できた。
前後は`87ba0000`・`61ee0000`。キュー1～2、クリップ0、最大変換149µs、実行遅延4,341µsで、
alpha.6のサンプル待ち追加だけでは解消しなかった。物理的な発生原因は未確定。

alpha.7では受信CLKのlowとhighを、それぞれ2 PIOサイクル離れた位置で確認する。
短いhigh/lowへの揺れを検出したら同じ状態の待ちへ戻り、データのビット数を進めない。
32MHzでチェック間隔62.5ns。データを遅らせて読むだけだったalpha.6と異なり、
クロックを余分に数える条件への対策である。正常な24ビット・SH同期・ビット順は維持する。
短い余分なhighパルスを含むモデルでは、alpha.6は有効な仮定値`87eb0000`から
今回と同じ異常値`0fd60000`を生成し、alpha.7は元の値を保つ。
これは再現可能な仮説であり、実機でそのパルスや元データを測定した結果ではない。

`RX qualify_ticks=2 ... reject_observations=N`は、PIOの除外フラグをCPUが観測した回数。
複数の揺れが1回にまとまる場合があり、パルス数や全てのノイズを検出した数ではない。
IRQ0はフラグとしてポーリングするだけで、CPU割込み処理を追加しない。
無効な指数0の変換チェック・異常時消音は維持し、不正値の補間やイベント間引きは行わない。
再発時は消音後の`RXFAULT`へ理由、フラグ、ブロック、最初の異常位置、生データと前後、
変換ゲインを記録する。`reason=1`は変換検証、`reason=2`はゲイン検証、
`flags=1`は指数0、`flags=4`は無効ゲイン。端の前後値0は隣接フレームなしを表す。

alpha.5の125入力→108出力・2ブロック蓄積（公称4.5ms）と既定FM100%を維持する。
固定ゲインのPCM・音色・エンベロープ・WYM1の時刻と順序・GPIOに変更はない。
従来の内蔵BIN再生はフラッシュから読む。新I2C経路では操作側から順次転送する。
MicroPython版のUSB-MIDI/REPLも、受入済みの別成果物として保持する。

## 書き込む前に

- Rev Cの承認済みGPIOを変更しない。GP0..7=データ、8=A0、9=RESET、10/11/12=I2S、
  13/14/15=CS/WR/RD、16/17/18=FM、19=LINE、22=ARM、26=DAC。
  GP20/21は承認済み外部I2Cのopen-drain。27（予備）・28（IRQ）は入力。
  USB音声経路テストでは操作側I2Cを外し、I2C全曲試験では手順書どおりにつなぐ。
- 外部5 V、4 MHz YM2203C、AE-PCM5102A、既存ミキサー、JLINE→AMS-22を使う。
  起動・接続だけでは発音しない。基板・AMS-22の音量は低くする。
- **UF2の書込みでMicroPythonを置き換える。boot.py/main.py/lib/必要なデータをPCへ保存する。**
  フラッシュ上のMicroPythonファイルがそのまま残るとは仮定しない。
- USBシリアル制御を使う。ThonnyのMicroPythonバックエンドではこのC版を操作しない。
  下記のブラウザー画面または115200 bpsのシリアル端末を使う。

## USB内蔵再生の互換性確認（再現用）

1. 操作画面を再読み込みし「BOOTSELへ移る」で今回の`revc-c.uf2`をコピーする。
   再接続後に`C=0.5.0-alpha.1`、`audio_ready=1 fault=0`、
   `PIPELINE input=125 output=108 prime=2 nominal_delay_us=4500`と
   `RX qualify_ticks=2 pio_hz=32000000`を確認する。
2. FM100%（既定値）、「バスの待ち時間：短縮（標準）」で「組み込みBINを1回再生」。
3. 約4分58秒の終端まで再生し、聴感と最終`DONE`、`events=123137/123137`、`fault=0`、`gates=0`を確認する。
4. 停止したら再起動前にログを保存し、`FAIL`、`RXFAULT`と末尾の`STATUS/AUDIO/TIMING`を報告する。
   異常時は消音とリセットを維持する。保存後に再起動・旧版へ戻せる。

内蔵Ys IIの全曲確認はalpha.7でユーザー実機が1回完了している。同じ確認の再実行は不要。
今回のZIPには内蔵Ys IIを含めない。新I2C経路の受入は別途行う。
再現用の手順として残す。配線やGPIOの変更は不要。起動・接続では演奏しない。

### 引き続き使える診断記録

FM記録の開始31秒を選んで「FM診断を録る」と、先頭から演奏し、31～33秒付近の
生FMをRAMへ記録して自動停止する。「診断データを保存」で`.rcd`を保存できる。
短いDMA125フレームを5個ずつまとめて、既存RCD1の625フレーム単位へ格納する。
形式・固定ファイルサイズ・オフライン解析ツールは従来のまま。記録中のFMゲインは固定。
[診断形式と解析方法](diagnostic-format.md)を参照。楽曲を含む生成物はGit管理外へ置く。
今回の立ち上がり比較には通常の組み込みBIN再生を使う。
画面はalpha.1～alpha.6にも接続でき、診断操作はalpha.4以降で有効。

## 最短の実機確認

曲入りのローカルテストZIPにも、著作物を含まない13秒の音声経路テストが内蔵されている。
UF2を1回書き込み、まず`test`、次に`play`を行えばよい。

1. 旧ファームウェアを停止・バックアップし、Pico USBとJPOWERを外す。
   操作側I2Cも外す。BOOTSELを押しながらPicoのデータ用USBをPCへ接続する。
2. BOOTSELのUSBドライブが現れたらBOOTSELを離し、**JPOWERへ外部5 Vを供給してから**
   ZIP内の`revc-c.uf2`をドライブへコピーする。再起動後に音源を初期化する。
   ブートローダー待機中のARMは基板のプルダウンで無効。
3. ZIPを展開し、そのフォルダーでローカルサーバーを起動する。
   `python3 -m http.server 8766 --bind 127.0.0.1`
   Windowsでpython3がない場合は`py -m http.server`に同じ引数を渡す。
   `http://127.0.0.1:8766/pc/revc-console.html`を開く。
   ソースツリーの`firmware-c/pc`を配信する場合はURL末尾は`/revc-console.html`。
4. 「Rev Cへ接続」を押し、**YM2203 Rev C C firmware**のシリアルポートを選ぶ。
   MIDIのページではなくC版のページを使う。画面の状態取得で
   `C=0.5.0-alpha.1 audio_ready=1 fault=0`を確認する。
5. 「音声経路テスト（13秒）」を1回押す。順に以下を左右で確認する。
   - FMだけでドレミファソファミレド（各音約400 ms、約100 msの隙間）。
   - SSGだけで同じ音階。
   - FM3声＋SSG3声の和音を約2秒、その後無音。
   - 最後に`DONE`、`events=191/191`、`gates=0`、`fault=0`。
6. 上記が正常なら「組み込みBINを1回再生」を押す。
   Ys II用UF2は`SONG events=123137 period_ms=298218`。
   約4分58秒の先頭～終端を1回演奏し、追加500 msの末尾待ちを含んで消音する。
   通常の画面切り替えでは継続する。最後に`DONE`、`events=123137/123137`、
   `gates=0`、`fault=0`を確認し、画面の「ログを保存」を押す。
7. 必要に応じて再生途中の「全音停止」も1回確認する。音が消え、明示的な次の再生まで戻らない。
   「組み込みBINを1回再生」は必ず先頭から再開する。

報告する内容：音声経路テストのFM/SSG/和音、Ys IIの完走、左右、歪み・予定外の音切れ・
クリック、末尾消音、STOP、保存ログ。追加で既存診断をすべて繰り返す必要はない。
`TIMING`は**書込み開始時点の遅れ**で、BUSY/実書込みに要した時間は含まない。
ビンは1/5/10/20/100 ms未満、同時刻もファイル順に逐次実行する。初期化群も集計に含む。
`AUDIO blocks/peak/max_convert_us/queue_min/queue_max`も採取する。
FMの標準出力は旧版の8倍（約+18.06 dB）なので、最初は基板/AMS-22の全体音量を下げる。
右デジタルチャンネルはゼロ、実基板でモノラルを左右へ複製する。
「FM出力レベル」は100%が標準。0～200%を12.5%刻みで選べる。
12.5%は初版相当、0%はFMのみミュート。USBの`fm 0..16`は12.5%刻み、8=100%、16=200%。
100%超でPCM範囲を超える場合は符号反転させず飽和し、`LEVEL clipped_samples`へ出力サンプル数を加算する。
その飽和はFAULTとしない。値は再生開始でゼロへ戻り、STOP後も比較のため保持する。
SSGのデータはそのまま。演奏中の変更は5つの短いブロック（合計約11.25ms）で滑らかに追従し、
設定変更だけで再生しない。再生開始・STOP後も設定を保ち、再起動で100%へ戻る。
`STATUS`の`fm_gain_eighths`（0～16）で受理した値を確認する。
まず標準100%で曲の同じ部分を比較し、必要なら演奏中にFMレベルを調整して合わせる。
全曲を何度も再確認する必要はなく、修正後の音量比と歪み、必要なら保存ログを報告する。

外部5 Vを付け忘れた場合、無音のまま`fault=11`になることがある。
外部5 Vを確認して「Rev Cを再起動」を押す。ほかのFAILではログを保存し、繰り返し再生せず報告する。
復帰用の「BOOTSELへ移る」は消音・リセットしてUSBブートへ戻る。
旧版へ戻す場合は公式Pico 2 MicroPython 1.29.0 UF2を書き、保存した旧/lib/boot.py/main.pyを戻す。

## 構成と停止条件

- Core 0：USB CDC、WYM1の検査と実行時刻、YMの並列バス。
  コマンド入力は48文字・1ループ最大64バイト、ログは非ブロッキングで取りこぼし数を記録する。
- Core 1：PIO0 SM0でFMのSH/24ビットフレーム受信、DMA2本、125入力→108 PCM変換、
  PIO1 SM0で48 kHz/16-bit I2S送信、DMA2本。静的リング8ブロックを使用する。
  2ブロック蓄積後に出力開始。完了DMAは新しいPCMの発行を待って再設定し、
  待機中に同じ消費を重複計上しない。未発行スロットを指定しない。
  初期2ブロックは約4.5ms、リング全体は約18ms。FIFO/DACの遅延は別。
  `AUDIO blocks`は旧版の5倍の粒度、正常時のキュー下限は1程度にもなる。
  `fault=5/6`はTXの継続/発行条件不成立、`fault=7`はRX所有権不成立を示す。
  125:108線形補間と負数の切捨て方向を維持する。FMゲインは0～2倍、初期値unity。
  有効な13-bit浮動小数点入力の全範囲をsigned16-bit（-32768～32767）へ収める。
  unity以下では正常入力のデジタルクリッピングなし。unity超は飽和回数を記録する。
  旧版相当1/8設定でのPCMは従来の計算とビット一致を検証する。
- GPIO待ち時間は標準1/1/2µs、比較用の従来10/10/20µsも選べる。
  `bus fast` / `bus slow`は演奏停止中のみ受理し、再起動はfastへ戻る。
  YMのBUSYを読み、アドレスを保持して再試行する。`BUS max_call_us`は1回の呼出しの実測時間、
  `busy_retries`はBUSYで返った回数、`writes`は実行済みレジスタ数。成功したコール以外も時間計測する。
  1書込み/11.25 msというソフトウェア制限はない。1回のループで最大1イベントを実行する。
- 再生のたびに無音で音声DMAを停止・確認してYMをハードリセットし、音声バッファを作り直す。
  過去の音色や保留サンプルを次の曲へ持ち越さない。250 ms後を演奏開始時刻とする。
- PCMの異常値、PIO FIFO停止、DMAバス/所有権異常、50 ms FM無応答、
  100 msの音声ハートビート停止はLINE/DAC/ARM/RESETを閉じてFAULTへ移る。
  最初のFAULTコードを保持する。音声の異常停止後は再起動が必要。
- 演奏中にUSB CDCが閉じる/休止するか、USB SOFが250 ms進まないと消音・演奏中止。
  再接続だけでは再演奏しない。MIDIの物理USB切断時の消音とI2C演奏継続は実機受入済み。
  250 msという検出期限と実際の可聴遅延は、実機の時間測定で確認したものではない。
- レジスタ実行が100 ms超遅れると演奏を中止する。これは許容音質を100 msとする意味ではない。
  実際の遅れ分布を実機で測り、必要ならGPIO待ち・バースト処理を調整する。
- 変換比は125:108で固定。640入力ブロック（約1.44秒）ごとに外部FM入力の実周期を測り、
  I2Sを公称48 kHz近傍へ追従させる。Picoの整数タイマーと音源発振器の微差で
  キューが徐々に枯渇/あふれることを避ける。追従上限は公称の約±0.5%、
  分解能は150 MHz時に約80 ppm。`i2s_div256`に分周値を記録する。
  追従計算はモデル検証済みだが、実機でのドリフトと可聴影響、24時間動作、
  USB/電源ノイズ、実機音量バランスは別途測定する。WebLabの波形との同一性は保証しない。

## ビルド

本ディレクトリをカレントディレクトリにする。
SDK 2.2.0 / TinyUSB / picotool 2.2.0のコミットは`toolchain-lock.json`に固定。
試験済みArm GNUは10.3.1 20210824、ホストはCMake4.4.2/Python3.14.6。
固定Armツールチェーンは別途導入し、グローバル環境をこのスクリプトで変更しない。

```sh
python3 tools/setup_sdk.py
python3 tools/build.py --output ../outputs/revc-c-demo.zip
# 個人のローカルテスト専用。データと生成物はGit管理外。
python3 tools/build.py --song ../local-test-data/ym2203/ysii/song.bin --output ../outputs/revc-c-ysii-local.zip
```

曲データはC配列として**フラッシュへ配置**する。RAMへ全曲を展開しない。
ビルド時/起動時にWYM1を検査し、CRC32・SHA-256で元データを照合する。
生のWYM1の全バイトを保持し、イベントの間引き・時刻の付け替え・順序の変更はしない。
曲入りUF2/ZIPはローカル再生テスト用で、GitやGitHub Releaseへ公開しない。
`build-manifest.json`は入力SHA/CRC/件数、UF2ハッシュ、ツールチェーン、メモリ使用量を含む。
SDKキャッシュ・中間生成物・ZIPはプロジェクトの`.cache/`と`outputs/`へ置く。

```sh
python3 -m unittest discover -s tests -v
python3 tools/generate_midi_pitches.py --check
python3 tools/verify_usb_descriptors.py --sdk ../.cache/pico-sdk-2.2.0
# 元データは手元にあるときだけ指定：
REVC_TEST_SONG=../local-test-data/ym2203/ysii/song.bin python3 -m unittest discover -s tests -v
../scripts/use-node.sh node verify-console.mjs
../scripts/use-node.sh node verify-midi-ui.mjs
```

C本体のパーサー・レジスタ許可表・スケジューラ・PCM変換をホストでコンパイルして検証する。
`board.c`の実コードもGPIO/BUSYの時刻モデルでコンパイルし、両モードのアクセス順、
BUSY中の保留、信号段階1µs以上、読み戻し・停止を検証する。これは電気的実測ではない。
全曲テストの20/250/400 µs書込みモデルは負荷条件の仮定であり、実機測定ではない。
PIOテストは実際のプログラムの命令/side-setを解釈し、I2Sの1ビット遅れと左右配置を検証する。
ブラウザーテストは模擬Web Serialのみ。クロスビルドやモデル試験から実機合格を推定しない。

## 診断コードの所有権と検証

`diagnostic.c`の固定バッファをCore0のトレースとCore1の生信号で分けて書く。
演奏リセット時の音声コア停止中だけバッファを初期化し、armをrelease/acquireで公開する。
ライブDMA125フレームを5回ずつ論理625フレームへ連結する。
Core1完了→Core0 seal後は全体を不変にしてCRC32とUSB転送へ渡す。
STOP/通信断は未完了のarmを取り消し、完了処理が後から記録を復活させない。
診断中に通常`play/test`を開始すると古い記録を破棄し、通常の再生を先頭から開始する。
起動・接続だけでは記録・再生・ダウンロードしない。

ホストC試験はレイアウト/ビット順、容量、時刻ラップ、途中中止、書き込み順、
デコード/PCM生成を検証する。模擬Web Serialで分割受信、明示保存、サイズ・CRC異常の
拒否、旧版の操作無効化を確認する。これらは実機の音質や負荷を保証する試験ではない。

## 次の段階

C版で実機の音声経路・Ys II全曲処理が成立したら、100/400 kHz候補の高速I2C、
ブロック転送・先読み・不足時停止・ホストライブラリは0.4版、USB-MIDIは0.5版へ移植した。
現行v1 I2Cのコマンドを黙って別形式に置換しない。

0.5.0-alpha.3のMIDI/I2C切替、MIDIのUSB喪失時停止、USB切断をまたぐI2C診断、
再接続後の無音と明示的MIDI復帰までの初期受入を完了した。
次は[常用手順](DAILY-USE-README.txt)のセットを使用できる。UF2は確認済みと同一バイトで再ビルドしない。
現行C0.5 alpha3での全曲実機受入もユーザーの数値報告で完了。旧C0.4 alpha2の生ログ照合とは
根拠の種類を区別し、現行版の未提示ログ・未実測項目はvalidation.jsonへ残す。
追加機能や長時間試験はこの受入のために増やさず、別の目的・仕様として扱う。

## ライセンスと一次資料

自作部分はプロジェクトのMIT。I2S PIOはRaspberry PiのBSD-3-Clauseプログラムを改変し、
開始位置を左チャンネルに合わせた。`THIRD_PARTY_LICENSES.txt`を参照。
配布ZIPにはSDK/TinyUSB/CMSIS/Armツールチェーン等のライセンスを同梱する。
USB IDはPico SDKのRP2350 CDC用試作識別子（2e8a:0009）を使う。

- https://github.com/raspberrypi/pico-sdk/tree/2.2.0
- https://github.com/raspberrypi/picotool/tree/2.2.0
- https://www.raspberrypi.com/documentation/pico-sdk/hardware.html
- https://github.com/raspberrypi/pico-extras/blob/master/src/rp2_common/pico_audio_i2s/audio_i2s.pio
- https://developer.chrome.com/docs/capabilities/serial

バス待ち時間の一次資料：
[Yamaha YM2203 Nov1989,p9](https://bitsavers.trailing-edge.com/components/yamaha/YM2203_198911.pdf)。
復号照合先：[WebLab採用ymfmのencode_fp/decode_fp](https://github.com/aaronsgiles/ymfm/blob/81aec25ccbb98f4873a255f7551ac4dadac59b4a/src/ymfm.h)。

## 受信の検証範囲

実際のPIOソースのWAIT、JMP、IN、遅延、IRQ、24ビット自動PUSHをモデル化する。
正常入力で24通りの位相・0～3サイクルのSD安定遅延、2フレームの全ビット位相で
幅1～2サイクルのhigh/lowへの揺れを検査する。以前のサンプル待ちだけのコードで
ユーザーと同じ異常値が出て、新受信では元の仮定値を保つ回帰試験を含む。
指数0そのものを正当なサンプルとして送った場合は、そのまま変換失敗になる。
実基板のCLK/SDの伝搬時間、SHの揺れや長い揺れは測定・保証していない。
一次資料：[Yamaha YM2203 Nov1989 p10～11](https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf)、
[Yamaha YM3014B Mar1994 p3](https://www.bitsavers.org/components/yamaha/YM3014B_199403.pdf)。
資料やモデルだけで実機の異常発生段階を確定しない。


## I2C版のビルドと検証

ファームウェアと操作側データを分けてパッケージ化する。`--host-song`はUF2へ埋め込まず、
ローカルZIP内`host/music/song.bin`へ原本どおりコピーする。旧`--song`は内蔵再生用として維持する。

```sh
python3 tools/build.py --host-song ../local-test-data/ym2203/ysii/song.bin --output ../outputs/revc-c-i2c-ysii-local.zip
REVC_TEST_SONG=../local-test-data/ym2203/ysii/song.bin python3 -m unittest discover -s tests -v
python3 tools/verify_host_micropython.py --micropython /path/to/micropython --song ../local-test-data/ym2203/ysii/song.bin
```

Cプロトコル/キュー/CRC/時刻/リースと実際のPythonホストを接続し、100kHz wire・YM50µsサービスの
モデルで全123,137件の値・順序とCRCを検査する。転送間隔やACK再送は演奏時計を動かさない。
I2C SDKアダプタはモックFIFOへ接続し、同一IRQでFINISHがRX_FULLに先行する場合の末尾取込みを検査する。
別途、実際のMicroPython v1.29 Unix版でも同じホストをCモデルへ接続して検証する。
Unix検証用ビルドはminimal variantのROMレベルをEXTRA_FEATURESへ変更し、thread有効、
`MICROPY_PY_BUILTINS_INPUT=0`、`MICROPY_DEBUG_PRINTERS=1`としたローカル専用構成。
RP2のピン・割込み・SCL/SDA電気特性やMicroPythonの実機速度を検証したとは扱わない。

I2C v2のリングは8192バイト、固定要求FIFO4件と64バイト状態を用いる。
既存の固定RCD1領域と合計してもRP2350 SRAM内に収まり、リンク時とパッケージ時にサイズを検査する。
初期化/STOPのGPIO処理以外の演奏中YM書込みは1回/ループで、ISRでは実行しない。
SDK2.2.0のpico_i2c_slaveを新たにリンクするが、SDK版・コミットは変更しない。
追加のBSD-3-Clause帰属は[LICENSE-PICO-I2C-SLAVE.txt](LICENSE-PICO-I2C-SLAVE.txt)に保持する。
