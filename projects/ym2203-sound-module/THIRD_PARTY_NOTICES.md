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
- Ys II/Sorcerianなどの楽曲データ、VGM/VGZ/BIN、曲入りプロジェクト/ファームウェアは
  Gitへ収録せず、MITライセンスの対象とも扱わない。
