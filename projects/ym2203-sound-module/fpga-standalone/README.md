# F1 FPGA単独制御の実装

現在の主案は[P2：PGA2350単独・FPGAなし](../hardware/ym2203-fpga-board/PGA2350-STANDALONE.md)。
以下はF1単独構成の実装・検証資産。P2用MCU実装や可変clockでの合格を表すものではない。

実YM2203＋Si5351Aを残し、外付けMCUなしで通信・制御・FM音声処理を実装する。
[構成仕様](../hardware/ym2203-fpga-board/FPGA-STANDALONE.md)と
[API互換計画](API-COMPATIBILITY.md)を正本とする。
ECP5を第一評価候補とし、UP5Kに限定しない。初版はソフトCPUを置かず、状態機械・FIFO・ROMで構成する。

## ULX3S 85Fの物理端子・クロック・配置配線（追加検証）

[BOARD.md](BOARD.md)で評価モジュールをULX3S 85F PCB v3.0.8へ具体化した。
49 padのLPF、12MHz専用PLL入力→48MHz制御、Si5351の49.152MHz音声、2 DCCAを実配線する。
通常P&Rの3 seedで50MHz control setup目標と49.152MHz audioを検査した。
既存HOST／wire・制御権切替・切断時停止は維持する。
USB VBUSの分離・検出とキャリア外付け監視が必要で、実clock skew・電気適合・実機は未検証。

```sh
python3 fpga-standalone/check_board.py --nextpnr /path/to/oss-cad-suite/libexec/nextpnr-ecp5 --output outputs/f1/ulx3s-board-01
```

## ULX3Sキャリア回路図とDiamond準備

[回路図レビューA](../hardware/ym2203-fpga-board/carrier-f1/README.md)に、165部品・110net・11sheetの
native KiCad、部品表、USB VBUS検出専用化、独立電源／heartbeat監視と最終muteを追加した。
[Diamond用bundle生成・制約確認手順](boards/ulx3s/diamond/README.md)を用意し、
49pad・48MHz／49.152MHz・IO・CDC・recovery/removalの追加検証を準備した。
KiCad ERC0、回路モデル7試験、bundle準備7試験、既存HOST/RTL/CのSHA一致を確認。
Diamond実行・PCB配置・電気計測・F1実機受入はまだ行っていない。

## USB統合ECP5内部配置配線（過去のOOC検証）

[TIMING.md](TIMING.md)にLFE5U-85F／grade6の3 seed OOC配置配線と、48MHz／49.152MHzの内部setup評価を記録した。
時刻判定・MIDI取出しのpipelineとCDC同期を調整し、既存HOST互換・所有権／切断時消音を回帰する。
このOOC記録の時点では物理pin未割当て。後続のpad／PLL／global配線評価は上記BOARD.mdへ分けた。

```sh
python3 fpga-standalone/check_pnr.py --nextpnr /path/to/oss-cad-suite/libexec/nextpnr-ecp5 --output outputs/f1/pnr-01
```

## USB CDC・USB-MIDI RTL（追加実装）

[USB.md](USB.md)にFull-Speed複合device、限定CDC console、MIDI6声、I2C排他と切断時消音を記載した。
入口は`revc_usb_ym_top`。48MHz USB/controlと49.152MHz audioを分離し、既存HOST／playerは無変更。
USB識別子は既定0でdetached。試験用IDを実機用の割当てとして流用しない。
理想USB bit列・C版MIDI照合・結合モデルとECP5 mappingを対象とし、このUSB機能単体記録ではOS／実機／配置配線を対象にしない。追加の内部OOC評価は上記を参照。

```sh
python3 fpga-standalone/check_usb.py --output outputs/f1/usb-01
```

## Si5351A起動・可変clock RTL（追加実装）

[CLOCKS.md](CLOCKS.md)に専用I2C controller、設定値生成、readback・PLL監視、
停止中だけのprofile変更と可変SRCを記載した。入口は`revc_clocked_ym_top`。
初期ROMは25MHz XTAL／10pF、YM 1.5〜4MHzの8profile、音声49.152MHz固定。
既存HOST／v2は4MHzのまま維持し、他profile時の4MHz BEGINはDATA6で拒否する。
可変clock選択は内部RTLインターフェースであり、公開HOST APIはまだ追加していない。

```sh
python3 fpga-standalone/check_clocks.py --output outputs/f1/clocks-01
```

## 実YMバス・音声RTL（追加実装）

[AUDIO.md](AUDIO.md)に実YMバス／BUSY、FM serial受信、C互換PCM変換、I2S、
reset・prime・全声停止とclock監視を記載した。`revc_real_ym_top`で既存I2C v2へ接続する。
固定4MHzを最初の検証対象とし、既存HOST／playerは無変更。
PCM 136ケース・73,440サンプルのC照合、RX 54ケース、結合7試験とECP5 mappingを実施する。
この音声単体記録では配置配線／Fmax・USB・実機を対象にしない。追加のclock／USBモデル検証は上記を参照。

```sh
python3 fpga-standalone/check_audio.py --output outputs/f1/audio-01
```

## I2C再生制御・FIFO・STOP／リース（追加実装）

[SESSION.md](SESSION.md)にI2C target・4要求buffer・v2 session・1024件FIFO・
時刻実行・STOP／leaseとadapter条件を記載した。既存HOSTライブラリとplayerを変更せず、
セッション23試験（任意のローカル楽曲1件を含む）・SDA/SCL線モデル8試験が合格した。
ECP5向けI2C制御topの合成・checkも確認した。実YMバス・音声RTLの追加結果は上記AUDIO.mdへ分けた。このI2C単体記録はUSB／統合配置配線／実機を対象にしない。

```sh
python3 fpga-standalone/check_session.py --output outputs/f1/session-01
```

## 初回frame検査ブロックの範囲

`rtl/revc_v2_frame.v`は[既存C I2C v2](../firmware-c/protocol-v2.md)の要求外形とCRCを検査する。
固定208-byte staging、Y2／version／予約領域／実長／宣言長、CRC32/ISO-HDLC、
受信中断、結果保持を実装した。CRCは末尾4 byteを保留して計算し、破損した宣言長を信用しない。
出力は検査済みpacketとresultであり、**成功したYM命令のACKではない**。
opの意味・sequence・所有権・lease・event検査・応答statusは後段session engineの仕事。
未知のopもCRCと外形が正常なら後段へ渡し、そこで拒否する。

全入力は`clk`同期。`reset`はこのモジュールでは同期入力。
`rx_ready`時に`rx_start`を1周期出し、**次周期から**`rx_valid/data`を渡す。
各byteの間に任意の空き周期を入れられる。`rx_end`は最終byteと同周期でも後でもよい。
`rx_abort`ならIO error7。shape error2をCRC error1より優先する。
end／abort後の検査が完了すると`frame_valid`を立て、`frame_take`までpacketと結果を保持する。
保持中の入力は受け付けない。read_addressはpacket全体のbyte offsetで、208以上はFF。
reset後のpacket RAMは未初期化であり、現frame_length内だけを有効として読む。

物理I2Cは追加のtargetと4要求×208 byte bufferを介して接続した。
このframeモジュールだけで物理線へ無制限にbackpressureできるとは扱わない。
受信overflowはsessionをIO fault消音する。USB受信とCDCは別のcomposite moduleへ接続する。
このモジュールだけで音を出したり、fault時の最終ゲートを制御したりはしない。

## 検証

プロジェクトルートから、空の出力先を指定する。外部ボードへの書込みは行わない。

```sh
python3 fpga-standalone/check.py --output outputs/f1/frame-01
```

Python標準ライブラリ、C/C++ compiler、Verilator、Yosysが必要。
検証時点はVerilator 5.054、Yosys 0.71+post (5628c13240f670b97aaaca3d47940c4afb8ff572)、
Apple clang 21.0.0。実行ごとに版・実行ファイルSHA・ソースSHAをsummary.jsonへ記録する。
USB実装では固定版usbcorevを使う。[USB.md](USB.md)に版・ライセンス・build時パッチを記録した。

- payload長0..192の各有効frame、CRC破損、短いframe、長さ不一致、予約byte、上限超過、
  大きなoverflow、受信中断、乱数入力等**576ベクトル**を実RTLへ投入。
- 全byteの保持・最終byteとendの同時入力・可変間隔・結果保持・途中resetを検査。
- errorの優先順等**380件を既存stream.c／wym1.cで照合**。有効frameの命令意味は比較対象外。
- ECP5向けYosys mapping、`check -assert`を実行。

[検証記録](verification/frame-20261114.json)はこの入口だけの結果。
この初回記録ではsessionを含まない。追加実装は[SESSION.md](SESSION.md)を参照。
この初回記録は配置配線とFmax、USB、実YM bus、FM RX、音声出力、API全体、実機受入を対象にしない。
旧JT03構成の収容結果をこの構成に引き継がない。

このフォルダーの独自RTL・試験・ツールはMIT。
既存GPLのJT03用ラッパーからコードを取り込んだものではない。
vendor/usbcorevは同梱LICENSEの例外。無改変の上流とbuild時パッチを分け、版とSHAを保持する。

## 2026-11-18 公開前の再確認

[確認記録](verification/publication-review-20261118.json)に、固定版JT03の再ビルド、
F1 I2C/USB・JT03最小構成のRTL試験と既存検証記録のソース照合を記録する。
楽曲・音声・実行バイナリ・配置配線の生成物は含めない。
保存済みのP&Rを今回再実行した結果や、新しい実機受入として扱わない。
