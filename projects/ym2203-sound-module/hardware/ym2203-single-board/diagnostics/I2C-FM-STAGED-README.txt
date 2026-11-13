YM2203C Rev C - 段階起動によるI2C + live FM/SSG診断 v1.3
2026-11-11

目的と根拠
----------
直前の無音段階診断v1は実機でPHASE 0～5すべてPASS、HOST PASS・SAFE/DONEまで完走しました。
各段階の受信173/送信458、保護書き込み無視1、stale flush 0が一致しました。
FM事前検査はピーク4064、56ブロック、最大変換1111us、期限超過0でした。
I2C設定は全段階で[804,66,1,1,0,6,16,90,90]、GP20/21のFUNCSELは3、入力ビットは3でした。
GP10/11/12はI2S動作中のみFUNCSEL=6、停止後は5でした。
I2S起動や事前変換が必ずI2Cを壊すという結果ではありません。
ただし、以前のFM/I2C v1.1が最初の書き込みでEIOとなった直接原因は未確定です。
段階ごとのI2C初期化と通信実績を経る順序が、結果に影響する可能性を調べます。

今回は成功した段階診断の起動順を踏襲し、最後の段階をSSGミキサーの無音設定へ変えて、
資源を保持したまま既存の連続FM変換とI2C発音制御へ進みます。
既知のEIOを修正できたと断定するものではありません。

v1.2の同時動作試験では、全起動段階と連続受信開始前後の通信検査が通り、途中まで音が出ました。
区間3のKEEP応答待ちでHOSTがタイムアウトし、最後の応答はb'@\x06\x00\x01'でした。
Rev CはCtrl+Cまで7453ブロック変換を継続し、ピーク4064、max_poll_us=7323、
命令65、期限消音1回、受信286/送信628、stale flush 0。最後の状態はb'A\x06\x00\x01'でした。
HOST全体の書き込み1324-前半173*6=286、読み取り3376-前半458*6=628で、両側の転送数は一致します。
I2Cの全バイト数が一致しても、各データ内容や実行タイミングまで正常と断定するものではありません。

ターゲットは約11.25msごとにI2Cを処理し、命令はスレーブFSMのIDLE時に確定します。
HOSTの状態確認の間隔が10msだと、STOP後の短いIDLE期間を毎回捉え損ね、
命令が保留されるケースがあります。以前のモデルはSTOP直後にpollを呼ぶため、この条件を隠していました。
独立した11.25ms周期でpollするモデルで、KEEPが保留され、ACK64のまま期限消音し、
HOST停止後にACK65へ進む同じ状態を再現しました。これはソフトウェア上の待ち合わせの欠陥です。
実機の全経過を波形で確認したわけではなく、今回の症状すべての原因と確定したものではありません。
v1.3はFM用HOSTの命令送信後と状態確認の間隔を40msにし、3ブロック以上のIDLE時間を設けます。
同じモデルは修正前に失敗し、修正後は9区間と意図的な最終期限消音まで通りました。
1秒のリースと応答タイムアウト、音声変換の期限監視は変更しません。
v1.3は実機で9区間すべて正常、左右正常・歪み/音切れなし・最後の自動消音、HOST PASS・SAFE/DONEまで合格しました。
2478ブロック、ピーク4064、最大変換1118us、期限超過0、max_poll_us=7502、確認カウンター111、期限消音1回。
受信407/送信744はHOSTから前半6段階分を引いた数と一致し、stale flush 0。
次はI2C-ENDURANCE-README.txtの3分間の2音+I2C KEEP耐久診断です。既存ターゲットをそのまま使います。

1. 配線とファイル
-----------------
配線・給電・GPIOは直前の成功した段階診断と同じです。
  Rev C JHOST 1 GND -> 操作側Pico GND（物理3番など）
  Rev C JHOST 2 SDA -> 操作側GP0（物理1番）
  Rev C JHOST 3 SCL -> 操作側GP1（物理2番）
  JHOST 4もGND、3本配線では未接続でよい。
操作側ハードウェアI2C0、10kHz、7bitアドレス0x42、信号3.3V。
Rev CのR1/R2各4.7kΩプルアップを使用。電源線同士はつなぎません。
配線変更時は両基板の電源OFF、テスト中は両方に給電します。
JLINE -> AMS-22 LINE IN、ヘッドホン -> AMS-22。
AMS-22は別バッテリー給電、PCとのUSBは外し、DIRECT MONITOR=ON、LOOPBACK=OFF。
両方のボリュームを低めにしてください。後半では音が出ます。

前回のv1.2一式を導入済みの場合、今回は操作側のhost/内5ファイルの上書きで再試験できます。
Rev C側はv1.2のまま実行できます。ターゲットのコードはバナー以外、前回と同一です。
一式を入れ直す場合のために、ZIPには両側の全依存ファイルも含めます。
Rev C側を入れ直す場合、target/からPicoの最上位へ次の11ファイルを保存します。
  rev_c_bus_check.py
  rev_c_fm_capture.py
  rev_c_dac_check.py
  rev_c_fm_live.py
  rev_c_fm_ssg_check.py
  rev_c_ssg_check.py
  rev_c_i2c_target_check.py
  rev_c_i2c_ssg_target.py
  rev_c_i2c_fm_target.py
  rev_c_i2c_isolation_target.py
  rev_c_i2c_fm_staged_target.py
ZIPのhost/から操作側Picoの最上位へ5ファイルすべてを保存します。
  rev_c_i2c_host_check.py
  rev_c_i2c_ssg_host.py
  rev_c_i2c_fm_host.py
  rev_c_i2c_isolation_host.py
  rev_c_i2c_fm_staged_host.py
HOSTは実行ファイルだけでなく共通ファイルも更新しています。host/の全5ファイルを上書きします。
main.py / boot.pyには保存しません。UF2の書き直しは不要です。

2. 実行
-------
1) 両側を停止して転送後、両方のPico USBとJPOWERをすべて外し、5秒待ちます。
2) JPOWER -> 両方のPico USBの順で接続し、2つのThonnyをそれぞれのPicoへ再接続します。
3) Rev C側でrev_c_i2c_fm_staged_target.pyを実行します。
   YM2203 Rev C / staged I2C + live FM mixer target v1.3
   （前回のRev C側を継続利用する場合、この行はv1.2のままで正常です。）
   PHASE 0 READY / BUS ONLY / address=0x42
   が出るまで待ちます。
4) 操作側でrev_c_i2c_fm_staged_host.pyを実行します。
   YM2203 Rev C / staged I2C + live FM mixer HOST v1.3 / OTHER Pico only
5) 以後は自動です。6段階の無音検査、連続受信開始前後の通信検査に通った後、
   5秒待って9区間の発音を行います。全体は約1分が目安です。

前半の段階0～4は、バスのみ -> FMレジスタ -> 受信PIO/DMA確保 -> I2S起動 -> 無音FM事前検査後。
段階ごとにI2Cを設定し直し、32回の識別情報読み取り、4種類の32バイトRAM検査、書き込み保護を確認します。
前回と異なり、段階5はSSG MIXER PREPAREDです。SSG Aの約220Hzを設定し、音量を0に戻します。
出力ゲートは低いままです。ここではYMをリセットせず、I2Sも終了しません。
直前の無音専用診断での段階5「I2S CLOSED」と混同しないでください。

段階5のPASS後は、連続発音制御用I2Cへ切り替えます。HOSTは3秒待ってから自動で続行します。
  Rev C: STARTUP PASS: six silent I2C phases; preparing live-control READY
         READY: I2C enabled, FM capture STOPPED ...
  HOST:  LIVE ACK: idle gap=40 ms; lease and acknowledgement timeouts remain 1000 ms
         PASS: initial I2C checks while FM capture STOPPED
         PASS: live capture START acknowledged
         PASS: 8 stable reads + 8 KEEP commands with FM capture running
ここまで通ってから発音します。受信開始後、Rev Cは途中の進捗をUSBへ出しません。
LIVE ACKが40msであることを確認してください。古い共通HOSTファイルを検出した場合は発音前に停止します。
後半の識別情報はRCMIX02!、前半はRCISO01!です。古い単独HOSTは今回の後半まで進みません。

3. 九つの発音比較
-----------------
左右へ同じモノラル音を出します。区間は各約2秒、1と2の後に約1秒のSTOPがあります。
  1 FM ONLY       高い約440HzのFMだけ
  2 SSG ONLY      低い約220HzのSSG Aだけ
  3 FM + SSG      両方
  4 DAC MUTE      低いSSGだけ残る
  5 DAC RESTORE   両方へ戻る
  6 LINE MUTE     両方消える
  7 LINE RESTORE  両方へ戻る
  8 STOP          約2秒の無音
  9 LEASE         両方を鳴らし、KEEPを止めて約1秒で自動消音
背景の小さなサー音と、テスト音の有無は分けて確認してください。
切り替え時にはI2CとI2Sのバッファによる短い遅延があります。

4. 報告
-------
両側のログ全文と、9区間の聞こえ方、独立ミュート、最後の自動消音、左右、歪み/音切れを報告してください。
正常終了の末尾:
  HOST: HOST PASS: concurrent live FM/I2C commands, independent mutes and lease mute verified.
        HOST SAFE ...
  Rev C: LIVE I2C: live_started=1 blocks=... lease_expirations=1 ...
         I2C CONFIG BEFORE LIVE / AFTER LIVE ...
         PASS: live sequence sent; max conversion=... us, deadline misses=0
         SAFE ... capture/I2S/I2C=stopped
         DONE: staged live FM/I2C check complete ...

失敗時はHOSTのエラー末尾まで保存し、Rev CもCtrl+Cで止めてLAST PHASEまたはLIVE I2C、
設定配列、SAFEと例外末尾まで保存します。どのPHASE/どのPASSまで進んだかが重要です。
live-control after phase=5という表示は、無音段階を終えた後の連続制御中の失敗を意味します。
HOSTの該当PHASE CHECKがRev CのREADYより先だった場合は、その順序も報告してください。
段階間の3秒を初期化が超えた可能性を区別するためです。

5. 変更と検証の限界
-------------------
共通の段階ランナーに、音源/資源生成、段階名、完了後の処理を指定する診断用引数を追加しました。
指定しない無音専用診断の動作は従来どおりです。
後半は既存のControlTarget、命令・通信期限、HOST手順を利用します。
SSG設定済みで呼べる引数を追加し、段階5後に同じSSG設定を繰り返しません。
受信・I2Sを保持し、連続変換は後半のSTARTで1回だけ再開します。
ネイティブ変換、PIO、DMAリング、48kHz形式、音量上限、期限監視、共通I2C通信部は変更しません。
GCは有効、明示的GCとUSB出力は受信停止中のみ、異常時は出力を止めて解放します。
GPIOや回路は変更していません。

v1.3では、共通HOSTの待ち時間をクラス属性にし、SSG専用の既定10msを維持してFM用だけ40msにします。
応答タイムアウトのエラーには、前回ACK・送信命令・期待モード・最後の応答も表示します。
Rev C側の処理はv1.2から変更せず、起動バナーのみv1.3へ更新しています。
この40msは音声ブロック間でポーリングする組立診断用の調整です。将来のIRQ処理等に基づく正式APIの制約ではありません。

PCの128項目（今回の待ち合わせ追加4項目）で、起動順、段階5でI2Sを閉じないこと、
各モード/ミュート/期限消音、SSG設定が1回であること、例外時の消音と共通資源の解放を検査します。
STOP直後に強制的にpollを呼ばないモデルで、10ms時の保留・期限消音と40ms時の回避、
同じ待ち合わせを通したHOSTの全9区間、古い共通HOSTの検出も検査します。
MicroPython WASMでは実際の前半/後半HOSTの連続処理を、模擬通信・時計・音源で実行します。
公式MicroPython v1.29.0 mpy-crossで変更/追加した4ファイルをArm向けにコンパイルします。
v1.2は途中の発音まで報告されましたが、9区間完走と音質の検証は未完了です。
v1.3の9区間は上記のとおり実機確認済みですが、以前の初回EIOの原因も確定したとは扱いません。
診断専用で、正式なAPI、予約演奏、USB-MIDI、長時間運転は今回含みません。
  python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
  ./scripts/use-node.sh node hardware/ym2203-single-board/diagnostics/verify_fm_capture_micropython.mjs
検証ログとvalidation.jsonのSHA-256一覧を同梱します。配布物はPythonソースです。
scheduling-before-fix.txtは修正前の回帰テスト失敗記録です。実機ログではありません。

スレーブFSMのIDLE状態の一次資料:
https://github.com/raspberrypi/pico-sdk/blob/2.2.0/src/rp2350/hardware_regs/include/hardware/regs/i2c.h
