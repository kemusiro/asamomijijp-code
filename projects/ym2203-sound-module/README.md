# YM2203サウンドモジュール

YM2203CとRaspberry Pi Pico 2を使う実音源モジュールの基板・診断・ファームウェア。
2026-10～11月にMicroPython WebLabの作業ディレクトリで作成し、2026-11-13に
`asamomijijp-code`へ取り込んだ。以後、実基板とファームウェアはこちらで管理する。
WebLabの仮想デバイス、ブラウザー実行基盤、汎用BINプレイヤーはWebLab側に残す。

専用記事は未公開。関連する使い方ガイドは
[MicroPython WebLab使い方ガイド](https://asamomiji.jp/articles/micropython-web-lab-guide/)。
記事の公開・サイトのビルドはこのプロジェクトの取り込みと独立している。

## 現在地と最終目標

**WebLabで再生できたYs II「TO MAKE THE END OF BATTLE」の全曲データを、
Rev Cの実YM2203Cで、音色・書込み順序・演奏時刻を保って演奏することが最終目標。**

- Rev Cの組立とFM/SSG→ライン出力の実機確認は完了。
- 常用MicroPython I2C版の基本再生、3分間の補充式演奏、STOP/通信復帰は実機合格。
- 0.2.0-alpha.1のUSB-MIDI認識、FM/SSG音階、全音停止、Thonny接続は実機確認済み。
- 6声・I2C/MIDI制御権切替もユーザーが確認済み。最後の報告は簡潔な確認であり、
  HOST全ログ・OS名・deadline missesの数値は提示されていない。
- [C SDK版0.5.0-alpha.3](firmware-c/README.md)でローカルWYM1再生とUF2生成を実装した。
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
  [現行版の全曲受入記録](firmware-c/verification/c05-alpha3-fullscore-hardware-acceptance.json)。今回の生ログ・詳細時刻集計は未提示。
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
