# JT03のiCE40UP5K合成・配置配線確認

PC上でYs IIを生成した[JT03シミュレーション](../simulation-jt03/README.md)と同じ
固定コア・YM2203設定を、iCE40UP5K-SG48へ合成・配置配線した。
**音源コアは収まり、4 MHzと16 MHzの内部タイミング条件を満たした。**
製品全体の収容・基板のピン配置・実機動作の確認とは分けて扱う。

## 結果（2026-11-14）

[機械可読の検証記録](verification/up5k-20261114.json)を正本とする。
Yosys 0.71+post / nextpnr-ice40 Homebrew 0.11.1_2 / IceStorm 1.1_1。
音源コアと観測用muxの配置配線結果は次のとおり。

| リソース | 使用 | UP5K全体 | 使用率 | 残り |
| --- | ---: | ---: | ---: | ---: |
| ロジックセル（LC） | 3,062 | 5,280 | 58.0% | 2,218 |
| EBR（4 Kibit） | 3 | 30 | 10.0% | 27 |
| DSP（SB_MAC16） | 1 | 8 | 12.5% | 7 |
| SPRAM（256 Kibit） | 0 | 4 | 0% | 4（計128 KiB） |
| PLL | 0 | 1 | 0% | 1 |
| グローバルバッファー | 5 | 8 | 62.5% | 3 |

EBRには30×4 Kibit、SPRAMには4×256 Kibitの枠があり、両者は異なるブロック。
容量仕様は[Lattice公式データシート](https://www.latticesemi.com/-/media/LatticeSemi/Documents/DataSheets/iCE/FPGA-DS-02008-2-4-iCE40-UltraPlus-Family-Data-Sheet.ashx?document_id=51968)も参照。
残りのメモリーが既存RTLへ自動的に置換利用できるという意味ではない。

音源だけの合成はLUT4 **1,532**、FF **1,908**、キャリー344、EBR3、DSP1。
観測用muxを追加するとLUT4は1,558（+26）、FF数は同じだった。
LUTとFFは同じLCへ格納できる場合があるため、両者を足してLC使用量とはしない。
上表はnextpnrが実際にパッキングしたLC数であり、観測用回路の分を含む。

| 制約クロック | 配置seed | 配線後の推定Fmax | 判定 |
| --- | --- | ---: | --- |
| 4 MHz | 1 | 23.736 MHz | PASS |
| 16 MHz | 1 | 23.736 MHz | PASS |
| 16 MHz | 2 | 23.937 MHz | PASS |
| 16 MHz | 3 | 23.954 MHz | PASS |
| 24 MHz | 1 | 23.736 MHz | **FAIL** |
| 49.152 MHz | 1 | 23.736 MHz | **FAIL** |

16 MHzは3通りの配置で条件を満たした。24 MHz以上の失敗もそのまま保存した。
`--timing-allow-fail`、`--force`、偽パス・マルチサイクル例外は使っていない。
全6ケースで配線が完了し、高周波数の2件は容量不足や配線不能ではなくタイミング未達。
seed 1の最長内部パスはMMRの`effect`から位相生成の`detune_mod_II`へ約42.13 ns。
Fmaxはその経路の遅延を元にした**デバイスモデル上の静的タイミング推定**である。
23.7 MHzでの実機動作や、全seed・全実装条件での上限を保証するものではない。
合成後ネットリストの音声とRTL音声の一致試験も、今回は未実施。

## 検査対象とI/Oの扱い

- 上流は`simulation-jt03/core-lock.json`のJT12/JT03＋JT49。41ファイルのハッシュを照合。
- `simulation-jt03/revc_jt03.v`をそのまま使う。`JT49_DIV=3`、
  `YM2203_LUMPED=0`、FM3声＋SSG3声、LFO/PCM/ADPCMなし。
  上流RTLや前回のWAV生成結果を変更していない。
- `read_verilog -defer`でパラメーターを適用してから階層を展開し、
  未使用の既定YM2612モードの依存モジュールを要求しないようにする。
- Yosysでは`SIMULATION`と`FASTDIV`を定義しない。
  `synth_ice40 -device u -dsp`でUP向けABC9とDSP推論を使い、`check -assert`を実行する。
- 音声40ビット（FM16＋SSG各8）をすべて外へ並列出力するとSG48のI/O数を超える。
  `jt03_fit_probe.v`は、選択入力で40ビットのうち1ビットずつを読む観測用mux。
  全音声ビットを観測可能にして、使わない出力が合成で削除されることを防ぐ。
  ステータス8ビットとサンプル信号も維持する。
- 観測用構成のI/Oは30／39。nextpnrが解析用に自動配置する。
  **I2S、SPI、採用ボードのピン配置を実装したものではない。**
  Rev Cや次期基板の承認済みGPIOを変更しない。
- 音源内部の正・負エッジ双方をツールのタイミング解析へ渡す。
  外部ポートの入力／出力遅延、基板負荷、セットアップ／ホールド、クロックの実デューティは
  制約・検証していない。IRQ・GPIO外部出力もシミュレーション版同様に未公開。

## クロックと次の構成判断

この結果のMHzはRTLの`clk`についての値。音源の公称マスター周波数と区別する。
`cen=1`のときは4 MHzの`clk`が4 MHz YM2203相当となり、前回の再生条件に対応する。
16 MHzで動かす場合は、例えば4クロックに1回の`cen`で4 MHz相当にする構成が考えられる。
その生成回路・通信タイミング・演奏結果は次段階で確認する。

音源単体で約42%のLCが残るため、UP5Kでの全デジタル音源化を続ける根拠が得られた。
ただしSPI／イベントFIFO／時刻制御／再サンプリング／I2S／CDC／安全停止回路はまだ含めない。
これらを加えた最終構成が2,218 LC以内に収まることは未確認。

現在のRTLを49.152 MHzの単一クロックへ統合する案は未達。
次の候補は**音源側を16 MHz等、48 kHz I2S側を49.152 MHz等とし、FIFOで境界を渡す構成**。
Si5351の出力・周波数の関係、可変音源クロック、FIFO残量と消音を同時に設計する必要がある。
もう一つの候補は長い内部経路のパイプライン化だが、FM演算の整合性を再検証する必要がある。
次はSPI＋小さなイベントFIFO＋I2S出力を加えた最小構成の収容・機能確認を行うのがよい。

## 再実行

`projects/ym2203-sound-module`から実行する。

```sh
# macOSで今回使ったツール。brewの最新版が固定版と同じとは限らない。
brew install yosys nextpnr-ice40
python3 -m unittest discover -s synthesis-jt03/tests -v
python3 synthesis-jt03/run.py --output outputs/jt03-up5k/run-01
```

上流RTLは前回の`.cache/jt03/upstream`を使う。なければ
`python3 simulation-jt03/build.py --fetch`で固定版を取得できる（このコマンドはVerilatorのビルドも行う）。
`--upstream`で別の固定版checkoutを指定できる。

`toolchain-lock.json`は検証時のツール版・公式ソースURL／アーカイブSHA・実行ファイルSHAを持つ。
nextpnrのこのHomebrew版は`--version`のバージョン文字列が空なので、パッケージ版と実行ファイルSHAも記録する。
既定では一致しない実行ファイルを拒否する。別OS・別版は、版と差異を確認して
`--allow-other-tools`を指定した別実験として実行する。結果に不一致が記録される。

各回は空の出力先を使い、過去の結果を上書きしない。
合成ログ・JSONネットリスト・配置配線レポート・ASCはGit管理外の`outputs/`へ保存する。
ASCは解析用の自動ピン配置を持つ生成物。書込みコマンドは含めない。
`summary.json`は成功・タイミング失敗・実装失敗を分け、未達を成功に数えない。
成功ケースと意図した高周波数のタイミング未達を収集できればスクリプト全体は正常終了する。
容量不足・配線失敗など別種のエラーはスクリプトを異常終了させる。
判定処理には自動テスト8件を用意した。

## ライセンス

`run.py`とテストはMIT。`jt03_fit_probe.v`は既存JT03ラッパー同様にGPL-3.0-or-later。
GPL全文は`simulation-jt03/LICENSE-GPL-3.0.txt`。JT12/JT49は上流の表示を保持してキャッシュで利用する。
Yosys・nextpnr・IceStormは別途導入するツール。楽曲データは合成へ入力しない。
