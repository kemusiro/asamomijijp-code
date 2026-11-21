# YM2203C専用・1枚基板 Rev C

電源専用USB Type-Cからの5Vで動作する、Pico 2 ×1・YM2203C ×1の試作設計。
入力は3.3V I2CとUSB-MIDI、出力はFM＋SSGを合成したモノラルを左右へ複製するライン出力。
AMS-22の3.5mmステレオLINE INへ取り込む。
GPIOは2026-10-18に確認・承認済み。旧 `sound-module-pcb/` の2枚版とは部品番号・配線が異なる。

**最終目標は、WebLabと同じYs IIの全曲データをRev C実機で演奏すること。**
組立・I2C/USB-MIDI初期受入は完了したが、Ys IIの実機再生はこれから。
手元のBINは平均約413書込み/秒で、現行音源側約89回/秒、HOSTの40 ms ACK待ち、
検証用10 kHz I2Cでは不足する。[性能分析とC SDK版への移行方針](firmware/YSII-PLAYBACK-PLAN.md)を参照。

**組立・I2C実現性確認は完了。常用ファームウェア初版を実装。**
2026-11-13、休符中STOP/4秒無音/再演奏/通信期限消音の最終総合試験までユーザー実機で合格。
[常用ファームウェア0.2.0-alpha.1](firmware/README.txt)は自動起動、バージョン付きI2C API、
補充式キュー、ホストライブラリを実装した。alpha.2の基本サンプル2回再生は実機で合格。
alpha.1の実機サンプルで発生したcode7は、I2C通信中に予約書き込みが待たされる
不具合としてモデル再現し、alpha.2で修正した。ユーザーが休符・伴奏・終了後消音、
左右正常、歪み/音切れなしを確認した。
[3分間の補充式再生](firmware/STREAM-3MIN-README.txt)も実機で完走し、
休符・伴奏・終了後消音、左右正常、歪み/予定外の音切れなし、HOST PASS・DONEを確認した。
[停止・通信復帰](firmware/RECOVERY-FINAL-README.txt)も全4区間実機合格。常用I2C版の受入は完了。
[USB-MIDI初版](firmware/USB-MIDI-README.txt)を実装し、CDC保持・6声割り当て・I2Cとの制御権を追加した。
USB-MIDIデバイス認識、FM/SSG音階、全音停止、左右正常、歪み/音切れなし、Thonny接続は実機で確認。
[6声・I2C切替](firmware/USB-MIDI-SIX-HANDOVER-README.txt)もユーザーから確認完了の報告があり、初期受入は完了。
今回の報告ではHOST全ログ・OS名・期限超過回数は未提示。物理USB切断、遅延測定、24時間運転は未確認。
以下は組立・診断の履歴であり、当時の未確認記述も保存する。

2026-11-11時点で組立個体の静的な電圧・クロック確認、SSGレジスタの読み書き、
SSG A/B/Cの計6回の発音とAMS-22経由の左右出力を確認。
チリチリ音はAMS-22を別バッテリーで給電してPCとのUSBを外すと消え、
外部給電を保ってPCへ再接続すると小さくなるものの戻ると報告された。
USB/GND経路の関与が疑われ、USB絶縁対策は別途行う。小さなサー音はLINEを外してもほぼ不変。
DAC単独診断でも、1kHzの3回の発音・左右出力とDAC MUTE/LINE MUTEの消音が実機で確認された。
無音FM受信診断v1.1で、CLK約1.333MHz・SH約55.556kHz・24クロック/フレーム、
キーオフ時0x0600固定、キーオン時217種類のデータをユーザー実機で確認した。
v1でのarray乗算による初期化エラーはv1.1で修正済み。
受信FM波形の復号・1周期のDAC再生も、3回の左右出力・ミュート・歪みなしをユーザー実機で確認。
入力PCM範囲-127～127、推定439.87Hz、再生440.37Hzと報告された。
連続FM診断v1.1も、音階2回の左右発音・音切れと歪みなし・SAFE/DONEまで実機で完走した。
最大変換時間1123µs、期限超過0、事前検査の空きメモリ419040バイトと報告された。
v1のGC停止と大整数演算によるMemoryErrorはv1.1で修正済み。
FM/SSG混合診断の9区間も左右正常、DACミュートでSSGのみ残り、LINEミュートで全消音、
合成時の歪み・音切れなし、SAFE/DONEまで実機で確認された。
最大変換1114µs、期限超過0、空きメモリ415712バイトと報告された。
FM各チャンネルとFM3音+SSG3音の診断も全10区間が左右正常、独立ミュート、
歪み・音切れなし、SAFE/DONEまで実機で確認された。
各FMピーク992、3音合成2976、最大変換1117µs、期限超過0、空きメモリ409280バイト。
4オペレーターFM音色診断の6区間も、音色の変化、発音中のTL/MULTI変更、
2回の減衰と再発音、左右正常・歪み/音切れなし、SAFE/DONEまで実機で確認された。
最大変換1115µs、期限超過0、事前検査ピーク4064、空きメモリ410736バイト。
連続運転診断v1は、開始直後のGC/メモリ計測とUSBログ出力付近で期限超過し、SAFE停止した。
その時の空きメモリ407344バイトであり、メモリ不足のエラーではない。
v1.1では明示的GC・メモリ計測・ログ出力を受信停止中へ移し、演奏中は固定6件の
時刻/ピーク記録のみ行う。GCは有効のまま、既存の期限・DMA・音量監視は維持する。
v1.1は実機で180000ms・16000ブロックを完走し、左右正常、音切れ/歪みなし、終了時消音とSAFE/DONEを確認。
最大変換1119µs、期限超過0、FMピーク2976。GC後の空きメモリは前後とも406960バイトで差0。
停止中のGC/メモリ計測時間は20281/20804µs。24時間運転や演奏中の最大メモリ使用量は未確認。
外部Picoからの無音I2C診断は、10kHz・0x42で実機合格。識別情報、22パターン、繰り返しSTART、
読み取り専用保護とアドレス周回、無音、HOST PASSとSAFE/DONEまで確認した。
ターゲット受信755・送信730・保護書き込み無視1・stale flush 0は想定どおり。
外部I2CコマンドによるSSG発音・消音診断の経過は `diagnostics/I2C-SSG-README.txt` に記録する。
I2C SSG診断v1の初回実機試験では、HOSTが6音目へ進んだ後にターゲットがTX abort 0x5000でSAFE停止した。
このv1試験は未完了。0x5000はターゲット送信中のSDA不一致/調停喪失を示す。
v1.1ではRP2350資料12.2.10.1.2に合わせ、送信データをFIFOへ入れてからRD_REQを解除する順へ修正。
旧通信ファイルの混在を検出し、0x5000を含むハードエラー時の消音停止は維持する。
v1.1の再試験は通常6音分のSTOP応答まで進み、7音目の開始コマンドでb'%\xff\xff\xff'を受信してHOST停止。
ターゲットはREADYのまま待機し、完走していない。実際の音の確認もこの報告からは判断しない。
v1.2は操作側を同じGP0/1・10kHzのハードウェアI2C0に切り替える切り分け用診断。
発音前の64回の状態読み取り・32回の消音中コマンド検査、HOSTの転送数と最後の応答、
Rev Cの例外/Ctrl+C時にも最後の制御状態を表示する機能を加える。ターゲット通信部はv1.1のまま。
v1.2は実機で通常6音と約1秒で自動消音する7音目を左右で確認し、歪み/音切れなし、終了時消音、HOST PASSとSAFE/DONEまで合格。
受信390/送信700バイトはHOSTと一致、制御命令108、通知期限消音1回、stale flush 0。
ハードウェアI2C経路での合格であり、以前のSoftI2Cでのエラー原因は確定していない。
次段階は `diagnostics/I2C-FM-README.txt` のFM連続変換と外部I2C制御の同時動作診断。
固定音程・音量のFM/SSG、独立ミュート、通信途絶時消音を音声ブロック間で操作する。
同時動作v1はHOSTの最初の書き込みでEIOとなり、発音命令まで到達しなかった。
Rev Cの停止時は2757ブロック・受信0・送信0・命令0。原因は未確定で、アドレスNACKと断定しない。
v1.1ではREADY前にI2Cを有効化し、受信停止中の通信検査後、HOSTのSTARTで連続FM受信を開始する。
開始後も無音で通信を再検査し、I2C設定とGP20/21のFUNCSELを前後で検査・記録する。
READY表示時にI2Cがまだ無効だったv1の順序不備は回帰テストで検出したが、実機エラーとの因果は未確認。
GPIO・回路・受信/変換のネイティブ処理・期限監視は変更しない。
v1.1の実機再試験もHOST最初の1バイト書き込みでEIOとなった。
BEFORE LIVE=[804, 66, 1, 1, 0, 3, 3, 3]は期待値と一致したが、識別情報読み取りとSTARTへは未到達。
この開始前の失敗は連続受信中の処理遅延だけでは説明できない。事前検査やI2S初期化の影響は未除外。
v1.1停止時の追加ログはlive_started=0、blocks=0、受信0/送信0、命令0、max_idle_poll_us=186。
既知の成功版SSG v1.2を同じ配線で両側Ctrl+D後に再試験しても、HOST最初の書き込みでEIOとなった。
その後、接続先確認・完全な電源再投入を案内して行ったSSG v1.2再試験はEIOなしで完走し、発音が報告された。
HOST PASS、ターゲットSAFE/DONE、命令108、期限消音1回、受信390/送信700の両側一致、stale flush 0を再確認。
復旧の直接原因は未確定で、リセットをまたぐ状態や接続/給電のどれかとは断定しない。
次はFM/I2C v1.1の全ファイルを両側へ戻し、転送後に両基板を完全に電源再投入して同時動作を再試験する。
この手順でFM/I2C v1.1へ戻した再試験も、設定値は同じでHOST最初の書き込みがEIOとなった。
SSG版の復旧後にFM版で症状が再現したため、追加した資源初期化を調べる。最新再試験の停止時統計は未報告。
次は `diagnostics/I2C-ISOLATION-README.txt` の無音段階診断で、バスのみ、FM設定、受信資源確保、
I2S起動、無音FM事前検査後、YMリセット/I2S停止後の6段階ごとにI2C通信を検査する。
共通通信処理とネイティブ音声処理は維持し、全段階でLINE/DACを許可しない。
段階診断v1は実機で全6段階PASS、HOST PASS・SAFE/DONEまで完走した。
各段階で受信173/送信458、保護書き込み無視1、stale flush 0。
FM事前検査はピーク4064、56ブロック、最大変換1111us、期限超過0。
全段階のI2C CONFIG=[804,66,1,1,0,6,16,90,90]、GP20/21のFUNCSEL=3、入力ビット3。
I2S動作中のGP10/11/12はFUNCSEL=6、停止後は5。事前検査後にも通信が通ったが、以前のEIO原因は未確定。
次は `diagnostics/I2C-FM-STAGED-README.txt` の段階起動FM/I2C v1.2。
成功した起動順を踏襲し、段階5をSSG無音設定へ変更してI2S/受信資源を保持し、既存のライブ制御へ接続する。
新しい同時動作の実機結果は未確認。共通I2C、ネイティブ変換、GPIOと期限監視は維持する。
段階起動v1.2は全起動段階と受信開始前後の通信検査に成功し、途中まで発音した。
区間3のKEEP応答待ちでHOSTがタイムアウト。HOST最後の応答はACK64/KEEP/モード0/期限フラグ1。
Rev CはCtrl+Cまで7453ブロック変換を継続し、ピーク4064、max_poll_us=7323、命令65、期限消音1回。
ターゲット受信286/送信628は、HOST全体1324/3376から起動段階1038/2748を引いた数と一致した。
ターゲット最終ACKは65。初回EIOではなく、命令確定待ちと期限消音の症状となった。
独立した11.25ms周期のモデルで、HOSTの10ms状態確認がIDLEを隠し、KEEPを保留させるケースを再現した。
モデルはACK64で期限消音しHOST停止後ACK65へ進む。同モデルは修正前に失敗し、40msでは全9区間まで通る。
次のv1.3はFM用HOSTの待ち時間だけ40msへ調整し、ターゲット処理・1秒のリース・音声の期限監視を維持する。
この調整の実機効果と、以前のEIOの直接原因は未確認。手順は `diagnostics/I2C-FM-STAGED-README.txt`。
v1.3は実機で9区間の発音・独立ミュート・最終自動消音、左右正常、歪み/音切れなし、HOST PASS・SAFE/DONEまで合格した。
2478ブロック、ピーク4064、最大変換1118us、期限超過0、max_poll_us=7502、確認カウンター111、期限消音1回。
ターゲット受信407/送信744はHOST全体1445/3492から起動段階1038/2748を引いた数と一致し、stale flush 0。
40msへの調整後に同時動作が完走した結果を記録するが、以前の初回EIOの原因までは確定しない。
次は `diagnostics/I2C-ENDURANCE-README.txt` の3分間の2音+I2C KEEP耐久診断。
既存v1.3ターゲットと全ヘルパーを維持し、新しい操作側スクリプトで連続音とACK周回、最後の期限消音を検査する。
3分の同時通信耐久試験は実機合格。主試験180045ms、KEEP 640回、ACK周回2回、HOST最大応答確認92ms。
左右正常、歪み/音切れなし、最終自動消音とHOST PASS・SAFE/DONEまで確認。
16854ブロック、ピーク4064、最大変換1118us、期限超過0、max_poll_us=11796、stale flush 0。
ターゲット受信2135/送信3048はHOST全体3173/5796から起動段階分を引いた数と一致し、最終ACK175も一致した。
次は `diagnostics/I2C-CYCLE-README.txt` の80区間の発音モード/独立ミュート切り替え反復診断。
新HOSTファイルだけを追加し、既存ターゲットv1.3、音量、40ms待ちと1秒リース、期限監視は維持する。
反復診断は実機で10周・80区間すべて合格。左右正常、歪み/予定外の音切れ/気になるクリック音なし。
主試験180388ms、640命令、ACK周回2回、最大モード応答確認91ms、最終自動消音とHOST PASS・SAFE/DONEを確認。
16780ブロック、ピーク4064、最大変換1118us、期限超過0、max_poll_us=8164、期限消音1回、stale flush 0。
最終ACK173はHOST期待値と一致。受信2289=3327-1038、送信3680=6428-2748も整合した。
次は `diagnostics/I2C-PITCH-README.txt` のI2C音程制御診断。FM/SSG各2回の音階を演奏する。
5音固定の診断命令と専用シグネチャを追加し、共通ループにターゲット差し替え引数だけを追加する。
GPIO・ネイティブ変換・音量・40ms待機・1秒リースは維持する。
音程診断は2026-11-12に実機合格。FM/SSG各2回の全36音、左右正常、歪み/音切れ/気になるクリック音なし。
最後の自動消音、HOST PASS・SAFE/DONEまで確認。4197ブロック、ピーク4064、最大変換1120us、期限超過0。
max_poll_us=8623、max_idle_poll_us=354、期限消音1回、stale flush 0、最終ACK165はHOST期待値と一致。
受信719=HOST全体1757-起動1038、送信1878=4626-2748も整合した。
次は `diagnostics/I2C-TIMBRE-README.txt` の発音中I2C音色変更診断。
以前実機合格したローカル4オペレーター設定を用い、3モジュレーターのTL4段階/MULTI3段階をI2Cで選ぶ。
既存ソースは変更せず、専用バスとターゲット・HOSTを追加する。GPIO/ネイティブ変換/期限監視は維持する。
I2C音色変更は2026-11-12に全8区間が実機合格。TL/MULTIの音色変化と再発音、左右正常を確認。
歪み/音切れ/気になるクリック音なし、最後の自動消音とHOST PASS・SAFE/DONEまで確認。
2671ブロック、ピーク992、最大変換1118us、期限超過0、max_poll_us=7338、max_idle_poll_us=379。
期限消音1回、stale flush 0、最終ACK124はHOST期待値と一致。受信468=1506-1038、送信946=3694-2748も整合。
次は `diagnostics/I2C-COMBINED-README.txt` の音程/音色組み合わせ診断。
既存の5音とTL/MULTIだけを使い、キーを保持したまま異なる音色で4回のFM音階を演奏する。
既存ソースは変更せず、専用ターゲットとHOSTを追加する。
組み合わせ診断v1は実機で4回の音階/音色変化、左右正常、歪み/音切れ/気になるクリック音なし。
最後の自動消音とHOST PASS・SAFE/DONEまで確認。4109ブロック、ピーク992、最大変換1119us、期限超過0。
max_poll_us=7332、max_idle_poll_us=381、期限消音1回、stale flush 0、最終ACK165が一致。
受信722=1760-1038、送信2058=4806-2748も整合した。一方、演奏開始のCが長いと報告された。
HOSTが発音開始後に初期音色設定とCの重複設定を行う時間を、独立通信モデルと回帰テストで再現した。
`diagnostics/NOTE-START-README.txt` のHOST v1.1では初期設定をSTOP中へ移し、最初のCの重複設定を省く。
以前のFM/SSG音程HOSTも同じ重複設定を省く。ターゲット/ネイティブ変換/GPIOは変更しない。
v1.1は最初の音色の先頭Cが他の音と同程度になったと実機報告された。2つ目以降はまだ長めとの報告。
v1.1の音階境界では前の最後のCと次の最初のCをつなぎ、発音中の音色設定時間も含んでいた。
`diagnostics/NOTE-START-V12-README.txt` のHOST v1.2では全音階をSTOP/1秒待機で分け、次の設定を無音中に行う。
各音階の中はキーを保持する。更新は組み合わせHOSTだけ。
v1.2は実機で全4音色の先頭Cがレ・ミと同程度になり、音階間の無音も確認された。
左右正常、歪み/音切れ/気になるクリック音なし、最後の自動消音とHOST PASS・SAFE/DONEを確認。
今回の報告には全ログがないため、新しいブロック数や変換時間、ACK実測値は記録しない。
次は `diagnostics/I2C-ENVELOPE-README.txt` のFMエンベロープ/キー制御診断。
以前のserial/decay値を使い、STOP中のプリセット変更、出力を開いたままのKEY OFFと再発音をI2Cで制御する。
既存ソースを変えず専用ターゲットとHOSTを追加し、GPIO/ネイティブ変換/共通I2C/期限監視は維持する。
エンベロープ診断v1は実機で未完了。ログは区間6後の最終SUSTAIN設定ACK101の後、期限超過でSAFE停止した。
max_poll_us=18516、1988ブロック、ピーク992、期限消音0、stale flush 0。HOSTはその後EIO。
受信386=1424-1038、送信776=3524-2748と整合。音質/最終消音の合格は記録しない。
8レジスタ一括設定が音声期限の余裕を消費し得る設計であり、人工負荷モデルで同じ期限例外を再現した。
v1.1は1poll最大1レジスタに分割し、全8書き込み後にだけACK/プリセットを確定する。
単一書き込みの時間を停止後のENVELOPEログに記録し、期限監視は維持する。
手順は `diagnostics/I2C-ENVELOPE-V11-README.txt`。既存19ヘルパー/GPIO/ネイティブ変換は変更しない。
エンベロープv1.1は実機で全6区間が合格。持続音/キーオフ/再発音/2回の減衰、左右正常、音質正常を確認。
2243ブロック、ピーク992、最大変換1115us、期限超過0、max_poll_us=3022、max_idle_poll_us=462。
ENVELOPE updates=3 writes=24 max_write_us=2667 pending=-1 step=8、期限消音1回、stale flush 0。
最終ACK104が一致し、受信403=1441-1038、送信824=3572-2748も整合。最終自動消音とHOST PASS・SAFE/DONEを確認。
次は `diagnostics/I2C-SIX-README.txt` の外部I2Cによる6音制御診断。
以前実機合格した固定FM3音/SSG3音を使い、各単独音、両和音、6音、独立ミュートを確認する。
1poll最大1チャンネル更新、消音での出力準備、期限切れ時の即時ゲートOFFと分割停止を用いる。
既存ネイティブ変換/共通I2C/GPIOは変更しない。
I2C6音制御は実機で15区間すべて合格。各FM/SSG単独音・両和音・6音・独立ミュート、左右正常を確認。
歪み/予定外の音切れ/気になるクリック音なし、最後の自動消音とHOST PASS・SAFE/DONEまで確認。
3825ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4698、max_idle_poll_us=434。
SIX I2C jobs=15 writes=38 max_write_us=4402 pending=-1 applied=0 prime_left=0。
最終ACK163が一致し、期限消音1回、stale flush 0、受信621=1659-1038、送信1270=4018-2748も整合。
次は `diagnostics/I2C-SIX-ENDURANCE-README.txt` の6音+I2C通信3分耐久診断。
HOST1ファイルだけを追加し、既存19ソース/GPIO/音量/期限監視を維持する。
6音+I2Cの3分耐久は実機合格。主試験180156ms、KEEP517回、ACK周回2回、最大ACK確認92ms、状態照合まで160ms。
左右正常、歪み/音切れ/気になるクリック音なし、最終自動消音とHOST PASS・SAFE/DONEを確認。
16901ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4541、max_idle_poll_us=468。
SIX I2C jobs=7 writes=24 max_write_us=4291 pending=-1 applied=0 prime_left=0。
最終ACK52が(517+47)&255と一致。期限消音1回、stale flush 0、受信2286=3324-1038、送信5680=8428-2748も整合。
次は `diagnostics/I2C-SIX-CYCLE-README.txt` の6音/ミュート/STOP切り替え10周診断。
HOST1ファイルだけを追加し、既存20ソース/ターゲット/GPIO/音量/期限監視は維持する。
6音切り替え10周・80区間も実機合格。独立ミュート/STOP/最終自動消音、左右正常を確認。
歪み/予定外の音切れ/気になるクリック音なし、HOST PASS・SAFE・DONEまで確認。
18268ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4568、max_idle_poll_us=475。
SIX I2C jobs=45 writes=192 max_write_us=4300 pending=-1 applied=0 prime_left=0。
主試験640命令/ACK周回2回、設定変更の最大ACK確認327ms（分割更新/出力準備/通信を含む）。
最終ACK173が(640+45)&255と一致。期限消音1回、stale flush 0、受信2466=3504-1038、送信4874=7622-2748も整合。
次は `diagnostics/I2C-SIX-RECOVERY-README.txt` のHOST通信一時停止と復帰を3回確認する診断。
HOSTの既存GP0/1だけを入力へ解放し、1800ms無通信後に同じI2C0へ再設定する。
同じRev Cの署名/ACK/期限消音/全音源停止を読んでから、明示的STOPで期限フラグを解除して再発音する。
新HOST1ファイルのみ追加し、既存21ソース/ターゲット/GPIO割り当て/音量/期限監視は変更しない。
HOST通信復帰診断も実機で3回の自動消音と再発音が合格。左右正常、音質正常、HOST PASS・SAFE・DONEを確認。
2118ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4577、max_idle_poll_us=470。
SIX I2C jobs=13 writes=48 max_write_us=4408 pending=-1 applied=0 prime_left=0、期限消音3回、stale flush 0。
復帰時ACK51/61/71、最終ACK83が一致。受信350=1388-1038、送信792=3540-2748も整合。
物理的なケーブル抜き差し/電源断/転送途中の異常は未確認。
次は `diagnostics/I2C-VOICE-PITCH-README.txt` の、FM3/SSG3各チャンネルの独立音程制御診断。
既存22ソースを変えず、新しいターゲット/HOST各1ファイルを追加する。診断用識別子はRCPOL01!。
反対側の音源の和音を保持し、各チャンネルでドレミファソファミレドを演奏する。
1poll最大1レジスタ、2回の書き込み完了後にACKし、6音分の音程インデックスを照合する。
ネイティブ変換/GPIO割り当て/音色/音量/1秒期限は維持する。
各チャンネルの独立音程制御も実機で6区間合格。旋律の音程変化と伴奏の持続、左右正常、音質正常、HOST PASS・SAFE・DONEを確認。
6713ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4913、max_idle_poll_us=531。
SIX I2C jobs=17 writes=60 max_write_us=4400 pending=-1 applied=0 prime_left=0。
VOICE PITCH updates=90 writes=180 max_write_us=4561 cancelled=0 pending=-1 step=2。
最終ACK201、期限消音1回、stale flush 0、受信855=1893-1038、送信3096=5844-2748が整合。
次は `diagnostics/I2C-DYNAMIC-PITCH-ENDURANCE-README.txt` の6音連続音程変更3分耐久診断。
全FMキー/SSG音量と出力ゲートを保持し、6チャンネルの音程を順に更新し続ける。
HOST1ファイルのみ追加し、今回合格したターゲットと既存24ソースを変更しない。新耐久診断は実機未確認。
連続音程変更の実機v1は途中で期限超過によりSAFE停止した。9415ブロック、ピーク2976、max_poll_us=18321。
VOICE PITCH updates=331 writes=663 max_write_us=17985 pending=135 step=1、最後のACK172/命令0x80。
FM2の次の音程設定0x87の1回目の書き込み後、2回目の前に停止している。HOSTのEIOはターゲット停止と整合する。
GPIOポートI/Oのenumerate()による一時確保を確認し、インデックスのwhileループへ置き換えた。
MicroPython Unix v1.29のGPIOモデルでは各128組の音程設定で旧FM409600/SSG737280bytesの未回収増分、修正後はいずれも0。
これは実機の約18msがGCによるものだと確定する証拠ではなく、不要な確保の削減を示す比較である。
v1.1ターゲットでは取り込み停止/ミュート中に実機の有限ヒープ検査も行い、1チャンネル16組で64bytesを超えたら発音前に停止する。
生演奏中はGCを有効のまま保ち、期限/ゲイン/PIO/DMA/I2S/GPIO割り当ては変えない。
再試験手順は `diagnostics/I2C-DYNAMIC-PITCH-ENDURANCE-V11-README.txt`。
Rev Cのrev_c_bus_check.pyとrev_c_i2c_voice_pitch_target.pyだけを更新し、HOSTは同じ耐久スクリプトを使用する。
229項目のPCテスト、MicroPython WASMの模擬手順、Unix版のヒープ比較、Arm向けコンパイルを確認。v1.1の実機効果は未確認。
v1.1は実機で3分耐久を完走。ヒープ事前検査6行すべて0bytes、左右正常、歪み/音切れ/クリック音なし、HOST PASS・SAFE・DONEを確認。
主試験181123ms/100グループ/600音程変更/700命令、ACK周回2回、最大状態照合226ms。
17240ブロック、ピーク2976、最大変換1119us、期限超過0、max_poll_us=4542、max_idle_poll_us=514。
SIX I2C jobs=7 writes=24 max_write_us=4075 pending=-1 applied=0 prime_left=0。
VOICE PITCH updates=612 writes=1224 max_write_us=4206 cancelled=0 pending=-1 step=2。
最終ACK247=(7*100+59)&255、期限消音1回、stale flush 0、受信3168=4206-1038、送信13156=15904-2748が整合。
次は `diagnostics/I2C-QUEUE-README.txt` の短い予約演奏診断。
I2Cで9音を先に登録し、FM単独/SSG単独で500ms間隔の再生と自動終了、通信断での予約中止を確認する。
診断用識別子はRCQUE01!。固定9音/500ms/3回の最初の検証であり、正式な予約API/永続形式は変更しない。
新しいターゲット/HOST各1ファイルだけを追加し、既存25ソース、ネイティブ音声変換、GPIO/音量/期限を維持する。実機結果は未確認。
9音予約演奏は実機でFM/SSG各9音が合格。一定間隔の音階、左右正常、音質正常、最後の通信期限中止と無音継続、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2128ブロック、ピーク992、最大変換1117us、期限超過0、max_poll_us=4954、max_idle_poll_us=638。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=58 max_write_us=4116。
FMのキーオフ4556ms/出力終了4700ms、SSG4557msで終了。最後は2音で中止、以降の予約音なし。
SIX I2C jobs=6 writes=6、最終ACK102=(69+17+16)&255、期限消音1回、stale flush 0。
受信416=1454-1038、送信890=3638-2748も一致。
次は `diagnostics/I2C-QUEUE-STOP-README.txt` の予約途中STOPと明示的再開始。
FMを途中停止して4秒の無音を確認し、同じ譜面を先頭から全9音再生、続いてSSGの途中停止を確認する。
HOST1ファイルのみ追加、既存27ソースとターゲットは変更しない。新STOP診断は実機未確認。
予約途中STOP/再開始も実機合格。FM/SSGの途中停止と4秒無音、FM先頭から全9音、左右正常、歪み/予定外の音切れなしを確認。
BUS HEAP全6行0bytes、2244ブロック、ピーク992、最大変換1116us、期限超過0、max_poll_us=4763、max_idle_poll_us=676。
QUEUE runs=3 completed=1 aborted=2 events=15 pitch_writes=30 partial_cancels=0 max_late_ms=58 max_write_us=4123。
SIX I2C jobs=5 writes=6、最終ACK84、期限消音0回、stale flush 0、受信354=1392-1038、送信807=3555-2748が一致。
次は `diagnostics/I2C-QUEUE-ACCOMP-README.txt` の、予約旋律と持続和音の4音再生診断。
FM旋律+SSG低音和音、SSG旋律+FM高音和音を各1回、最後は通信期限で全4音を中止する。
新しいターゲット/HOST各1ファイルを追加、既存28ソースとGPIO/音量/ネイティブ変換/期限は維持する。実機結果は未確認。
伴奏付き予約再生も実機合格。FM/SSGの旋律と反対側の持続和音、最後の全音自動消音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2162ブロック、ピーク2976、最大変換1119us、期限超過0、max_poll_us=4753、max_idle_poll_us=716。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=62 max_write_us=4113。
ACCOMP run_masks=[57,15,15] applied=0、SIX I2C jobs=6 writes=24、最終ACK99=(69+15+15)&255、期限消音1回、stale flush 0。
受信429=1467-1038、送信894=3642-2748も一致。
次は `diagnostics/I2C-QUEUE-ACCOMP-STOP-README.txt` の伴奏付き予約途中STOPと再開始。
FM旋律+SSG和音を途中停止して4秒無音、同じ譜面を先頭から全9音再生し、SSG旋律+FM和音も途中停止して4秒無音を確認する。
HOST1ファイルのみ追加、既存30ソースと伴奏ターゲットは維持する。この追加試験は実機未確認。
伴奏付き途中STOP/再開始も実機合格。全4音の停止と4秒無音、同じ譜面をFMで先頭から全9音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2309ブロック、ピーク2976、最大変換1119us、期限超過0、max_poll_us=4758、max_idle_poll_us=724。
QUEUE runs=3 completed=1 aborted=2 events=15 pitch_writes=30 partial_cancels=0 max_late_ms=44 max_write_us=4051。
ACCOMP run_masks=[57,57,15] applied=0、SIX I2C jobs=5 writes=24、期限消音0回、最終ACK82=(59+23)&255、stale flush 0。
受信373=1411-1038、送信828=3576-2748も一致。
次は `diagnostics/I2C-QUEUE-MUTE-README.txt` の予約再生中の出力ミュートと解除。
FM旋律+SSG和音の途中でDACを、SSG旋律+FM和音の途中でラインをミュートし、譜面を進めたまま解除する。
新しい診断署名RCQMT01!のターゲット/HOST各1ファイルを追加し、既存31ソースとGPIO/音声変換/音量/期限は維持する。実機結果は未確認。
予約再生中のミュート/解除も実機合格。DACミュートはSSG和音だけが残り、ラインミュートは全消音、解除後は旋律途中から継続し、最後の自動消音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2164ブロック、ピーク2976、最大変換1117us、期限超過0、max_poll_us=4941、max_idle_poll_us=872。
QUEUE runs=3 completed=2 aborted=1 events=20 pitch_writes=40 partial_cancels=0 max_late_ms=70 max_write_us=4065。
QUEUE GATES commands=4 dac_mutes=1 line_mutes=1 restores=2 gates=0、GATE NOTESの途中3音はFM側2/SSG側1。
SIX I2C jobs=6 writes=24、期限消音1回、最終ACK99=(73+13+13)&255、stale flush 0、受信448=1486-1038、送信909=3657-2748が整合。
次は `diagnostics/I2C-QUEUE-MUTE-STOP-README.txt` のミュート中STOPとPLAYだけによる再演奏。
DACミュート中のFM旋律+SSG和音とラインミュート中のSSG旋律+FM和音をSTOPし、各4秒無音を確認する。
間に同じ登録譜面をFMで再演奏し、RESTOREなしで通常出力へ戻り先頭から全9音鳴ることを確認する。
HOST1ファイルだけ追加し、既存33ソースとターゲットは維持する。この追加試験は実機未確認。
ミュート中STOP/再開始も実機合格。DAC/ラインミュート中のSTOP後4秒無音、PLAYだけで先頭からFM全9音と伴奏、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2511ブロック、ピーク2976、最大変換1116us、期限超過0、max_poll_us=4912、max_idle_poll_us=862。
QUEUE runs=3 completed=1 aborted=2 events=19 pitch_writes=38 partial_cancels=0 max_late_ms=70 max_write_us=4063。
QUEUE GATES commands=2 dac_mutes=1 line_mutes=1 restores=0 gates=0、再演奏9音のGATE NOTESはすべて3。
SIX I2C jobs=5 writes=24、期限消音0回、最終ACK88=(61+27)&255、stale flush 0、受信418=1456-1038、送信883=3631-2748が整合。
次は `diagnostics/I2C-QUEUE-MUTE-LEASE-README.txt` のミュート中通信中断による自動消音と明示的復帰。
HOST1ファイルのみ追加し、既存34ソースとターゲットは維持する。DAC/ライン各ミュート後1.8秒間I2Cを休止し、予約中止と全音源停止、4秒無音を確認する。
間にSTOPで期限切れフラグを解除し、同じ譜面をPLAYで先頭から通常出力で再演奏する。この追加試験は実機未確認。
ミュート中の通信休止/復帰も実機合格。通信休止で全音自動消音と4秒無音、明示的STOP/PLAYで先頭からFM全9音と伴奏、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2755ブロック、ピーク2976、最大変換1117us、期限超過0、max_poll_us=4914、max_idle_poll_us=855。
QUEUE runs=3 completed=1 aborted=2 events=19 pitch_writes=38 partial_cancels=0 max_late_ms=61 max_write_us=4071。
SIX I2C jobs=7 writes=24、期限消音2回、最終ACK84=(61+23)&255、stale flush 0、受信402=1440-1038、送信901=3649-2748が整合。
予約再生の基本、ミュート、STOP、通信期限切れからの復帰は上記範囲で実機確認済み。
次は `diagnostics/I2C-QUEUE-REPLACE-README.txt` の譜面差し替えとFM/SSGへの再利用。
FMで従来音階を完奏し、停止中に「ドミソミドレファレド」を登録してFMで完奏、同じ登録譜面を再登録せずSSGで完奏する。
HOST1ファイルのみ追加、既存35ソースとターゲットは維持する。この追加試験は実機未確認。
譜面差し替えも実機合格。従来音階と差し替え旋律をFMで完奏し、同じ新譜面をSSGでも完奏、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2578ブロック、ピーク2976、最大変換1118us、期限超過0、max_poll_us=4936、max_idle_poll_us=854。
QUEUE runs=3 completed=3 aborted=0 events=27 pitch_writes=54 partial_cancels=0 max_late_ms=61 max_write_us=4081。
SIX I2C jobs=5 writes=24、期限消音0回、最終ACK114=(69+15+15+15)&255、stale flush 0、受信514=1552-1038、送信1086=3834-2748が整合。
次は `diagnostics/I2C-QUEUE-REST-README.txt` の、伴奏を保持した旋律の休符と再発音。
診断署名RCQRS01!のターゲット/HOST各1ファイルを追加し、「ド・ミ・休・ソ・休・ミ・レ・休・ド」をFM/SSG/FMで完奏する。
休符は旋律だけキーオフし、次の音の音程2レジスタとキーオンを別pollへ分ける。既存36ソース、GPIO、ネイティブ音声処理と期限は維持する。実機結果は未確認。
休符と再発音も実機合格。3回とも旋律だけが休み、伴奏が持続し、次の音で再発音、左右正常、歪み/予定外の音切れなし、HOST PASS・SAFE・DONEを確認。
BUS HEAP全6行0bytes、2428ブロック、ピーク2976、最大変換1119us、期限超過0、max_poll_us=5002、max_idle_poll_us=946。
QUEUE runs=3 completed=3 aborted=0 events=27 pitch_writes=36 partial_cancels=0 max_late_ms=53 max_write_us=4062。
REST QUEUE tones=18 rests=9 rest_key_offs=9 resume_key_ons=9 pair_step=0、SIX I2C jobs=5 writes=42。
期限消音0回、最終ACK110=(59+17+17+17)&255、stale flush 0、受信470=1508-1038、送信994=3742-2748が整合。
この段階の終了条件は `diagnostics/COMMISSIONING-CHECKPOINT.txt` に固定した。
Rev Cの組立とI2C経由FM+SSG再生の実現性確認は、`diagnostics/I2C-QUEUE-REST-FINAL-README.txt` の総合試験1件を残す。
休符中STOP、同じ譜面の完奏、休符で通信を休止して期限中止と無音継続を確認する。合格後はこの段階の追加診断を終了する。
新HOST1ファイルだけを追加し、既存38ソースと休符ターゲットを維持する。この最終試験の実機結果は未確認。
常用ファームウェアとしての正式な音源API・汎用楽曲再生・USB-MIDIは、今回の診断とは別に実装と実機確認が必要。
USB-MIDI、I2C受信、音源制御、FM取り込み・PCM変換をファームウェアへ実装してから発音試験を行う。
ERC/DRCは配線・設計ルールの検査であり、動作や音質、USB認識を保証するものではない。

静的な組立確認の後に使う、実基板Rev C専用の無音バス診断を
`diagnostics/rev_c_bus_check.py` に用意している。Pico 2の公式MicroPython v1.29.0で
SSGレジスタの読み書きだけを検査し、終了時にARM・リセット解除・音声許可をLへ戻す。
手順と制約は `diagnostics/README.txt`。無音診断は2026-11-11に実機で全項目PASSと報告された。
I2Cスレーブ・USB-MIDI・FM取り込みを含む専用ファームウェアとは別の、組立診断用プログラムである。

次のSSG発音診断は `diagnostics/rev_c_ssg_check.py`。同じバス操作を使用し、
A/B/Cを1チャンネルずつ約440Hz・2秒で鳴らし、1秒のミュートを挟んで2周する。
手順は `diagnostics/SSG-README.txt`。発音は実機で確認済みだが、無音時のノイズを評価中。
診断プログラムの終了ログだけでは、音声出力や音質の合格とはしない。

## 成果物

- `output/ym2203-single-board-rev-c.zip`：KiCad 10編集データ、専用ライブラリ、部品表、GPIO表、
  検査結果、ガーバー／ドリル、再生成スクリプト、PDF、SHA-256一覧。
- `output/pdf/ym2203-single-board-rev-c.pdf`：構成・接続・組立・PCB配線・検証結果とA0回路図。
- `rev-c/ym2203-single/ym2203-single.kicad_pro`：ZIPを全部展開してからKiCad 10で開く。
- `output/ym2203-single-board-rev-c-gerbers.zip`：製造入稿用の銅箔・レジスト・シルク・外形・PTH/NPTHドリル。
- `rev-c/verification.json`：検査結果の正本。

### 部品間を線で追える読図用回路図

発注済みRev Cの回路・GPIO・基板データを変更せず、同じ接続を読みやすく描き直した補助図。
全499端子をKiCadのネットリストと照合し、電源3ネット以外の92ネットは連続した信号線で示す。

- `output/pdf/ym2203-single-board-rev-c-connected-a0.pdf`：全部品を載せたA0横の一枚図。
- `output/pdf/ym2203-single-board-rev-c-connected-a3.pdf`：同じ全体図をA3横9ページへ分割。
  ページの周囲を少し重ね、別ページへ続く線を追えるようにしている。
- `output/ym2203-single-board-rev-c-connected.svg`：拡大可能なベクター図。
- `output/ym2203-single-board-rev-c-connected.html`：ブラウザで線に触れるか信号名を入力すると、
  その経路を強調する。ネット接続や外部ライブラリは不要。
- `output/ym2203-single-board-rev-c-connected-validation.json`：入力データのSHA-256、端子照合、
  信号線の連続性と交差の検査結果。

電源の `+5V`・`+3V3`・`GND` は、通常の回路図と同じ共通記号で接続する。
信号線は黒丸のある交点のみ接続、×印は未接続。数字は物理端子番号。
同じICを機能・電源・未使用端子に分けて表示する場合があるが、実装個数は増えない。
Pico 2など既製モジュールの内部回路は省略し、主基板へ接続する全端子を表示する。
H1〜H4は電気接続を持たない固定穴として注記する。

再生成は `python3 hardware/ym2203-single-board/draw_connected_schematic.py`。
Pythonのreportlabが必要。元の `design.json` とKiCadの `netlist.xml` を読み取り、
読図用成果物のみ出力する。回路図の照合は実機動作・音質の検証を代替しない。

## 構成

```text
外部ホスト ─ 3.3V I2C ─┐
                        ├─ Pico 2（C/C++） ─ レベル変換 ─ YM2203C
PC ─ USB-MIDI ──────────┘       ↑                        │
                               └── FM SD/CLK/SH ─────────┘
                                │ PIO/DMA・PCM変換・I2S
                                ↓
                          AE-PCM5102A OUTL ─────┐
YM2203C SSG A/B/C ──────────────────────────────┤
                                               ↓
                              MCP6022 基準電圧＋モノラル混合
                                               ↓
                              CD74HC4053 ミュート → 音量
                                               ↓
                              左右に同じ音 → AMS-22 LINE IN → PC
```

- 主基板は160 × 120mm、2層FR-4、厚さ1.6mm、銅箔35µmを想定。
- Pico 2、AE-PCM5102A、AE-LLCNV ×2は既製モジュールを主基板へ実装する。
  「1枚版」は共通ベースと音源交換基板を一つの主基板へ統合した意味。
- 50ピン交換コネクタ、基板ID、MCP23017、将来音源用A1/SH2/AUXバスは省略。
- MCP6022は1個。基準電圧バッファとFM＋SSGの混合に各1回路を使用する。
- YM2203C、DAC、ミキサーに加え、指定の2連音量ボリュームと3.5mmラインジャックも主基板へ直接実装する。
- スピーカー／イヤホン用電力アンプ、YM3014 DAC、DIN MIDI端子、USBオーディオ機能は含まない。
  モニター用イヤホンはAMS-22へ接続する。

## GPIOと接続端子

使用25 GPIO、GP27は予備（基板上で未接続）。物理端子番号は `rev-c/gpio.csv`。

| GP | 信号 | GP | 信号 |
| --- | --- | --- | --- |
| 0～7 | D0～D7、D0がLSB | 8 | A0 |
| 9 | RESET_RELEASE | 10/11/12 | I2S DATA/BCLK/LRCK |
| 13/14/15 | CS_N/WR_N/RD_N | 16/17/18 | FM SD/CLK/SH |
| 19 | LINE_ALLOW | 20/21 | HOST SDA/SCL |
| 22 | ARM | 26 | DAC_ALLOW |
| 27 | 予備・未接続 | 28 | IRQ_N |

| 端子 | ピン番号と信号 |
| --- | --- |
| JPOWER | AE-USB2.0-TYPE-C（秋月113080）。電源専用USB Type-C。CN2：1=VBUS、2/3=D-/D+未接続、4/7=GND、5=CC1、6=CC2 |
| JHOST | 1=GND、2=SDA、3=SCL、4=GND |
| JRUN | 1=Pico RUN、2=GND。モーメンタリスイッチで短絡してリセット |
| RV1 | RK0971220-F15-C0-A103、2連A10kΩ。1/4=CCW/GND、2/5=左右ワイパー、3/6=CW/音声入力 |
| JLINE | ST-005-G、基板上3.5mm TRS。メーカー端子2=RING、3=SLEEVE、4=TIP（2本） |
| PicoのUSB端子 | PCへ。USB-MIDIデバイスとして使うためのファームウェアが必要 |

JHOSTは3.3V信号のみ。初期I2C速度は400kHzを評価値とし、アドレス・制御コマンド・SysEx形式は
ファームウェア仕様で確定する。現時点で実装済みAPIやWebLab仮想音源ドライバーとの互換性を主張しない。
SDA/SCLの4.7kΩプルアップをホスト側が持つ場合は重複分を実装しない。
外部ホストとはGND/SDA/SCLを接続し、ホストの5Vや3.3V出力を基板の電源へ並列接続しない。
無給電時のI2Cバス分離回路はない。片側だけの給電で接続しない。

USB-MIDI 1.0のクラスコンプライアント機器として実装する方針。
Mac/Windows上での列挙、Note On/Off、Program Change、専用SysEx、I2C同時動作は実機検証対象。
MIDIとI2Cの命令は共通のキューへ集め、音源のレジスタを書き換える順序と制御権を管理する。
標準MIDIファイルの音色がそのままYM2203用に再現されるわけではない。

## 電源

**JPOWERのUSB Type-Cが主電源入力。Pico 2のUSB端子はUSB-MIDI用。**
USB-Cモジュールは秋月113080、AE-USB2.0-TYPE-C（CX70M-24P1実装済み）を使用する。
2ピンの旧電源端子は廃止した。D-/D+は未接続なので、JPOWERはPCへUSBデバイスとして接続されない。
CC1/CC2はそれぞれ独立した5.1kΩ・1%でGNDへ接続する。CC同士を短絡しない。
これによりUSB-Cソースから5Vを受ける。PD通信は行わず、9V/12V等を要求しない。

```text
JPOWER VBUS → F1（PTC 0.5A hold） → USB_FUSED → U11 TPS22918 → +5V
                                                               ├→ YM・5V回路・アナログ
                                                               └→ D1 SS14 → Pico VSYS → 3V3 OUT
JPOWER CC1 → R26 5.1kΩ → GND
JPOWER CC2 → R27 5.1kΩ → GND
```

U11はON=VINで自動投入、CTは10nF・25V以上X7R、QODは未接続。
入力C32=1µF、既存の47µF等はスイッチ後段。5V時の10～90%立ち上がりは典型約26.6ms。
突入電流を抑えるためのスルーレート制御で、定電流制限・逆流遮断・過電圧保護ではない。
F1は短絡対策のPTCで、0.5Aに厳密制限するものではない。

電源は**5Vで1.5A以上を供給できるUSB-C ACアダプター**と短く低抵抗のC-Cケーブルを使用する。
本基板はCCの供給可能電流を自動判定せず、USB列挙やBC1.2判定も行わない。
PCやUSBハブの汎用データポートからの給電は対象外。USB-Aから供給する場合も、
5V・1A以上の専用USB ACアダプターと適切なA-Cケーブルに限定し、実測して使用する。
アダプターの1.5A/3A定格は基板にその電流を流す指定ではない。

全体の初期消費電流予算は400mA以下、3.3V外付け負荷は200mA以下。
USBケーブル・PTC・ロードスイッチに電圧降下があるため、音源ICの電源端子で4.75～5.25Vを必ず確認する。
不足する場合はケーブル／電源の見直しが必要で、5Vを昇圧して補償する回路は含まない。

D1はA=+5V、K=VSYS。PicoのUSBから主電源USB-Cへ逆流する経路を遮断する。
Picoの40番VBUSは基板上で未接続。Pico USBだけでも3.3V側は起動するが、音源側5Vは供給されない。
主電源USB-Cを先に接続し、その後Pico USB-MIDIとホストI2Cを接続する。
終了は演奏停止・ARM=L、I2CとPico USBを外してから主電源USB-Cを外す。
5V喪失検出・I2Cの無給電時分離はないため、演奏中の主電源切断や片側だけの給電でのI2C接続はしない。
両USB端子の同時接続はこの順序で使用する。D1の向き、USB-Cプラグの表裏両方、起動時突入電流と電圧を実機確認する。

## バスと起動時の状態

```text
RESET_N = ARM AND RESET_RELEASE
DAC_XSMT = ARM AND DAC_ALLOW
LINE_RUN = ARM AND LINE_ALLOW
OE_WRITE_N = NOT(ARM AND RD_N)
OE_READ_N = NOT(ARM AND NOT RD_N)
SAFE_CS_N = CS_N OR NOT ARM
SAFE_WR_N = WR_N OR NOT ARM
SAFE_RD_N = RD_N OR NOT ARM
```

ARM、RESET_RELEASE、DAC_ALLOW、LINE_ALLOWにはプルダウンを設ける。
Picoのリセット中はARM=LでYMをリセットし、両データバッファを無効化し、音声をミュートに保つ。
制御用AE-LLCNVは常時有効、DIR=H。3.3V→5V書き込み専用とし、読み取りには74LCX245FTを別に使う。
5V側VIHが3.5V必要な変換器へ、YMのTTL最小VOHをそのまま入力しない。

起動は全ALLOW/ARM=L → CS/WR/RD=H・D0～7入力 → 受信/DMAと無音I2S初期化 →
ARM=H → RESET_RELEASE=H・YM初期化 → DAC_ALLOW=H → LINE_ALLOW=H。
停止・異常時はまずLINE_ALLOW=L、ARM=Lにする。

読み取りへの切り替えはCS/WR=H → Pico D0～7入力 → RD=L → バッファ切替待ち →
CS=L → 音源アクセス待ち → 読み取り → CS=H → 音源バス解放待ち → RD=H →
バッファ切替待ち → Pico D0～7出力。待ちは各1µs以上から評価を開始するが、確定した最適値ではない。
レジスタ書き込み後はBUSYを確認する。実機で過渡的なバス競合がないことを観測する。

8MHzの5V発振器をTC74HC74で2分周し、4MHzをYMへ供給する。
YMのFM出力はI2Sではない。PIOでSD/CLK/SHを取り込み、整数PCM化と48kHzへのレート変換が必要。
FM受信最大2 SM、I2S出力1 SMを別PIOブロックへ置く予算とし、DMA・USB・I2Cの同時処理を評価する。

## 音声と実装

- AE-PCM5102AのOUTLのみ使用し、OUTRは未接続。左右DAC出力を短絡して混ぜない。
- OUTLの470Ω/2.2nFフィルター後とSSG A/B/Cを、それぞれ4.7µF BP・100kΩ経由で合成する。
- SSG各出力の1kΩ対GND負荷は、同系統YM2149資料の条件を参考にした初期値。現物の振幅・歪を測って調整する。
- 帰還22kΩと47pF、小信号利得は各入力およそ-0.22。基準電圧は5Vの中点をバッファした2.5V。
- CD74HC4053のXをMIX_MONOとVREFから選択。MUTE_5V=HでVREFを選び、DACだけでなくSSGも消音する。
- 混合出力をAC結合後、2連10kΩ Aカーブの両連へ入力し、左右のワイパーを各100Ω経由でTRSへ接続する。ワイパー同士は短絡しない。
- 音源の内容は左右同じモノラル。共通軸で左右同時に音量調整するため、部品の連動誤差による左右レベル差はあり得る。ミュートと音量位置は独立する。
- 最大FM＋SSG3音時のヘッドルーム、FM/SSGバランス、相対極性、ノイズとポップ音は実機で確認する。
- AMS-22の3.5mm LINE INへステレオTRSで接続する。平衡モノ入力へのTRS配線と混用しない。

集合抵抗はKOA RKC B回路、1番共通。RN1/RN2/RN6は8素子10kΩ、RN3/RN4は4素子10kΩ、
RN5は8素子1kΩ（SSGに3素子使用）。個別抵抗とフットプリント・内部接続が異なる。
音声・基準電圧の指定抵抗は1%、それ以外は5%可。R/Cは主に1206。
TPS22918はSOT-23-6・0.95mmピッチ。4.7µF BP・10µF等のラジアル品は径5mm・ピッチ2mmを想定。47µFも指定フットプリントに収まる品を選ぶ。
74LCX245FTはTSSOP20・0.65mmが2個、MMBT3904はSOT23のはんだ付けが必要。
既製モジュールとDIP ICはソケットを推奨。モジュールの列間、番号、USBコネクタの向き・挿抜空間を現物照合する。

PCBは公称信号幅0.25mm、最小0.18mm、クリアランス0.20mm、ビア径0.7mm・穴0.3mm。
5V公称0.8mm、3.3V公称0.4mm。GND面は連続させる。両面GNDベタへ直接接続するため手はんだ時は熱容量を確保する。
M3穴は(5,5)、(155,5)、(5,115)、(155,115)mm、穴径3.2mm。寸法は主基板左上を原点とする。

## Rev Bで追加したボリューム・LINEジャック

Rev Aの外付け端子JVOL/JLINEを、RV1とST-005-Gへ置き換えた。GPIO・電源・基板外形は変更なし。
旧Rev Aのガーバーにこれらの部品を取り付けることはできない。製造には最新のRev C一式のみを使用する。

- **RV1**：秋月103604、ALPS RK0971220-F15-C0-A103、A10kΩ×2、軸径6mm Dカット。
  ボディ前面・軸中心の基板上座標を(96,118.5)mmとし、軸は下辺の外へ向く。
  基板上面視のピン1～3は(93.5,113.5)、(96,113.5)、(98.5,113.5)mm、
  ピン4～6は(93.5,111)、(96,111)、(98.5,111)mm。穴径1.0mm、2.5mmピッチ。
  ピン1～3をR1、4～6をR2として図面の連番号を割り当てた。時計回りで音量が増す結線。
  ボディは幅9.5mm・奥行9.55mm。軸・ブッシングは前面から15mm突出し、到達Y=133.5mm。
  突出部分は基板内コートヤードに含めず、F.Fabと別の機構図に示す。
- **JLINE**：秋月102460、Switronic ST-005-G、3.5mm TRS、スルーホール。
  口中心は(145,120)mm（口を基板端に揃える）、挿入口は下辺へ向ける。ボディ幅6.5mm・奥行14mm。
  2=RINGは(142.75,109)、3=SLEEVEは(147.25,109)mm、
  4=TIPは(142.1,116.5)と(147.9,116.5)mmの2本。信号穴径1.2mm。
  位置決めピン用の絶縁穴は(142.5,113)、(147.5,113)mm、穴径1.0mm。
  メーカー図面の1は樹脂ボディの部品番号で、電気端子1は存在しない。
- 挿入側から見た図面を、基板上面視へ正しく対応させた自作フットプリント。
  ジャックとボリュームの軸高は揃わない。ケース穴の高さと板厚、ナット、Dカット用ノブ、
  TRSプラグの外径と挿抜空間を現物照合する。ケース／パネルの製造図は含まない。
- 2連10kΩの入力は並列で約5kΩ、出力の4.7µFとの低域遮断は無負荷概算約7Hz。
  接続先の入力抵抗・ボリューム位置によって負荷と周波数特性は変わる。最小位置で左右が消音し、
  時計回りで両方増音すること、全域の左右偏差、最大出力時の歪を実機確認する。
- 基板外のボリューム／ジャック用配線は不要。ノブと必要に応じたパネル固定は別途。

## Rev CのUSB-Cモジュール実装

モジュールを上面に重ねて実装し、挿入口を主基板の下辺へ向ける。
CN2の7ピン（2.54mmピッチ）に加え、前側のVBUS/GND各2ピンも直ピンヘッダで支えてはんだ付けする。
USBモジュール背面に製造時の端切れが残っている場合は、メーカーの指示どおり切り離す。
長さの異なる足や浮きで傾かないように高さを揃える。ソケットではなく、11本での直接はんだ固定を前提とする。
部品取付前に、モジュール裏面と主基板上の配線・部品の間隔を確認する。

- モジュール外形は20×12.46mm。CN2の端子1を(40.62,108.34)mmとし、
  端子7までXを2.54mmずつ減らして並べる。これはメーカー上面図を180度回転した向き。
- 前側VBUSの支持ピン2本はX=40.62、GNDはX=25.38、いずれもY=115.96/118.5mm。
  支持穴はそれぞれCN2端子1/7と同じネットに接続する。
- 穴径1.02mm、パッド径1.9mm。モジュール基板前端Y=118.9mm。
  USBコネクタの突出・ヘッダ高さ・プラグ外径は現物で照合する。ケース設計図は含まない。
- 電源側の表示は「USB-C POWER 5V」、Pico側は「USB-MIDI」。I2C・音声回路とGPIOはRev Bから変更なし。
- 端子がVBUS/GNDだけのUSB-C部品（秋月116895/117123）はCCが出ておらず、今回の代用品にはならない。

## 段階的な確認

1. 全電源OFF、ICを挿す前に電源間短絡・端子極性・部品番号を確認する。
2. USB-C電源部だけ実装し、表裏両挿しでCC・スイッチ後5V/3.3V・起動電流を測る。
3. ロジック実装後、ARM=LでRESET=L、ネイティブCS/WR/RD=H、両データバッファ無効を確認する。
4. YM未実装で無音I2SとDAC単音、2.5V基準、ミュート、音量、ライン出力DCを確認する。
5. 全電源OFFでYMを挿し、負荷時電圧・4MHz・リセットを確認する。
6. BUSY/ステータス読み取り、SSG A/B/C単音を確認する。
7. SD/CLK/SH波形を観測し、PIO/DMAとPCM変換を確認する。
8. FM＋SSGをAMS-22で録音し、音量、クリップ、ミュート、ノイズを確認する。
9. Mac/WindowsでUSB-MIDIの認識・送受信、I2Cとの同時動作、リセットと長時間運転を確認する。

## 再生成

生成元を編集し、生成物を手直しして再生成で失わないようにする。
Python 3.11以降、KiCad 10.0.5 CLI、KiCad同梱Python（pcbnew）を使用。
`cad.py`・`build_pcb.py`・`finish_pcb.py`は先行2枚版の自作ツールから再利用・適用したもの。

```sh
python3 generate.py
"$KICAD_PYTHON" build_pcb.py
# 出力DSNをローカル配線し、SESを保存する
"$KICAD_PYTHON" finish_pcb.py ym2203-single path/to/routed.ses
kicad-cli sch erc --format json -o rev-c/ym2203-single/erc.json rev-c/ym2203-single/ym2203-single.kicad_sch
kicad-cli pcb drc --schematic-parity --format json -o rev-c/ym2203-single/drc.json rev-c/ym2203-single/ym2203-single.kicad_pcb
python3 verify.py
# PCBからガーバーと分離PTH/NPTHドリルをrev-c/ym2203-single/gerbers/へ出力
python3 make_docs.py
```

`build_pcb.py`は配線済みPCBを未配線へ戻すため、通常の閲覧時には実行しない。
配線はFreerouting 2.5.0 JARをローカルで使用。DSNは0.23mmの余裕を取り、短い細線の幅を
0.18mmへ戻した後、KiCad DRCの0.20mmを検査する。配線ツールは配布物に含めない。
製造入稿ZIPとPDFの作成は検査合格後のみ行う。

## 一次資料

- [USB-Cモジュール回路図](https://akizukidenshi.com/goodsaffix/AE-USB2.0-TYPE-C_sch.pdf)
- [USB-Cモジュール寸法図](https://akizukidenshi.com/goodsaffix/AE-USB2.0-TYPE-C_dimm_20190206.pdf)
- [USB-Cからの給電](https://akizukidenshi.com/goodsaffix/powered_by_type-c.pdf)
- [TPS22918](https://www.ti.com/lit/ds/symlink/tps22918.pdf)
- [Pico 2](https://datasheets.raspberrypi.com/pico/pico-2-datasheet.pdf)
- [YM2203](https://www.bitsavers.org/components/yamaha/YM2203_198911.pdf)
- [YM2149：SSG負荷条件の参考](https://www.bitsavers.org/components/yamaha/YM2149_199209.pdf)
- [AE-LLCNV回路図](https://akizukidenshi.com/goodsaffix/AE-LLCNV-LVC8T245_sch_20210113.pdf)
- [74LCX245FT](https://akizukidenshi.com/goodsaffix/74LCX245FT_datasheet_ja_20150130.pdf)
- [PCM5102A](https://www.ti.com/lit/ds/symlink/pcm5102a.pdf)
- [MCP6022](https://akizukidenshi.com/goodsaffix/MCP6022.pdf)
- [CD74HC4053](https://www.ti.com/lit/ds/symlink/cd74hc4053.pdf)
- [MMBT3904](https://www.onsemi.com/pdf/datasheet/mmbt3904lt1-d.pdf)
- [KOA RKC](https://akizukidenshi.com/goodsaffix/rkc.pdf)
- [指定ボリューム寸法図](https://akizukidenshi.com/goodsaffix/RK0971220-F15-C0-A103.pdf)
- [ST-005-G寸法図](https://akizukidenshi.com/goodsaffix/ST-005-G.pdf)
- [AMS-22](https://zoomcorp.com/manuals/ams-22-ja/)
- [TinyUSB MIDI](https://docs.tinyusb.org/en/latest/examples/device/midi_test.html)

メーカーの図面・フットプリントやファームウェアは配布物へ複製しない。回路記号とフットプリントは自作。
WebLab本体、公開API、WYM1ファイル形式の変更はない。
