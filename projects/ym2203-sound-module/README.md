# YM2203サウンドモジュール

YM2203CとRaspberry Pi Pico 2を使う実音源モジュールの基板・診断・ファームウェア。
2026-10～11月にMicroPython WebLabの作業ディレクトリで作成し、2026-11-13に
`asamomijijp-code`へ取り込んだ。以後、実基板とファームウェアはこちらで管理する。
WebLabの仮想デバイス、ブラウザー実行基盤、汎用BINプレイヤーはWebLab側に残す。

Rev Cの回路とファームウェアの解説記事：
[YM2203をPico 2で鳴らす――Rev C音源基板の回路とファームウェア](https://asamomiji.jp/articles/ym2203-revc-sound-module/)。
関連する使い方ガイドは[MicroPython WebLab使い方ガイド](https://asamomiji.jp/articles/micropython-web-lab-guide/)。
記事の公開・サイトのビルドはこのプロジェクトの取り込みと独立している。

## 次期基板：P2ベース＋交換式音源基板

[review J：220mm幅ベース・右側操作部](hardware/ym2203-fpga-board/clean-sheet-pcb-review-j/README.md)を主案にする。
base220×142mm/source100×100mm、4層。DIP・STOP・TESTを右側へ移動し、開口なしシールドと音源の位置は維持。
Hの228参照とGPIO/40接点/電気接続を維持し、
両基板ERC/DRC/未配線/回路図差分0、947pad・40嵌合位置・38UNO接点・64Core接点を照合した。
既存HOST opn1・4MHz、USB-MIDI/所有権、STOP/lease、UNO R3機能を維持する要件。

ソケット高さとシールド干渉は条件付きCADモデル。6か所のビアは実装前の先埋め・平坦化が必要。
新firmware、電源/USB/音声/熱の測定、実物嵌合と実機回帰は未完。製造リリースではない。
G/Hを含む旧設計とRev C実機受入は保存する。

音色編集用の[UNOシールド review B](hardware/ym2203-fpga-board/editor-shield-review-b/README.md)も設計した。
秋月調達優先の4ノブ・encoder・1.54インチLCD・64音色EEPROM保存・USB CDC JSON取得の仕様と接続済み回路図。
ERC0、32接点/159pad照合、保存等13モデル試験。購入小計3,160円（基板等別）。
回路図review A/Bと開口付きPCBは保存。review Bの[開口なし2層PCB](hardware/ym2203-fpga-board/editor-shield-review-b/pcb-review-b/README.md)へ更新し、
ERC/DRC/未配線/回路図差分0、166padと32嵌合座標を照合。LCD・シールド外形とUNO座標は維持。
JではDIP・STOP・TESTを右側へ移し、音源基板との間隔は最小11.225mm。
シールド下面の余裕は寸法モデル。現物嵌合・P2 firmware・実機受入は未完。

[一体型revision 2.1](hardware/ym2203-fpga-board/PGA2350-STANDALONE.md)と
[配線済みレビューB](hardware/ym2203-fpga-board/carrier-p2/pcb-review-b/README.md)は旧設計として保存する。
そのERC/DRCや電源・機構検討の結果は交換式設計へ転用しない。
[P1 PGA2350＋FPGA案](hardware/ym2203-fpga-board/PGA2350-PROTOTYPE.md)も比較資料として保持する。

以下は旧[F1：FPGA単独制御](hardware/ym2203-fpga-board/FPGA-STANDALONE.md)での実装・検証記録。
比較・再利用資産として保持し、MCUへ移すP2の合格とは扱わない。

[最初のRTL](fpga-standalone/README.md)としてRev C v2の要求フレーム検査を実装し、
576入力試験、既存Cパーサーとの380件照合、ECP5向けmappingを確認した。
[I2C制御RTL](fpga-standalone/SESSION.md)では、4要求buffer・v2 session・1024件FIFO・
STOP／リースを追加し、セッション23試験とSDA/SCL線モデル8試験が合格した。
既存HOST／playerは無変更で、ローカルYs II全123137イベントも制御モデル上で順序・CRCを確認した。
[実YMバス・音声RTL](fpga-standalone/AUDIO.md)をI2C制御へ接続した。
固定4MHzのFM受信・C互換PCM変換・I2S、reset／prime・全声停止とclock監視を追加し、
PCM 136ケース・73,440サンプル照合、RX 54ケース、結合7試験とECP5 mappingを検証した。
[Si5351A起動・可変clock RTL](fpga-standalone/CLOCKS.md)も接続した。
設定値生成、専用I2C・readback・PLL監視、停止中の8profile切替と可変SRCを追加した。
既存HOST／v2の4MHz互換を保ち、非4MHz時の誤再生を拒否する。可変選択の公開APIは未追加。
[USB CDC・USB-MIDI RTL](fpga-standalone/USB.md)を接続した。
理想USB bit列・C版MIDI照合・MIDI／I2C排他・USB切断時消音をモデル検証する。
既存HOST／playerは無変更。VID/PIDは未割当てで既定USB detached、OS列挙／実機はこれから。
[USB統合ECP5内部配置配線](fpga-standalone/TIMING.md)を追加した。
LFE5U-85F／grade6の3 seed OOCで48MHz control／USB・49.152MHz音声の内部setupを評価する。
時刻判定・MIDI取出しを段階化し、HOST／制御権／切断時停止を回帰する。
このOOC記録に続き、[ULX3S 85F v3.0.8の物理実装](fpga-standalone/BOARD.md)を具体化した。
49 padのLPF、専用PLL入力、48MHz USB/controlと49.152MHz音声のglobal配線を追加する。
12MHz基準発振器をキャリアに追加し、USB VBUSの給電分離・検出を接続条件にした。
通常P&Rの推定setupとIO配線予算を検証し、USB電気適合・実clock skew・F1実機は別工程。
[ULX3Sキャリア回路図レビューA](hardware/ym2203-fpga-board/carrier-f1/README.md)へ、
US2 VBUSの分離・検出、電源監視と独立watchdog・最終mute、YM／DAC／clock回路を具体化した。
[Diamond追加STAの準備](fpga-standalone/boards/ulx3s/diamond/README.md)に持ち運び用ソースと制約確認手順を追加。
KiCad ERC0とモデル／準備検査を確認し、WindowsでのDiamond実行とF1実機は未実施。
[API互換計画](fpga-standalone/API-COMPATIBILITY.md)はWebLab・Rev C・F1で共通ホストAPIを目指す。
現在のwireの差分を明示し、まずF1とRev CのI2C v2／既存HOST player互換から進める。
[主案の入口](hardware/ym2203-fpga-board/README.md)でPico維持M1等の比較資料を保持する。
Rev Cの既存資産と受入記録を維持する。F1評価用の物理pinを割り当て、キャリア回路図はレビューAまで具体化し、購入・PCB・実機受入は未完。

## JT03によるPC上の音源シミュレーション（比較・再利用資産）

現在のP2も実YM2203を使う。以下のJT03試験は別案の比較・再利用資産として保持する。

[JT03シミュレーター](simulation-jt03/README.md)で、既存の4 MHz WYM1をVerilator上の
YM2203互換RTLへ入力し、全曲WAV・FM/SSG分離音・旧Rev C録音とのA/Bを生成できる。
固定版JT03/JT49のRTLは変更せず、ラッパーでSSG分周を明示する。
楽曲・音声・上流キャッシュはGit管理外。RTL機能試験と次期FPGAの合成・実機受入は区別する。
GPL-3.0-or-laterのシミュレーターは本プロジェクトのMIT既定からの例外。

[JT03のUP5K向け合成・配置配線](synthesis-jt03/README.md)も確認した。
音源＋観測回路は3,062/5,280 LC、EBR3、DSP1。16 MHzは3配置で合格し、
内部Fmax推定は23.736～23.954 MHz。24 MHz／49.152 MHzは未達。
通信・FIFO・I2S・CDC・安全停止を含む最終システムの収容と実機動作は次段階。

[2クロック・SPI/FIFO/I2Sの最小RTL](fpga-jt03-minimal/README.md)を追加した。
4,850/5,280 LC、EBR7、DSP2で収まり、16 MHz／49.152 MHzの両制約を3配置で確認。
CRC付きSPI、イベント時刻実行、音声CDC、I2S、STOP／リース／異常時消音をRTL試験した。
固定4 MHz／48 kHzの試作であり、Pico向けSPIファームウェア・ローダー・物理ピンと実機受入は次段階。

## 現在地と最終目標

**WebLabで再生できたYs II「TO MAKE THE END OF BATTLE」の全曲データを、
Rev Cの実YM2203Cで、音色・書込み順序・演奏時刻を保って演奏することが最終目標。**

- Rev Cの組立とFM/SSG→ライン出力の実機確認は完了。
- 常用MicroPython I2C版の基本再生、3分間の補充式演奏、STOP/通信復帰は実機合格。
- 0.2.0-alpha.1のUSB-MIDI認識、FM/SSG音階、全音停止、Thonny接続は実機確認済み。
- 6声・I2C/MIDI制御権切替もユーザーが確認済み。最後の報告は簡潔な確認であり、
  HOST全ログ・OS名・deadline missesの数値は提示されていない。
- [C SDK版0.5.0-alpha.4](firmware-c/README.md)でローカルWYM1再生とUF2生成を実装した。
  alpha.1の音声経路・Ys II全曲再生はユーザー実機で確認済み（左右正常、歪み・音切れなし）。
  alpha.2のunity出力で音量比は改善したがFMがまだ小さく、一部に粒状音があるとの報告。
  alpha.3のFM150%で音量比は近づき、左右正常・歪み/音切れなしを実機確認。
  30～35秒の粒状音が残り、FM0%で消えるため、alpha.4に生FM信号と書込み時刻の診断記録を追加した。
  粒状音の発生段階・原因は未確定。GPIOと楽曲イベントは変更しない。
  alpha.4の約2秒の生FM記録・先頭13982件の時刻/順序・CRC付き保存を実機確認。
  AMS-22のライン録音ではFMが約46ms遅れるモデルが最良で、FMのみ45ms蓄積する実装と整合。
  alpha.5は公称4.5msへ短縮し、固定ゲインのPCMと楽曲イベントを維持した。
  ユーザー実機で全体的に原曲に近い聴感とFM100%の適切なバランスを確認。
  その後の全曲試験は約112秒、46,468/123,137イベントでfault=9により停止した。
  alpha.6も46.8秒で指数0の受信データを検出して停止。ゲイン異常ではないことを確認。
  alpha.7では低遅延を保ち、クロックの短い揺れを除外する2段階の確認を追加。
  全123,137件・約4分58秒をユーザー実機で1回完走。FM100%で良好なバランス、歪み・音切れなし。
  fault=0、終了時gates=0、DONE、クリップ0、書込み開始遅延最大4,353µsをログ確認。
  除外フラグの観測5回。ローカル内蔵BINの全曲再生を受入完了とする。
  先の短いFM比較音ではユーザーが違い・症状を感じなかったが、録音35秒は曲の約29.2秒で場所が異なる。
  0.4.0-alpha.1で操作側MicroPythonからのI2C v2ストリーミングを実装。
  100kHz・32イベント/要求・1024件リング・CRC/連番・1秒リース・STOPを備える。
  alpha.1はI2C識別後のBEGINで音声fault3を検出して停止。alpha.2でDMAのTX FIFO先行充填と
  音声準備エラーの通知を修正した。alpha.2のI2C全曲再生はHOST・Rev C双方のログで実機受入済み。
  HOSTは123,137件・CRC一致・再送0、Rev Cは全件受信/実行・fault=0・終了時gates=0を確認。
  Rev Cログには2回の完走があり、最大遅延4,475/4,480µs、クリップ0。FM100%で歪み・音切れなし。
  [両側ログの実機受入記録](firmware-c/verification/c04-alpha2-hardware-acceptance.json)。停止/通信休止/復帰の総合確認もユーザー実機で合格。
  現行MicroPython版の1書込み/11.25 ms、HOSTの40 ms ACK待ち、検証用10 kHz I2Cでは不足する。
- 0.5.0-alpha.1でC版USB-MIDI＋CDCを追加。FM3声/SSG3声、ノート制御、全音停止、I2Cとの制御権切替を実装。
  USB-MIDI認識、FM/SSG音階、6声同時発音、全音停止、左右正常、歪み/音切れなしをユーザー実機で確認済み。
  通常Note Off後の余分な入力破棄により、300ms後の和音を落とす不具合をalpha.2で修正。
  追加ログのaudio_ready=0/fault16に対応し、連鎖DMA停止とDREQ再初期化をalpha.3で修正。
  alpha.3で6つの単独音と和音保持、audio_ready=1/fault=0、左右正常・歪み/音切れなしをユーザー実機で再確認。
  [再確認記録](firmware-c/verification/c05-alpha3-restart-hardware-acceptance.json)はユーザー報告に基づく（CDC生ログ未提示）。
  MIDI/I2C制御権切替も実機受入済み。HOST完了とI2C 191/191、fault=0/gates=0、MIDI owned=0を確認。
  [切替受入記録](firmware-c/verification/c05-alpha3-handover-hardware-acceptance.json)。USB切断・復帰も実機受入済み。HOST v1.1でUSB切断中のI2C191件完了、終了後の無音とMIDI復帰を確認。
  [USB受入記録](firmware-c/verification/c05-alpha3-usb-disconnect-hardware-acceptance.json)。
  現行UF2と修正版HOSTの[常用手順](firmware-c/DAILY-USE-README.txt)を用意した。
  **0.5.0-alpha.3でも操作側PicoからYs II全曲を実機受入済み（ユーザー報告）。**
  123,137/123,137件・HOST PASS/DONE・fault=0/gates=0、FM100%で良好なバランス、左右正常・歪み/音切れなし。
  [alpha.3の全曲受入記録](firmware-c/verification/c05-alpha3-fullscore-hardware-acceptance.json)。今回の生ログ・詳細時刻集計は未提示。
- 操作側Pico用の[HOSTプレーヤー](firmware-c/PLAYER-README.txt)を追加。番号選曲・単曲リピート・全曲1周/一覧リピート・Ctrl+C停止に対応する。
  既存のI2Cストリーム処理とRev C UF2は変更せず、112件の自動テストとMicroPythonモデルで検証。alpha.4で選曲再生・リピート・Ctrl+C消音/メニュー復帰もユーザー実機で確認。
- alpha.3の全曲完走後、待機中の音声fault5により次のHOST再生のBEGINが拒否された追加報告あり。
  alpha.4でI2S分周余りの繰越を実装。旧版の長期キューずれを実際のaudio.cモデルで再現し、修正版の10分×6条件と全115件を検証。
  [更新手順](firmware-c/I2S-CLOCK-FIX-README.txt)。**alpha.4も10分待機後の再生とYs II全曲を実機受入済み。**
  123,137件・fault=0/gates=0・クリップ0、最大書込み開始遅延5,301µs、全件10ms未満。
  [alpha.4受入記録](firmware-c/verification/c05-alpha4-hardware-acceptance.json)。旧版の成功・後続異常の記録も維持する。
- イースI「First Step Towards Wars」の1曲全長も、同じalpha.4/HOSTプレーヤーで実機受入済み。
  FM100%で良好なバランス、左右正常・歪み/音切れなし、DONE、期待する5,024件・CRC32=`be705192`の一致、fault=0/gates=0をユーザーが確認した。
  [イースI受入記録](firmware-c/verification/c05-alpha4-ys1-first-step-hardware-acceptance.json)。今回の生ログ・詳細集計は未提示。
- イースIII「The Boy’s Got Wings（翼を持った少年）」の1曲全長も、同じalpha.4/HOSTプレーヤーで実機受入済み。
  FM100%で良好なバランス、左右正常・歪み/音切れなし、DONE、期待する43,172件・CRC32=`568fcf61`の一致、fault=0/gates=0をユーザーが確認した。
  [イースIII受入記録](firmware-c/verification/c05-alpha4-ys3-boys-got-wings-hardware-acceptance.json)。今回の生ログ・詳細集計は未提示。
- 可聴遅延の実測、24時間実機運転、USB/GNDノイズの絶縁対策は別途未検証。

詳細：
[基板・組立と診断履歴](hardware/ym2203-single-board/README.md) ／
[常用ファームウェア](hardware/ym2203-single-board/firmware/README.txt) ／
[実機結果](hardware/ym2203-single-board/firmware/hardware-results.json) ／
[Ys II性能分析と移行計画](hardware/ym2203-single-board/firmware/YSII-PLAYBACK-PLAN.md)。
古い静的検証レポートの「firmware未実装」などは当時の履歴であり、現在の実機結果とは区別する。

## 収録内容

| 場所 | 内容 |
| --- | --- |
| `hardware/ym2203-single-board/rev-c/` | 発注・組立したRev CのKiCad回路図、PCB、ローカルシンボル/フットプリント、製造テキスト、監査資料 |
| `hardware/ym2203-single-board/output/` | 接続を描いたSVG/HTMLなどの閲覧資料 |
| `hardware/ym2203-single-board/diagnostics/` | 組立時からの手動診断、HOST/target、回帰テスト、実機手順 |
| `hardware/ym2203-single-board/firmware/` | 0.2.0-alpha.1のソース、ホストライブラリ、USB-MIDI確認画面、プロトコル、受入記録、固定ランタイム依存 |
| `firmware-c/` | 0.5.0-alpha.3 C SDK版：2コア・PIO/DMA・ローカルWYM1再生、UF2ビルド、USB-MIDI＋CDC操作画面、実機確認手順 |
| `hardware/ym2203-single-board/rev-a/`, `rev-b/` | 1枚基板の設計履歴 |
| `hardware/sound-module-platform/`, `hardware/sound-module-pcb/` | 共通ベース＋交換基板案の履歴と元になったCAD生成コード |
| `hardware/ym2203-i2c-prototype/` | 初期I2C試作案と参照ドライバー接続の検証 |
| `reference/weblab/` | WYM1仕様とMITのPythonプレイヤー/ドライバーの参照用スナップショット |
| `migration.json` | 元ファイルのSHA-256、移行後のSHA-256、除外理由と移行時の変更 |

Rev CのKiCad ERC/DRC記録は10.0.5。旧版は各レポートに記録された版を確認する。
KiCadの回路図・PCB・ローカルライブラリは編集可能な原本として収録する。
Gerber/ドリルなどのテキストとSVG/HTMLは、発注時との照合・人間のレビューに使うため収録する。
古い案をRev Cの部品番号・GPIOと混同しないこと。

生成ZIP/PDF/PNG、KiCadの個人状態・バックアップ、PythonキャッシュはGitへ入れない。
旧手順のZIP/PDFへの記載は生成成果物を指す。旧ZIPをリモートへ公開したという意味ではない。
元のローカル成果物は削除していない。新規生成先は`outputs/`などの管理対象外ディレクトリとする。
必要なReleaseの作成・添付ファイルの公開は、この取り込みでは行っていない。

取り込みハッシュと固定ランタイムを維持するため、`.gitattributes`で改行の自動変換を抑止する。
KiCad生成SVGの末尾空白、CSVのCRLF、既存3ソースの末尾空行と過去ログの空白は
原本のまま保存し、その箇所に限りGitの空白検査属性を指定している。

## 検証の実行

以下は本ディレクトリをカレントディレクトリにして実行する。
CPython検証は標準ライブラリだけを使用し、現在の検査環境はCPython 3.14.6。
実機ファームウェアは公式MicroPython 1.29.0、Pico 2/RP2350 Arm用。

```sh
python3 -m unittest discover -s hardware/ym2203-single-board/firmware/tests -v
python3 -m unittest discover -s hardware/ym2203-single-board/diagnostics -p 'test_*.py' -v
python3 hardware/ym2203-single-board/verify.py
python3 hardware/ym2203-single-board/firmware/generate-midi-pitches.py --check
python3 tools/verify-migration.py
python3 hardware/ym2203-single-board/firmware/build.py outputs/ym2203-source.zip
```

基板検証は収録した設計モデル・ネットリスト・幾何情報・KiCadレポートの整合検査。
KiCad ERC/DRCを再実行したことや、実機測定を代替したことにはならない。
一部のCAD生成/PDF出力にはKiCad CLI、ReportLab、日本語対応フォントが別途必要。
特にPDF生成は元のmacOSフォント参照を保持しているため、他OSではフォント指定の移植が必要。

Nodeは22.23.2、pnpmは11.19.0、Playwrightは1.64.0で固定する。
`scripts/setup-node.sh`は公式アーカイブのSHA-256を検査し、プロジェクト内`.cache/`へ展開する。
グローバルNodeは変更しない。Nodeコマンドは`./scripts/use-node.sh`を経由する。

```sh
./scripts/use-node.sh pnpm install --frozen-lockfile
./scripts/use-node.sh pnpm exec playwright install chromium
./scripts/use-node.sh node hardware/ym2203-single-board/firmware/verify-midi-ui.mjs
```

MicroPython WASM検証だけは外部の固定ビルドを明示的に指定する。アプリ本体を本リポジトリへ
取り込まず、[元リポジトリの固定コミット](https://github.com/kemusiro/micropython-web-lab/tree/d504cb2bdc1ab29a6cee63115e9e87c962184ed3)
にある`src/vendor/micropython-build/micropython.mjs`と隣接する`.wasm`を使用する。
ローダーは両ファイルを`tools/micropython-wasm-lock.json`のSHA-256と照合する。

```sh
export MICROPYTHON_WASM_MODULE=/path/to/micropython-web-lab/src/vendor/micropython-build/micropython.mjs
./scripts/use-node.sh node hardware/ym2203-single-board/firmware/verify-micropython.mjs
```

WASMはMicroPython 1.28.0、実機は1.29.0であり、GPIO・USB・時刻はモデルに置き換える。
WASM/CPython/Arm向けコンパイル/ユーザーの実機確認を、同じ試験結果として扱わない。
過去の詳細な検証条件・ヒープ測定・コンパイル結果はファームウェアの`validation.json`と
`verification/`へ保存している。移行時に行った検査は`migration-verification.json`へ記録する。

## 配線・導入

GPIO割当は既にユーザー承認済み。変更前には必ず確認する。
Rev C側は外部5 V電源、4 MHz YM2203C、Pico 2、PCM5102A、アナログミキサーを使い、
FM＋SSGのモノラルを左右のライン出力へ複製する。AMS-22でPCへ取り込む。
現在のファームウェア導入は
[導入手順](hardware/ym2203-single-board/firmware/USB-MIDI-README.txt)を参照する。
移行によるtarget/host Pythonソースと製造データの変更はなく、実機の再書込みは不要。

## ライセンスと来歴

**このプロジェクトは[MIT License](LICENSE)**。移行先ルートのBSD-2-Clauseを
遡って適用せず、元の著作権・SPDX・帰属表示を保持する。
詳しくは[第三者要素](THIRD_PARTY_NOTICES.md)と[migration.json](migration.json)を参照する。

Ys II等のBIN/VGM/VGZ、曲入りUF2、曲入りZIPはローカル再生テスト専用。
このリポジトリには含めない。今後の実機テストデータも`local-test-data/`へ置く。
WYM1仕様の参照コピーと曲の性能統計は、楽曲イベントそのものの公開とは区別する。

## P2 revision 2.1 配線候補レビューB

[電源・ソケット・PCBの検討](hardware/ym2203-fpga-board/carrier-p2/pcb-review-b/README.md)を追加。
164部品・164×124mm・4層の配線済み候補をKiCadで検査する。UNOヘッダー座標、47 GPIO、既存HOSTは維持。
電流と温度の実測、ソケットの実物嵌合、製造条件確定、P2ファームウェア移植と実機受入は未完。
