# F1 USB統合RTL：ECP5内部配置配線・タイミング評価

後続のULX3S物理pad／PLL／global配線評価は[BOARD.md](BOARD.md)を参照。
以下はOOC検証時点の条件・結果を保持する。

2026-11-15。実YM2203C＋Si5351A＋USB CDC/MIDI＋I2C v2を含む
`revc_usb_ym_top`について、ECP5向け配置配線を追加した。
対象は**LFE5U-85F、speed grade 6、CABGA381をcontextとするout-of-context（OOC）評価**。
物理pinの割当て・基板への書込みは行っていない。

## 評価範囲

control／USB 48 MHz、音声49.152 MHzの2入力clockをSDCで明示する。
両clockの位相関係は仮定しない。YMの4 MHzはSi5351から実YMへ供給される別信号で、
FPGA内部のclockには使わない。USBを最適化で除去しないよう、モデル専用の非zero IDを指定した。
製品用VID/PIDは未割当てで、RTL既定値0では従来どおりUSB detachedとなる。

nextpnrのOOCモードはIO buffer挿入・global clockのpromotion／routingを無効にする。
論理データ経路を配置配線し、**理想clockでの内部setup制約**を検査する評価である。
多数の診断用top出力を物理GPIO数として扱わず、実モジュール用LPFも作成しない。
clock treeのskew／jitter、pad・USB PHY・電圧変換・PCBの遅延、IO setup/hold、
非同期resetのrecovery/removal、実機電源・アナログ音質は判定していない。
USBの電気適合とホストOSでの列挙も別途必要。[USB実装範囲](USB.md)。

## タイミング経路の修正

最初の統合OOC配置配線ではcontrol側の推定Fmaxが22.48 MHzとなり、48 MHzを満たさなかった。
FIFOのBRAM読出しからms→us変換、遅延判定、停止・所有権処理までが1周期につながっていた。

- FIFO headの時刻変換を段階化し、headの絶対due時刻と100 ms遅延期限を保持する。
  pop・STOP・flushで全段のvalidを破棄する。時刻は64 bit、32 bit msの変換値は42 bitで保持する。
- due／late／期間終了の判定には**現在のnow_us**を使う。期限を過ぎた瞬間にwriterがreadyに
  なっても、1件を余分に実行しない。経過時間snapshotも要求時の64 bit差分から取得する。
- PUSHの6 byte単位・最大32 eventの件数は、合法payload長の有限decodeで判定する。
  MIDI setupのchannel／operator選択も小さい幅の比較・減算にし、汎用整数除算を除いた。
- USB-MIDIの4 byte取出しを登録してからMIDI decodeへ渡す。backpressure中は保持し、
  STOP・USB切断・configuration変更では、その保持語も後続語もflushする。
- 音声faultと実出力gateの状態は、control側のFSM・clock切替interlock・consoleで使う前に
  2段同期する。raw faultによる出力の非同期inhibitと、control clock停止中にも見えるraw診断出力は維持する。

I2Cの0x42／YM22S002／64 byte status／WYM1形式、既存HOST library／playerとC参照コードは変更しない。
MIDI所有中BEGINの拒否、I2C所有中のMIDI破棄、STOP、1秒lease、USB reset／suspend／切断時のMIDI消音、
USB切断中のI2C継続と明示操作による復帰をモデルで回帰する。

中間の相対時刻pipelineには、境界の1周期で古いnowを参照する問題があった。
追加回帰試験はその中間版で失敗し、現在時刻による絶対期限比較で合格した。
元の非pipeline版に同じ問題があったという記録ではない。

## 検証結果

| seed | control推定Fmax | audio推定Fmax | control setup余裕 |
| --- | ---: | ---: | ---: |
| 1 | 49.85 MHz | 85.62 MHz | 0.774 ns |
| 2 | 50.55 MHz | 83.66 MHz | 1.050 ns |
| 3 | 51.41 MHz | 86.06 MHz | 1.382 ns |

3 seedすべてで48 MHz／49.152 MHz制約に合格。IO／DCCA使用数は両方0（OOC）。
合成時LUT4=11,715、FF=7,221、DP16KD=5、DSP=4。
配置後TRELLIS_COMB=18,427/83,640。carry／LUTRAM等も含むためLUT4数とは別の指標。

機能回帰：session 25件（ローカルYs II全123,137 eventを含む制御モデル）、SDA/SCL／HOST 8件、
Si5351／実YM音声結合 10件、USB結合 5件、metadata 3件、MIDI 768 C照合、USB bit列試験が合格。
report拒否／BRAM clock分類テスト4件が合格。FF coneの未分類crossingは0、data／enable bypass変異2件を拒否した。
同期段・reset release間の52チェックで、最大net遅延は2.636 ns。
これはOOCの理想clock下の配置検査であり、MTBFやreset recovery/removalの保証ではない。

Fmaxはツールの遅延モデルからの推定値で、実測値ではない。SDC周期のps丸めにより、
report上の制約値は約48.00077／49.15213 MHzと、公称値よりわずかに厳しくなる。
内部setup余裕の小さいcontrol側は、物理clock treeや最終IOを含めて再評価する必要がある。

`check_real_cdc.py`で直接の2段同期・排他的な初段fanout・reset release pairを確認する。
`check_pnr_cdc.py`では、対応するmapped cell typeを通る**全FFのD／CE／LSR cone**を調べ、
列挙した初段・reset chain以外のclock間consumerを拒否する。dataとenableのbypass変異も拒否する。
36 bit pseudo-dual-port BRAMは、DOA/DOB両方をread port Bのclockで扱う。
rate設定busはstream reset中に反復捕捉し、動作中はsourceが保持するbundled-data方式である。
このcensusはprimary非同期入力、bundled-dataの物理settle時間、MTBFの証明を含まない。

受入runでは`--force`、`--ignore-loops`、`--ignore-rel-clk`、`--timing-allow-fail`を使わない。
広いclock-group切断やfalse-path waiverも追加しない。固定nextpnrのSDC `set_false_path`は
未実装の警告を出す実装であり、効いたものとして扱わない。

## 再現コマンド

プロジェクトルートから、空の出力先を指定する。

```sh
python3 fpga-standalone/check_pnr.py \
  --nextpnr /path/to/oss-cad-suite/libexec/nextpnr-ecp5 \
  --output outputs/f1/pnr-01
```

通常はUSB／音声／Si5351／HOSTの回帰、合成、CDC構造検査、3 seed配置配線を行う。
実行済みの現行RTL機能検証は`--functional-report`で再利用できる。
再利用時は記録したsourceとHOST／C oracleのSHAを照合し、不一致を拒否する。
長い結合モデルを含むため検証には時間がかかる。子プロセスには用途に応じた上限時間を設けた。

[toolchain-pnr-lock.json](toolchain-pnr-lock.json)にOSS CAD Suiteの版・URL・archive SHAを固定する。
本評価はmacOS arm64版。Yosys・Verilator・C compiler、nextpnr実行ファイルのSHAも記録する。本配布物のECP5 chip databaseは実行ファイル内蔵で、そのSHAに含まれる。
配布物の`bin` wrapperはuser領域のXDG設定へ作用するため、ここでは`libexec`を直接指定する。
グローバルツールやHOMEの設定を変更せず、ツールbinary・chip databaseをGitへ取り込まない。

新規記録：[verification/pnr-20261115.json](verification/pnr-20261115.json)。
過去のframe／session／audio／clock／USB報告とRev Cの実機受入記録は保持する。
生成したmapped／routed JSONと実行ログは`outputs/`以下のGit対象外へ置く。
OOCからbitstreamを生成せず、FPGAへの書込みは行わない。

次は実モジュール・USB受信回路・clock入力とpin制約を確定し、IO／global clock treeを含む配置配線、
全cornerのタイミング・reset／CDC・電源確認、F1実機受入へ進む。

一次資料：
[nextpnrの制約](https://github.com/YosysHQ/nextpnr/blob/5e2718b6364e189e414c35b8eef3db4d5e3c0773/docs/constraints.md)、
[ECP5 OOC実装](https://github.com/YosysHQ/nextpnr/blob/5e2718b6364e189e414c35b8eef3db4d5e3c0773/ecp5/main.cc)、
[固定版SDC parser](https://github.com/YosysHQ/nextpnr/blob/5e2718b6364e189e414c35b8eef3db4d5e3c0773/common/kernel/sdc.cc)、
[Yosys DP16KD mapping](https://github.com/YosysHQ/yosys/blob/5628c13240f670b97aaaca3d47940c4afb8ff572/techlibs/lattice/brams_map_16kd.v)。
