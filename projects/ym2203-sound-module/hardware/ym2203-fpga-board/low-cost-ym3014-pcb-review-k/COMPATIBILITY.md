# 変更範囲と互換境界

2026-11-20。Fからの変更はbase U13のモジュール化、Y1削除、周辺再配線と、
調達Jの同パッドロジック（音源U16/ULINK0/ULINK1=SN74LV4T125QPWRQ1、UTXOR=SN74LVC1G32DBVRE4）。
全276部品の端子、変更対象外の部品値・配線ネット・実装原点を独立照合する。

| 境界 | 保存する仕様 |
| --- | --- |
| HOST | I2C0 GP20/21、0x42、100kHz、既存v2 BEGIN/APPEND/PLAY/KEEP/STOP、WYM1時刻・順序・CRC |
| service I2C | GP26/27、MCP0x20・panel0x30・ADC0x4A・clock0x60。HOSTとは別バス |
| USB | USB-B信号/RAW VBUS検出/外部5V分離、CDC/MIDI、所有権切替 |
| 停止 | GPIO23 STOP_N、DAC_XSMT強制ゲート、音源ENABLE/RUN、リース、USB喪失時の所有者別停止、明示再開 |
| 音声 | ADC・I2S入力・DACとFM/SSG合成。37=FM、39=SSG、通常プロファイルはFMのI2S二重加算なし |
| 編集パネル | 3.3V I2C、物理ノブ/LCD/保存/JSON取得の契約。UNO形状は既に廃止したLC案を維持 |

## U13新端子

メーカーTOP VIEWのモジュール端子。IC自体の端子番号ではない。

| 新端子 | 名称 | 接続 | 旧IC端子 |
| --- | --- | --- | --- |
| 1 | VDDO | V3V3 | 7 |
| 2 | SCL | SERVICE_SCL | 4 |
| 3 | SDA | SERVICE_SDA | 5 |
| 4 | GND | GND | 8 |
| 5 | CLK0 | SI_YM | 10 |
| 6 | CLK1 | SI_CLK1 | 9 |
| 7 | CLK2 | SI_CLK2 | 6 |
| 8 | VDD | V3V3 | 1 |

25MHz・アドレス0x60を維持。水晶負荷を10pFから8pFへ変更する。
AN619のregister183はbit7:6=10、bit5:0=010010なので全byte書込みなら0x92。
RMWで上位2bitだけ変更するときも下位予約bitの規定を満たすことを確認する。

P2側の必要な起動順序は`clock-profile.json`に記録した。
YM RESET保持・最終出力消音、SYS_INIT完了確認、全クロック無効、CL/PLL/MS設定と読戻し、
PLL安定確認後CLK0だけを有効、音源を無音で初期化・音声prime後に明示再生、の順とする。
CLK1/2は配線を維持するが通常プロファイルでは無効。クロック異常は出力許可を閉じて停止し、自動再演奏しない。
クロック変更もSTOP中だけに制限する。4MHzで既存opn1の初回受入を行い、YM3014のCLK条件を外れる設定を許可しない。

これは接続と実装契約の維持。新P2 HAL、分担MCU、ADC、可変クロックの常用firmwareは未実装。
既存Rev CのCコードは変更せず保存し、そのMIDI・streamモデル試験も回帰確認として実行した。
新基板でのHOST/MIDI実動作・所有権切替・USB切断・STOP/leaseを保証する実機試験ではない。
