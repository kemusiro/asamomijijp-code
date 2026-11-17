# ライセンス・第三者要素

- 旧MicroPython WebLab作業ディレクトリから取り込んだコード・独自CAD・資料は
  MIT License。`LICENSE`とソース内の著作権/SPDX表示を保持する。
- `reference/weblab/`の仕様・Pythonドライバー/プレイヤーは同じMITプロジェクトからの
  参照用コピー。元のパスとSHA-256は`migration.json`に記録する。
  WebLab側での改訂を自動取得せず、物理Rev Cのv1 I2Cプロトコルと互換とも仮定しない。
- CAD生成コードは独自シンボル/フットプリントを生成する。メーカーのデータシートは
  URLによる参照とし、メーカーPDFそのものは同梱しない。
- MicroPythonはMIT License。公式UF2、mpy-cross、WASMのバイナリは同梱しない。
  WASMの外部参照元と固定ハッシュは`tools/micropython-wasm-lock.json`に記録する。
- 検証用のPlaywrightはApache-2.0、Node.jsはMIT等のライセンスで配布される別途導入物。
  それぞれの配布物のLICENSE/NOTICEに従う。ブラウザーやNodeバイナリはGitへ収録しない。
- ReportLabとPDF用フォントは利用者環境の別途導入物。ライブラリやフォントデータは同梱しない。
- `firmware-c/pio/i2s_tx.pio`はRaspberry Pi pico-extrasのBSD-3-Clauseコードを改変したもの。
  当該ファイルはプロジェクトのMIT既定からの例外とし、著作権と全ライセンスを
  `firmware-c/THIRD_PARTY_LICENSES.txt`に保持する。C版UF2には別途取得したPico SDK、
  TinyUSB、CMSIS、Armツールチェーンのコードがリンクされるため、ローカル配布ZIPにも
  各ライセンスを同梱する。SDK・ツールチェーンのバイナリ自体はGitへ入れない。
- Ys II/Sorcerianなどの楽曲データ、VGM/VGZ/BIN、曲入りプロジェクト/ファームウェアは
  Gitへ収録せず、MITライセンスの対象とも扱わない。

- C版I2C slave補助コードはPico SDK2.2.0のpico_i2c_slaveをリンクする。
  Copyright (c) 2021 Valentin Milea、Copyright (c) 2023 Raspberry Pi (Trading) Ltd.、
  BSD-3-Clause。`firmware-c/LICENSE-PICO-I2C-SLAVE.txt`をUF2配布ZIPにも同梱する。

- C版USB-MIDI1.0のクラス処理と記述子マクロは、固定コミットのTinyUSB（MIT）を利用する。
  上流を変更せずリンクし、UF2配布ZIPに既存のLICENSE-TINYUSB.txtを同梱する。

- `simulation-jt03/`はPC上の機能検証用。JT12/JT03とJT49（Jose Tejada Gomez）は
  GPL-3.0-or-later。上流は`core-lock.json`の固定版を別途取得し、Gitへベンダー化しない。
  独自ラッパー`revc_jt03.v`とC++ハーネス`simulator.cpp`、RTLをリンクした
  シミュレーターもGPL-3.0-or-laterとして扱う。全文は同ディレクトリの
  `LICENSE-GPL-3.0.txt`。独立したPythonツールはMIT。楽曲・生成音声には適用しない。
  Verilator・FFmpeg・NumPy・SciPyは別途導入する検証ツールで、バイナリやライブラリを同梱しない。

- `synthesis-jt03/jt03_fit_probe.v`もGPL-3.0-or-laterのJT03用ラッパー。
  合成・配置配線スクリプトと判定テストはMIT。GPL全文は
  `simulation-jt03/LICENSE-GPL-3.0.txt`を参照する。
  Yosys・nextpnr・IceStormは別途導入し、固定した版とSHAを検証記録へ残す。

- `fpga-jt03-minimal/`のRTLとVerilator用C++テストはGPL-3.0-or-later。
  `simulation-jt03`と同じ固定版JT03/JT49を利用する。GPL全文は
  `simulation-jt03/LICENSE-GPL-3.0.txt`。独自Pythonツール／テストはMIT。
  同期FIFO・Grayポインター・SPI・I2S・安全停止は独自の試作RTLであり、
  楽曲データや第三者のサンプル音声をRTL／検証コードへ埋め込まない。

- `fpga-standalone/`の独自I2C／frame／session／FIFO RTL、C++試験、Python検証はMIT。
  既存C版のMITプロトコル実装を照合元として使い、GPLのJT03ラッパーを取り込まない。
  LUNA（BSD-3-Clause）はUSB実装の候補資料への参照のみで、現時点では依存の追加・
  ソース／生成物の取り込みはしていない。導入時に上流版と表示義務を記録する。

- F1 USB PHY/SIEはavakar/usbcorevのcommit
  `8f799bb9f188f0266ff7926fdc93fad0fc754eae`を固定する。
  元のLICENSE（No-notice MIT License）全文と無改変ソース、ファイルSHAを
  `fpga-standalone/vendor/usbcorev/`に保持する。このvendor部分を本プロジェクトのMITへ置換しない。
  `tools/prepare_usbcore.py`がSHA照合後、build出力コピーへだけ
  `patches/f1-validation.patch`を適用する。変更内容・検証・上流参照は
  `fpga-standalone/USB.md`。独自class／MIDI／console RTL・試験・ツールはMIT。
  upstream READMEにある第三者開発ボードの文言は来歴であり、F1の対応board保証ではない。
  USB VID/PIDの使用権や電気規格への適合を、ソースのライセンスから導かない。

- `fpga-standalone/check_pnr.py`は外部のnextpnr-ecp5／Project Trellisのdevice遅延モデルを
  使用する。評価に用いたOSS CAD Suite配布物は`toolchain-pnr-lock.json`で版・archive SHAを
  固定し、別途取得する。binary／chip databaseはGitへ取り込まない。
  nextpnrはISC、Project TrellisのlibtrellisはISC、databaseはCC0の各上流表示に従う。
  配布物のライセンスをそのまま保持し、独自のRTL／Python検証は従来どおりMITとする。

- F1のULX3S 85F端子事実はemard/ulx3s commit
  `6a92cec6b177191c5b0f80e260013a1f8ec147dd`のv3.0.8回路図・LPF・manualを参照する。
  上流Copyright (c) 2016-2018 EMARDと、基板ロゴ保持条項を含む元の許諾文を
  `fpga-standalone/boards/ulx3s/UPSTREAM-LICENSE.md`に保持する。
  回路図PDF／基板CAD一式は取り込まない。独自boardラッパー・検証はMIT。

- `hardware/ym2203-fpga-board/carrier-f1/`の回路・KiCad symbol・生成器・検査は独自MIT。
  ICのdatasheet、ULX3Sの固定版回路図は部品のpin／電気条件の参照資料で、PDFや図版を取り込まない。
  KiCad本体・公式footprintは外部インストールを参照し、公式library素材を同梱しない。
  Diamond準備用Tclは公式User GuideのAPIを参照した独自script。
  Lattice Diamond／Synplifyのbinary、device library、文書を同梱しない。利用時は各社のlicenseに従う。
  解析bundleにもプロジェクトMIT・USB上流・ULX3S来歴の許諾表示を保持する。


## P2 revision 2.1 carrier review A (2026-11-15)

- Pimoroni PGA2350公式回路図・pinout・寸法図とArduino UNO Rev3e CADは、
  実ピン番号・位置・寸法の照合にのみ参照した。第三者のPDF、CADアーカイブ、
  銅箔、シルク、回路データは同梱しない。参照URLとSHA-256は
  `hardware/ym2203-fpga-board/carrier-p2/sources.json`に記録する。
  Arduino提供CAD自体のライセンスはCC BY-SA 4.0。新規ソケットとヘッダー配置用の
  フットプリントは数値事実から独自生成し、本プロジェクトのMITを適用する。
- KiCad 10標準フットプリントの参照名をBOMに使用し、配置確認用PCB内では
  標準DIPソケットと取付穴フットプリントを使用する。
  KiCadライブラリは[CC BY-SA 4.0 + KiCad libraries exception](https://www.kicad.org/libraries/license/)。
  この例外に基づき、使用した設計文書全体のライセンスはMITを維持する。
  標準ライブラリファイルの単独再配布は追加していない。
- RP2350 pin muxの照合は既存の固定Pico SDK 2.2.0（BSD-3-Clause）の定義を参照し、
  新しいSDKコピーや実行時依存は追加しない。

## P2 PCB review B の設計支援ツールと寸法資料

- KiCad 10.0.5の標準フットプリントをキャリア候補PCBへ埋込み。KiCadライブラリのCC-BY-SA-4.0と
  回路基板への組込み例外について、既存のKiCad記載を参照。P2C独自ソケット／UNOフットプリントは寸法事実から作成。
- Freerouting 2.1.0（GPL-3.0）をローカルDSN/SES変換へ使用。ツールJARは同梱せず、
  使用版・ハッシュをcarrier-p2/pcb-review-b/toolchain.jsonへ記録。ツールの使用は本プロジェクトのMIT表示を置換しない。
- Pimoroni、TI、Diodes、Skyworks、Harwin、Mill-Max、Samtecのデータシート／製造寸法を参照。
  第三者PDFとモデルは同梱しない。64本の単端子ソケット候補の実挿入量・保持力は未実測。

### P2分離PCBレビューD

- `hardware/ym2203-fpga-board/digital-module-pcb-review-d/`の回路・独自Core個別ソケット座標・検査・組立図・説明はMIT。
- 標準KiCadフットプリントをネイティブPCBへ埋込み。既存のCC-BY-SA-4.0とKiCad libraries exceptionの記載を適用する。
- Waveshareの外形図とラベル付き上面図、Samtec/Mill-Maxの製造寸法を参照し、寸法事実からソケット図を作成。
  メーカー写真・PDFは同梱しない。出典と確認用ハッシュはレビューDの`sources.json`。
- Freerouting2.1.0をローカル配線候補に使用。JAR、Javaクラス、メーカー図は再配布しない。最終CADと検査を正本にする。


## P2 音色編集シールド review BのPCB

- `hardware/ym2203-fpga-board/editor-shield-review-b/pcb-review-a/`と`pcb-review-b/`のnative PCBにはKiCad10標準footprintを埋め込む。
  上記CC BY-SA 4.0とKiCad libraries exceptionの記載を適用する。
- ED2のUNO座標・encoder長穴・支持穴、配置図・検証コードは数値事実から作成した独自MIT。
  メーカーPDF、製品写真、Freerouting JAR/クラスは同梱しない。最終native CADと検査結果を正本とする。
