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
