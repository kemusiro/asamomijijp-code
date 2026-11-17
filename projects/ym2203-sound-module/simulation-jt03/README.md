# JT03でWYM1をPC上再生する

4 MHz・YM2203×1のWYM1を、JT03/JT12のVerilog RTLをVerilatorで実行してWAVにする。
Pico 2・Rev Cを接続せずに動作する。ソフトウェア音源ライブラリへの置換ではない。
本ディレクトリは**RTLの機能シミュレーション**を扱う。続く[UP5K向け合成・配置配線](../synthesis-jt03/README.md)で
音源＋観測回路の収容と内部タイミングを確認した。DAC/I2Sを含む最終回路と実機受入は次段階。

## 固定した構成

- [JT12/JT03公式](https://github.com/jotego/jt12)のコミットとJT49サブモジュール、
  使用41ファイルのSHA-256を`core-lock.json`に固定。取得したRTLにパッチを当てない。
- `revc_jt03.v`はJT03と同じYM2203モードの`jt12_top`を接続する薄いラッパー。
  `use_lfo=0,use_ssg=1,num_ch=3,use_pcm=0,use_adpcm=0,mask_div=0`。
  Rev Cの独立したSSG抵抗入力に合わせて`YM2203_LUMPED=0`。
- **`JT49_DIV=3`を明示する。** 固定した上流`jt03.v`ではこの値が公開されず、
  `jt12_top`の既定値2が使われる。そのままの単音試験は約880 Hzだった。
  本構成ではSSG周期142が`4 MHz/(64×142)=440.141 Hz`となり、実測FFT約440 Hz。
  FMもFNUM=1038/BLOCK=4の単音約440 Hz、FMサンプル周期72マスタークロックを確認した。
  単に楽曲を半速再生したり、書込み値を半分・倍にしたものではない。
- `FASTDIV`は使用しない。4 MHzマスターの両エッジを評価する。
  4096クロックのリセット後を曲時刻0とする。WYM1の同時刻イベントも原順序で送る。
  ステータスBUSYを待ち、アドレス/データを各2 µs保持・各2 µs解放する。
  ミリ秒で丸められた密集イベントは順番に遅れる。実際の開始時刻を全件記録する。
- `fm_snd`と`psg_A+B+C`を分離し、4クロック平均の1 MHz float PCMをFFmpegに流す。
  SWRの128-tap設定で48 kHzへ変換する。1 MHz中間音声をディスクには保存しない。

## 準備・実行

検証した環境はmacOS/Apple clang 21、Python 3.14.6、Verilator 5.054、FFmpeg 8.1.2。
Git・C++17・make・Verilator・FFmpegを別途導入する。スクリプトは依存を自動インストールしない。
下記は`projects/ym2203-sound-module`をカレントディレクトリとして実行する。

```sh
python3 simulation-jt03/build.py --fetch
python3 -m venv .cache/jt03/venv
.cache/jt03/venv/bin/python -m pip install -r simulation-jt03/requirements-analysis.txt
JT03_BINARY="$PWD/.cache/jt03/build/jt03-render" \
  .cache/jt03/venv/bin/python -m unittest discover -s simulation-jt03/tests -v
python3 simulation-jt03/render.py local-test-data/ym2203/ysii/song.bin \
  --output local-test-data/ym2203/ysii-jt03/run-01
.cache/jt03/venv/bin/python simulation-jt03/audio.py \
  local-test-data/ym2203/ysii-jt03/run-01
```

`build.py`は既存のcheckoutを勝手に更新しない。`--fetch`は存在しない場所に固定版をcloneする。
別のcheckoutは`--upstream`、ビルド先は`--output`、実行バイナリは`render.py --binary`で指定できる。
`render.py --limit-ms 35000`なら先頭35秒の確認用。全曲合格とは記録しない。
再生成は別の出力ディレクトリを指定する。楽曲と音声は`local-test-data/`内に置きGitへ入れない。

## 音声の意味

| ファイル | 内容 |
|---|---|
| `ysii-jt03-full.wav` | 全曲、48 kHz/16-bit、同じモノラル信号をL/Rへ複製 |
| `ysii-jt03-fm.wav` / `ysii-jt03-ssg.wav` | FM/SSG別、全曲モノラル。合成と共通のゲインを使用 |
| `ysii-jt03-25-35s.wav` | 曲の25～35秒だけ、同じ固定バランス |
| `stems-float.wav` | 解析用float：ch0=FM、ch1=SSG。**左右音声ではない** |
| `bus-trace.bin` | 各書込み開始cycleのu64LE＋reg u8＋value u8、1件10 bytes |
| `manifest.json` / `simulation.json` / `audio.json` | 入力CRC/SHA、コア・ツール版、全件検査、音声倍率 |

試聴用は各成分に一次5 Hzハイパスを適用してSSGのDCを除き、
`FM/32768 + (255/1024)×(SSG_A+B+C)/255`で合成する。
この相対倍率は上流JT03の`fm_snd + (psg_snd << 5)`に対応する。
16-bit加算器を経由せず浮動小数点で合成し、合成・分離音の最大ピークに共通の
3 dBヘッドルームを設ける。FMとSSGを個別にピーク正規化しない。

**この倍率はRev CのFM100%とアナログ的に校正された値ではない。**
DAC出力電圧・SSGの負荷・反転ミキサー・ポット・録音ADCをモデル化していない。
`audio.py --ssg-weight`で相対倍率を変更でき、使用値は`audio.json`に残る。
raw float stemsはDC・元の倍率を保持する。フィルターやゲインは試聴用音声に限る。

## 既存の実機録音とのA/B

既存の約44秒のライン録音は**C 0.3.0-alpha.4時点**のもの。
受入済み0.5.0-alpha.4の新録音と混同しない。任意の別録音をこの固定設定に渡さない。

```sh
.cache/jt03/venv/bin/python simulation-jt03/audio.py \
  local-test-data/ym2203/ysii-jt03/run-01 \
  --legacy-recording local-test-data/ym2203/ysii-line-capture-20261113/recording.aifc
```

- A＝実Rev Cの曲25～35秒（録音30.770～40.770秒）、1秒無音、B＝同じ箇所のJT03。
- 過去の解析に従い、Bでは旧alpha.4のFM相対遅延46 msを再現する。
  現行ファームウェアの公称4.5 ms遅延を再現する比較ではない。
- 曲1～24秒の帯域制限したパワー包絡から、一定のFM/SSG倍率とノイズ床を非負最小二乗で推定。
  比較する曲25～35秒はフィットに使わない。その後、Bの全体RMSだけAに合わせ、共通に減衰する。
  曲の値・時刻・音程・エンベロープは変更しない。動的コンプレッサーや立上がり補正は加えない。
- `comparison.json`に倍率、遅延、入力SHA、音声SHA、保留区間の包絡相関を記録する。
  包絡相関は波形一致・音色互換の合否判定ではない。聴感の評価が別途必要。
- 校正していない全曲音声と分離音は残す。最新Rev Cとの厳密な比較には新しい同条件録音が必要。

## 2026-11-14の確認結果

[検証記録](verification/ysii-20261114.json)に数値・コア版・生成音声のSHAを保存した。
Ys IIは123,137件・298.218秒・入力CRC32 `ae592289`。
全件の値と同時刻内の順序、早過ぎる書込みがないこと、FMサンプル周期72クロックを検査した。
BUSY待ちを含むアドレス開始遅延の最大は4,967.5 µs。48 kHzの出力は14,314,464フレーム。
単音・キーオフ・データ検査・音声合成など自動テスト8件に合格した。
試聴用7ファイルのフルスケール到達0、全曲の末尾100 msは無音。
リポジトリ内の再ビルドでも先頭900 msのfloat PCMが一致した。

ローカル音声の保存先は`local-test-data/ym2203/ysii-jt03-20261114/`。
旧録音との保留区間25～35秒のパワー包絡相関は約0.971だった。
これは聴感の合否、音色や位相の完全一致を示す数値ではない。
聴き比べと、必要に応じた最新ファームウェアでの新録音比較が次の確認となる。

## ライセンス

独自Pythonツールはプロジェクト既定のMIT。
JT03/JT12とJT49はJose Tejada Gomezによる**GPL-3.0-or-later**。
`revc_jt03.v`・`simulator.cpp`とRTLをリンクするシミュレーターもGPL-3.0-or-laterとして扱う。
`LICENSE-GPL-3.0.txt`にGPL全文を保持する。この例外をプロジェクト全体のMITに読み替えない。
RTL、バイナリ、音声はGitに同梱せず、RTLは固定版を別途取得する。
楽曲WYM1・生成した演奏音声にコードのMIT/GPLを適用しない。公開配布はこの作業の範囲外。
