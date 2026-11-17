# P2のリファレンス：Segaアーケード3作品

2026-11-16。移植版ではなく**オリジナルのアーケード版**を対象に構成を調べた。
曲名・版・loop条件・取得元の演奏ログは未選定。再生データの変換や実機確認はまだ行っていない。

| 作品 | FM側 | PCM側 | 提案する音源基板 |
| --- | --- | --- | --- |
| OutRun | YM2151×1、4MHz | Sega 315-5218 PCM系 | OPM＋SegaPCM系＋サンプルメモリ＋DAC/合成 |
| Space Harrier | YM2203×1、4MHz | 初期SegaPCM（discrete logic）系 | OPN＋初期PCM系＋サンプルメモリ＋DAC/合成 |
| After Burner | YM2151×1、4MHz | Sega 315-5218 PCM系 | OutRunと共通ハード候補、bank/clock/mixは別profile |

根拠はMAME開発者の実装：
[OutRun driver](https://github.com/mamedev/mame/blob/master/src/mame/sega/segaorun.cpp)
の`outrun_base`、
[Hang-On/Space Harrier driver](https://github.com/mamedev/mame/blob/master/src/mame/sega/segahang.cpp)
の`sharrier`→`sound_board_2203`、
[X-board driver](https://github.com/mamedev/mame/blob/master/src/mame/sega/segaxbd.cpp)
の`xboard_base_mconfig`。After Burner IIも同系列だが、曲/版は別に識別する。
YM2151はOPM8声の別レジスタ体系であり、YM2203×2やOPNAでそのまま代替しない。

[SegaPCM実装](https://github.com/mamedev/mame/blob/master/src/devices/sound/segapcm.cpp)では、
調査時点の`segapcm_discrete_device`は8 voices、`sega_315_5218_device`は16 voicesで、
レジスタ配置も分離されている。Space Harrierを一律に後期16chの315-5218として扱わない。
同sourceの左右volume、address、delta、loop、bank等をprofile別に照合する。

調査した現行driverのPCM device clock指定は4MHz。これはモデルの入力値であり、
原基板の16MHz等の発振子や外部ICの入力pinへ直結すべき値と混同しない。
PCMを実部品で作る場合は、原回路図の分周・pin timingを確認してSi5351設定を決める。
MAMEのmix係数も回路の抵抗比そのものとせず、原回路と録音比較で決める。
ここでの確認はソース調査であり、基板実測や演奏一致の証明ではない。

## SegaPCMをどう実装するか

| 方式 | 利点 | 残る課題 |
| --- | --- | --- |
| 元のcustom IC / 初期discrete回路 | 原構成に寄せられる | IC入手性・故障/真贋、ROM bus、周辺回路数、初期型との差。主案への採用は未決定 |
| RP2350でPCM機能を実装 | ベースにFPGAを増やさず試せる | 8/16voice、sample fetch、loop/bank/pan、再サンプリング、最悪USB/I2C負荷時の締切を実測。性能合格は未確認 |
| 音源基板に第2MCU / FPGA | sample処理を分離できる | 部品・電源・内部FIFO/時刻同期・firmware/RTL追加。ベースFPGAなし方針を変えるものではないが、別途選択が必要 |

まずPC上のPCMモデル＋手元の正当に利用できるログ/サンプルで音と負荷を測り、
PGA2350一台で足りるか判断する。現在の[raw FM I/F](P2-MODULE-INTERFACE.md)では、
ベースでPCMも作る場合はFMのPCMとソフト合成して共通I2S/DACへ出す案が可能になる。
ただしsample fetch・同時処理・deadlineは未検証。音源基板側でPCMのDACを持つ場合はAUX L/R入力を使う。
互換性は完成音楽のWAV再生でなく、音源イベントとsample address/loopの動作で評価する。
第2MCU/FPGA採用も、別PCM音源ICへの単純置換も、現時点で決定済みではない。

## データ形式とHOST

現行[HOST実装](../../firmware-c/host/lib/ym2203_revc_stream.py)はWYM1と4MHzを検査し、
16-byte headerの後に`<IBB`の6-byteイベントを渡す。
chip番号、OPNAの追加port、PCM memory register、ROM data blockは入らない。
複数WYM1を別々に走らせても、同じ時刻での複数IC・PCMの順序と同期は保証できない。

拡張形式（仮称、名称・byte仕様・protocol番号は未確定）で次を表現する：

- chip type / instance / clock、module ID・能力・必要sample memory。
- 共通時刻＋同時刻内の順序、chip番号、portまたはbus address、値。
- sample blobのID・size・CRC/hash・address配置、bank/mirror、読取範囲。
- upload完了→検証→明示開始。再生中のサンプル補充が要るなら別に設計・検証する。
- 全音源を一度にSTOP/lease停止する単一session。readback・再接続だけでは再発音しない。

既存I2C v2は互換YM2203モードで維持し、新機能は明示的な能力照会と拡張クライアントで扱う。
FIFO不足、未対応chip/clock、sample不足・CRC異常は発音前に拒否し、再生中異常なら全経路消音。
MIDIはmoduleごとのchannel/voice割当を別途定義し、6voiceの旧割当を全候補へそのまま拡張しない。

100kHz I2Cは9clock/byteなら理想上限約11.1kbyte/sで、実効値は要求frame/ACK/statusでさらに減る。
新形式の平均/1ms・10ms・1s窓の最大イベント数、同時刻burst、sample転送量を測り、
先読みFIFOとUSB経路の予算を決める。Ys IIの負荷から3作品の性能を推定合格にしない。
時計精度、bus BUSY、PCM処理、stereo mix、最大遅延も計測項目にする。

## 検証の区切り

1. 著作物を含まない合成sample/自作イベントで、各chipのtone、PCM loop/pan/bank、異常停止を確認。
2. 正当に利用できる原ログとsampleをローカルで解析。曲の対象版、clock、event/sample hashを記録。
3. PCモデルと基板出力をFM/PCM別に比較し、左右、音量比、attack、時間差を評価。
4. 全曲、STOP、通信断・再接続、USB/I2C所有権、sample破損/不足、無音待機を受入。

演奏ログ、ROM/sample、VGM/VGZ、生成音声・曲入りfirmwareはGitへ追加しない。
公開するのは変換/検証コード、合成試験データ、構成・hash等の記録とする。
