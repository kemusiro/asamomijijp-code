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
