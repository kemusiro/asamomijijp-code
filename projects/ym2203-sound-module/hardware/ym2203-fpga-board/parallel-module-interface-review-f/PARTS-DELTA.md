# review F：40接点化による部品点数の見通し

回路/BOM/見積の確定前の比較。E/Dの購入表へ数量変更を混ぜない。

| 機能 | E32接点 | F40接点 | 判断 |
| --- | --- | --- | --- |
| parallel PSGへの制御 | SPI→latch/bridge | baseが直接8bit＋control出力 | 変換latch/bridge MCUを省略可能 |
| 5V digital整合 | カードごとに必要 | 同じく必要 | 接点数では電圧は変わらない |
| read用双方向変換 | 機種別 | 最初のAY/SNはwrite-only | 双方向回路を一律必須にしない |
| SN76489AN READY | bridgeで取込む案 | connector CTL3でbaseへ | 真のopen collectorなら3.3V pull-upのみ候補 |
| 複数SPIのCS | 1本＋局所decode | CTL1/CTL0で追加2本候補 | 一部のdecode/IO expanderを省略可能 |
| 音源別MCU/ADC | 最小構成では不要 | 同じ | I2C発声/ラジオのためだけに増やさない |
| YM FM変換Core | 残る | 残る | bus並列化では独自FM serial→PCM変換は不要にならない |
| アナログ共通ADC/最終DAC | base共通 | 同じ | カード枚数に比例させない |
| コネクタ | 32位置/2×16 | 40位置/2×20 | ハンダ8箇所ずつ増、接点列10.16mm延長 |

追加8接点はすべて信号に使い、GNDは既存12位置を維持。配線時のGND planeと音声線/clock線の配置確認が必要。
単純なラジオカードだけなら40pinの実益は小さいが、parallel PSGや多数の制御端子には具体的な削減余地がある。
基板外形・stack高さ・UNOとの干渉は再確認が必要で、connector延長分だけ基板が増えると確定したわけではない。
