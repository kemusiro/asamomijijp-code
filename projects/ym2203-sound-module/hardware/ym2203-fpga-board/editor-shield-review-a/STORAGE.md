# 音色データと保存・取り出し

新規の提案形式。既存WYM1・I2C status/command形式は変更しない。
[voice_model.py](voice_model.py)はPC上の検証モデル。実FRAM/I2C/USB firmwareではない。

## USB CDCとJSON

ベースのCDCへ追加するnamespaceは以下。既存help/statusと混在しない専用frameで応答する。

```text
voice list
voice export 0
voice import <slot> <byte_count> <crc32hex>  # JSONは続く指定byte数、最大4096。
```

export応答は `VOICE 1 <slot> <byte_count> <crc32hex>\n`、指定長のJSON、`\nENDVOICE\n`。
statusの定期出力はこのframeの外へ延期する。CRC32はJSONのUTF-8 byte列そのものへ適用する。
importは停止時のみ、byte数/CRCと構文/範囲を検証、RAMのstaged patchへ置き、確認操作でFRAMへ保存する。
不完全frameはtimeoutで破棄し、元のslotを消去しない。未知version/重複key/範囲外/過大入力は拒否する。
PCへはUTF-8 `.voice.json`として保存でき、GitやWebLabへの持出しに向く。
専用USBドライブ/MSC・MIDI SysEx・SDは初版で追加しない。CDCからの実取得ツールとfirmwareは次工程。

[JSON例](example.voice.json)。FM1音色templateを3FM channelへ適用できる構造だが、初版試聴はCH1のみ。
clock_hzは採音時の注記。load時には現在clockとの不一致を警告し、クロックを勝手に変更しない。
PCモデルはvalidateとregister plan出力を提供する。

```sh
python3 voice_tool.py example.voice.json --registers
```

## FRAM

MB85RC256V、A2/A1/A0=000で7bit address0x50。1回のmemory pointerは16bit。
64slot×2copy×256byte=32768byte、空き領域なし。slotの絶対位置は `(slot*2+copy)*256`。
メーカーに従い電源安定前のアクセスを避ける。低電圧状態で正常な書込みが成立するという保証は置かない。
WPはLOW固定。UIの明示SAVEが書込みの入口で、knob操作ごとに自動保存しない。

| byte | 内容 |
| --- | --- |
| 0..3 | ASCII Y2VP |
| 4 | version1 |
| 5 | slot0..63 |
| 6..7 | payload length80、LE |
| 8..11 | generation uint32 LE |
| 12..15 | CRC32、LE。0..11と16..254を連結して計算 |
| 16..19 | ALG,FB,preview note,velocity各1byte |
| 20..23 | 0固定 |
| 24..47 | name UTF-8最大24byte、残り0埋め |
| 48..91 | OP1..4各11byte：DT,MUL,TL,KS,AR,DR,SR,SL,RR,SSG-EG,enabled |
| 92..95 | clock_hz uint32 LE |
| 96..254 | 0固定 |
| 255 | commit marker0xA5。最後に1byteで書く |

初期起動で有効slotがなければquiet initをRAMへ作るだけで、全slotを自動初期化しない。
保存はinactive copyのcommitを0へ→0..254を書込み→全体readback/CRC照合→255へ0xA5→再読確認。
active copyは残す。途中断は旧copyを採用。両方正常ならuint32周回を考慮した新generationを採用し、差が2^31なら曖昧として拒否。
CRCは保存時破損の検出であり認証ではない。FRAM実機のbrownout試験は別途行う。

9モデル試験は64slot、257通りの書込み中断、256byte各位置の1bit破損、generation周回を含む。
既存形式への互換主張ではなく、この新形式の設計検査である。
