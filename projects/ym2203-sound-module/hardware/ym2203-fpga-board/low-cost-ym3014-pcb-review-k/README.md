# 秋月Si5351Aモジュール採用：回路図・PCB review K

2026-11-20。[保存したreview F](../low-cost-ym3014-pcb-review-f/README.md)から別版を作り、
ベースU13を秋月AE-Si5351A-B（110679）へ置換した。内蔵25MHz水晶を使い、旧Y1を削除。
[購入追補J](../low-cost-ym3014-procurement-review-j/README.md)で選定したQ1/E4ロジックも同じランドで採用する。
旧CAD・Gerber・HOST・firmware・実機受入記録は保存する。

| 基板 | 外形 / 層 | 実装参照 | ネイティブPCB |
| --- | --- | ---: | --- |
| ベース | 100×100mm / 4層 | 142 | [p2-base-lc-k.kicad_pcb](base/p2-base-lc-k.kicad_pcb) |
| YM2203音源 | 100×80mm / 2層 | 83 | [p2-ym2203-lc-k.kicad_pcb](module/p2-ym2203-lc-k.kicad_pcb) |
| I2C編集パネル | 100×76mm / 2層 | 51 | [p2-panel-lc-k.kicad_pcb](panel/p2-panel-lc-k.kicad_pcb) |

各PCBと同名の`.kicad_pro`・`.kicad_sch`を一緒に開く。全276参照。
0.6mm径/0.3mm穴の通常ビア、0.2mm以上の配線、鉛フリーHASL、各5枚・部品1セットの条件を維持する。
現Fの製造Gerberは保存用で、Kの新しい接続を製造するために使わない。

- [変更・初期化条件と互換性](COMPATIBILITY.md)
- [モジュール取付・積層・電源](ASSEMBLY.md)
- [購入費27,358.48円の内訳](COST.md) / [購入表](purchase-plan.csv)
- [検証手順と結果](VALIDATION.md) / [機械可読結果](verification.json)
- [一次資料](SOURCES.md) / [クロックプロファイル](clock-profile.json)

モジュールは中心(40,38)mm、10×10mm、2.54mm端子ピッチ・7.62mm列間の独自ランドへ実装。
MSOP10の古いランドと外付水晶は残さない。外付C21/C22は電源のバイパスとして維持する。
他部品の実装原点・表裏、G40全40接点、取付穴、GPIO割り当ては変更しない。

![ベース配置](base/preview-top.svg)

YM3014のFMとSSGはG40の37/39番から共通ADCへ入り、ベースで合成してDAC左右に送る。
オプションのG40 I2S入力、USB CDC/MIDI、受信/6声LED、I2C音色編集、STOP/TEST/RESETも維持する。

P2 firmwareの移植・実機受入は未実施。8pFの水晶負荷設定と起動順序を実装する必要があり、
Rev Cの既存UF2をそのまま使うバイナリ互換を意味しない。KiCad合格を音質や実ミュート時間の実測と扱わない。
