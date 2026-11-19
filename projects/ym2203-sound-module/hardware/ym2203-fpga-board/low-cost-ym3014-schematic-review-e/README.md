# LC YM3014B-F音源基板：接続済み回路図 review E

2026-11-19。review Dの方針を回路図へ具体化した。実YM2203C＋支給YM3014B-F＋MCP6002-E/PでFMをアナログ化し、**G40の37番CH1=FM、39番CH2=SSG**としてベースADCへ送る。ベース内の合成後、PCM5102Aから左右へ出す。左右をFM/SSGへ分けて聞く配線ではない。

旧C/D・L/K/シールドB・HOST/C firmware・実機記録を保存し、別版として追加した。GPIOは変更しない。ベースとパネルの電気部品・端子・ネットはCと完全一致し、ベースのPCM1863 ADC・I2S入力・PCM5102A DACを維持した。

| 基板 | KiCad回路図 | 部品参照 | シート（表紙込み） | ネット | native ERC |
| --- | --- | ---: | ---: | ---: | ---: |
| ベース | [p2-base-lc-e.kicad_sch](base/p2-base-lc-e.kicad_sch) | 143 | 15 | 114 | 0 |
| YM2203音源 | [p2-ym2203-lc-e.kicad_sch](module/p2-ym2203-lc-e.kicad_sch) | 83 | 11 | 81 | 0 |
| I2C編集パネル | [p2-panel-lc-e.kicad_sch](panel/p2-panel-lc-e.kicad_sch) | 51 | 9 | 38 | 0 |

YM3014部分は音源の[06-fm-dac-1](module/06-fm-dac-1.kicad_sch)、SSGは[05-ssg-1](module/05-ssg-1.kicad_sch)。3枚ともKiCad10.0.5の全警告を含むERC違反0、出力netlistの全ピン/ネットを設計データと照合した。合計277参照を81購入行でカバーする。回路・端子の静的検証であり、新PCB/DRC・ファームウェア稼働・音質受入の合格ではない。

- [アナログ・時計・電源・停止回路](ANALOG-AND-STOP.md)
- [HOST/MIDI互換と移植・受入条件](COMPATIBILITY.md)
- [費用・各5枚/1セット](COST.md)／[購入CSV](purchase-plan.csv)／[算術正本](purchase-plan.json)
- [KiCad検証](native-verification.json)／[独立検証](verification.json)／[検証手順と制約](VALIDATION.md)
- [メーカー資料・価格観測](sources.json)／[承認・実装範囲](adoption.json)／[保存照合](preservation.json)

## 回路と部品

音源基板の追加は10参照。YM3014B-Fは16SOP、ピッチ1.27mm。RB基準へ10µF電解、MCP6002のA側をRB→MPフォロワ、B側をTO_BUFF→FM出力フォロワにする。DAC入力はYMのSD/CLK/SHから各33Ω、FM出力は100Ωの分離抵抗を介して37番へ接続する。SSGの3本の10kΩ合成抵抗は39番へ変更し、従来の各1.33kΩ負荷は維持する。

MCP6002-E/Pは秋月130011で80円・在庫290個の観測値。8DIPを直接実装し、高価なオーディオ専用品や追加の輸入店を使わない。RBの10µFは秋月117897の50PX10MEFC5X11（10円）。一般0805抵抗・X7R・通常の標準ビア/HASL方針を維持する。支給DAC自体はlegacy品なので、新規に同等品を恒常調達できるとは仮定しない。

YM3014B-F用の[独自ランド](P2LC.pretty/YM3014BF_SOP16_5.3x10.2_P1.27mm.kicad_mod)をメーカー外形図から作成し、16端子・番号・1.27mmピッチを照合した。汎用SOIC16幅3.9mmを代用しない。現物のリード曲がり・実寸による合わせは未完。ベース/音源MCU、USB-B、Grove2箇所の計5ランド未確定はCから継承し、PCBへ進む前に確定する。

## 音声経路

```text
YM2203 FM → YM3014B-F → MCP6002 B → 37 CH1 → PCM1863 L ┐
YM2203 SSG A/B/C → 抵抗合成 → 39 CH2 → PCM1863 R      ┴→ RP2350合成 → PCM5102A → 左右同じFM+SSG
将来音源のMCU → 31/33/34 I2S ──────────────────────────→ RP2350（明示した別プロファイル）
```

音源MCUはSPI/YMバス/停止用に残す。既存FM受信回路も診断用に保存し、承認GPIO16～18を変更しない。通常のE再生はsplit-analogでI2S寄与0とし、source GPIO27のTX_DISABLEをHIGHに保つ。アナログFMと同じFMのI2Sを二重加算しない。将来の別音源基板ではI2S＋analogのhybridが使用できる設計条件を維持する。

価格は各5枚・実装1セット、YM流用・DAC支給、送料と予備枠込み**29,936円**。前Cから185円増。新Gerber/CAMの送料込み見積や全品番の最新カートではなく、約3万円の計画値。追加の音源基板・ADPCMメモリや将来ICの費用は含まない。

## 再生成

リポジトリrootで実行する。Python3.15.2、KiCad CLI10.0.5を使用した。

```sh
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-ym3014-schematic-review-e/generate.py --check
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-ym3014-schematic-review-e/purchasing.py
python3 projects/ym2203-sound-module/hardware/ym2203-fpga-board/low-cost-ym3014-schematic-review-e/verify.py
git diff --check
```

`design.py`は保存Cのcircuit.jsonを読み取り専用で参照し、Eのみを生成する。生成物を直接編集しない。custom symbols/generator/landは本プロジェクトのMIT、メーカーPDFは参照リンクのみで同梱しない。commit/push・発注は行っていない。
