# Rev C — 実機確認済みの単板設計

[組立・回路の詳細](ASSEMBLY.md)。編集可能なKiCadと製造テキストは`rev-c/`、読図用SVG/HTMLは`output/`。
現行のC版はプロジェクト直下の`firmware-c/`。旧MicroPythonの`firmware/`は比較試験と旧版利用のために保持する。
`diagnostics/`には旧ファームウェアの固定依存5ヘルパーだけを同梱する。

```sh
python3 verify.py
```

正本は配線済みPCB。`generate.py`や`build_pcb.py`は未配線状態を作るため、閲覧・再発注時に実行しない。
回路図・読図資料の生成器はこのディレクトリで完結する。ReportLab等は別途必要。元のRev A/Bや初期2枚版を要求しない。
実機のGPIO・安全停止回路・音声処理を抽出作業では変更していない。
