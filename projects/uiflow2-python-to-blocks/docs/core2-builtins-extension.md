# Core2内蔵デバイスと画面部品への対応計画

## 方針

変換プロファイル`core2-v1.3-uiflow2-v2.5.3`を、RGB Unitだけでなく、M5Stack Core2 v1.3の
内蔵画面部品と内蔵デバイスまで段階的に拡張する。

完成条件は従来と同じく、入力Pythonの元のブロック配置や分割を復元することではない。
対応範囲のPythonから、Core2／UiFlow2 V2.5.3で読み込み、編集、Python再生成、実機実行できる、
動作が同等な`.m5f2`プロジェクトを生成する。

現在の実装はRGB Unitの`fill_color`、`time.sleep`、最善努力変換での
`M5Page`、`M5TextArea`、`BtnA/B/C.wasPressed()`、Speakerの`begin`、
`setVolumePercentage`、`tone`に対応する。
この文書にあるその他の機能は、
V2.5.3 Core2でのfixture採取、実装、自動テスト、Web IDE往復、実機確認が終わるまで
「対応済み」とは扱わない。

## 根拠

APIの一次資料は、M5Stack公式[`uiflow-micropython`](https://github.com/m5stack/uiflow-micropython)の
タグ[`2.5.3`](https://github.com/m5stack/uiflow-micropython/tree/2.5.3)、コミット
[`50e440780492aa847378c7d3477ab912f7063bac`](https://github.com/m5stack/uiflow-micropython/commit/50e440780492aa847378c7d3477ab912f7063bac)へ固定する。

Core2／V2.5.3で採取した空プロジェクトの`resources`には、次の内蔵ハードウェア識別子がある。

```json
{
  "hardware": [
    "hardware_button",
    "hardware_pin_button",
    "imu",
    "speaker",
    "touch",
    "sdcard",
    "mic"
  ]
}
```

内蔵デバイスはUnitと異なり、`units`配列へインスタンスを追加する形式ではない。
多くは`from M5 import *`で提供されるグローバルオブジェクトを使い、Blockly側に操作ブロックを置く。
SDカードは`from hardware import sdcard`を追加して初期化する。

公式タグ内のサンプル`.m5f2`にはCoreS3用または古い`versionNumber`のものも多い。
API名とブロック型の候補には使えるが、Core2 V2.5.3の保存形式としてそのまま複製しない。

## 対応対象

### 画面部品

現在の`m5ui.M5Page`方式に統一し、旧`Widgets.Circle`などと混在させない。

| 種類 | Python API | `.m5f2`の中心 | 初期対応 |
| --- | --- | --- | --- |
| テキストラベル | `m5ui.M5Label` | `components[].type = lvgl_label` | 静的配置、文字変更 |
| テキストフィールド | `m5ui.M5TextArea` | `components[].type = lvgl_textarea` | 静的配置、文字設定・追記・消去 |
| 線 | `m5ui.M5Line` | `components[].type = lvgl_line` | 静的な点列、色、太さ |
| 図形描画 | `m5ui.M5Canvas` | Canvas部品＋描画ブロック | 四角形、円弧、線、三角形 |

部品コンストラクターは主に外側JSONの`components`へ変換する。画面読み込み後の`set_text`、
`add_text`、`add_point`などはBlocklyの操作ブロックへ変換する。

このうち`M5Page`一つと`M5TextArea`の静的配置、`set_one_line`、`set_text`、既定状態の
`set_text_color`は最善努力変換へ
実装した。コンストラクターのリテラルまたはトップレベル定数から、位置、寸法、初期文字列、
placeholder、フォント、背景色、枠色、文字色、親ページを`components`へ反映する。文字色はRGB888の
リテラルまたはトップレベル定数、不透明度0～255、`lv.PART.MAIN | lv.STATE.DEFAULT`に対応する。
追記、消去、イベントと他のpart/stateは未対応である。自動テストではJSON部品構造とBlockly参照を確認し、
文字色BlockのXMLとPython生成はCore2を選択したUiFlow2 V2.5.3 Web IDEで確認した。変換済みの
カウント例全体の再読み込みと実機動作は未確認である。

テキストフィールドを配置するだけの対応と、画面上で文字入力する対応は分ける。
入力にはキーボード部品、フォーカス、イベント処理が必要になるため後段で扱う。

### ボタン

公式の[Button API](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/button.rst)では、
Core2は`BtnA`、`BtnB`、`BtnC`を持つ。

初期対応候補は次の通り。

- `BtnA.isPressed()`、`BtnB.isPressed()`、`BtnC.isPressed()`
- `wasPressed()`、`wasReleased()`、`wasClicked()`、`wasDoubleClicked()`、`wasHold()`
- 上記の真偽値を条件にする`if`

このうち`BtnA/B/C.wasPressed()`は、公式Button APIとBtnA／BtnB／BtnCを含む公式サンプル対で確認した
`button_was_pressed`を使い、
最善努力変換の条件式として実装した。BtnA・BtnB・BtnCを同じ入力で変換し、それぞれ異なる
`NAME`値を持つ専用Blockになることを自動テストで確認済みだが、
V2.5.3 Web IDEでの読み込み、Python再生成、実機動作は未確認である。

Blocklyには状態取得ブロックと`button_callback`イベントブロックがある。
最初はLoop内のポーリングを対応し、イベントコールバックはトップレベルイベント構造を扱えるようになってから追加する。

`M5.update()`をLoop先頭で呼ぶというプロファイル条件は維持する。Button APIはこの更新処理へ依存する。

### IMU

公式の[IMU API](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/imu.rst)では、
Core2のIMUはMPU6886で、加速度と角速度を取得できる。

初期対応候補は次の通り。

```python
Imu.getAccel()       # (x, y, z)
Imu.getGyro()        # (x, y, z)
(Imu.getAccel())[0]  # 軸の選択
```

対応Blockly型として`imu_get_accel`と`imu_get_gyro`を公式例で確認した。
戻り値は3要素のタプルなので、値式、添字`0`～`2`、変数代入、表示用の文字列変換が必要になる。

`getMag()`はAPIに存在するが、公式対応表ではCore2のMPU6886に磁気センサーが示されていないため、
Core2実機で有効性を確認するまで対象外とする。

### スピーカー

公式の[Speaker API](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/speaker.rst)では、
Core2はNS4168を搭載し、`Speaker`は`M5`モジュールから提供される。

初期対応はリソースファイルを必要としない操作から始める。

```python
Speaker.begin()
Speaker.setVolume(128)
Speaker.setVolumePercentage(0.2)
Speaker.tone(440, 500)
Speaker.stop()
Speaker.end()
```

値域は公式APIに合わせ、音量は`0`～`255`とする。`setVolumePercentage`は公式生成Pythonで
0.0～1.0、対応するBlockのスライダーで0～100としている。チャンネル指定を追加する場合は
`0`～`7`を検査する。

`playWavFile`は、`.m5f2`だけでなく音声ファイルの配置とパスの扱いを決める必要があるため後段とする。
`playRaw`はバッファ型を実装した後に追加する。

`begin`、`setVolumePercentage`、`tone`は、公式のPython／`.m5f2`サンプル対を根拠に
最善努力変換の専用Blockとして実装した。音量はPython側の0.0～1.0をBlock上の0～100へ換算する。
自動テストではXML構造と換算値を確認済みだが、Core2 V2.5.3 Web IDEでの往復と実機動作は未確認である。

### タッチパネル

公式の[Touch API](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/touch.rst)に基づき、
最初は表示回転を自動反映する単一タッチAPIを対象にする。

```python
M5.Touch.getCount()
M5.Touch.getX()
M5.Touch.getY()
```

これらを使うには、数値式、変数代入、`if M5.Touch.getCount():`、ラベル文字列への変換が必要になる。

`getDetail()`と`getTouchPointRaw()`はタプル構造、複数タッチ、回転前の生座標を扱うため後段とする。
特に生座標は`screen.rotation`との座標変換が必要になる。

### マイク

公式の[Mic API](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/docs/source/hardware/mic.rst)では、
Core2はSPM1423を搭載し、`Mic`は`M5`モジュールから提供される。

対象候補は次の通り。

```python
Mic.begin()
Mic.setSampleRate(8000)
Mic.record(buffer, 8000, False)
Mic.isRecording()
Mic.end()
```

録音には`bytearray`、変数、サンプルレート、録音完了待ち、Speakerとの共有リソース管理が必要になる。
このため、単純呼び出しを追加するだけでは対応できず、後段の複合機能とする。

### SDカード

Core2の空プロジェクトには`sdcard`リソースがある。公式実装は
[`hardware/sdcard.py`](https://github.com/m5stack/uiflow-micropython/blob/2.5.3/m5stack/libs/hardware/sdcard.py)の
`sdcard.SDCard(...)`で`/sd`へマウントする。

初期化引数は機種ごとに異なるため、CoreS3の公式テスト例にあるピンをCore2へ流用しない。
Core2 V2.5.3で生成された初期化コードをfixtureとして採取してから対応する。

初期対応候補は、読み取り中心の次の処理とする。

- 初期化と`/sd`へのマウント
- `os.listdir()`
- ファイルの存在、ファイル／ディレクトリ種別の取得
- テキストファイルの読み取り

書き込み、rename、削除は変換可能性とは別に、試験用ディレクトリを限定して実機確認する。

### その他のCore2内蔵機能

RTC、電源・バッテリー情報、振動モーターなどはCore2のハードウェアとして存在するが、今回採取した
空プロジェクトの`resources.hardware`には個別識別子がない。M5モジュールでのAPI、UiFlow2ブロック、
V2.5.3保存形式を別途確認してから対象へ加える。

## 変換器の構造変更

現在の変換器は、SetupとLoopにある二種類の呼び出しを`(name, integer)`の列として保持する。
内蔵デバイスに対応するには、次の型を表現できる中間表現へ置き換える。

### 文

- 呼び出し文
- 変数代入
- `if`と`if/else`
- 対応範囲を限定した`while`
- イベントハンドラー

### 値式

- 整数、浮動小数、真偽値、文字列、色
- 変数参照
- センサー値を返す呼び出し
- タプル要素の取得
- 比較と論理演算
- 文字列連結と`str(...)`
- `bytearray`生成

ASTから直接XMLを作らず、一度この中間表現へ正規化する。PythonパターンとBlockly型の対応は、
機能ごとの変換規則として登録する。未知のASTは従来どおりエラーにし、部分変換は行わない。

## メタデータ

画面部品のコンストラクターに含まれない設計時属性は、変換用コメントで補う。
候補形式は次の通り。

```python
# uiflow2-component: {"name":"label0","type":"label","layer":1,"page":"page0"}
```

位置、寸法、色、フォント、初期文字列など、Pythonコンストラクターから一意に得られる値は重複指定しない。
`id`、`pageId`、`createTime`、Blockly IDは変換器が新しく割り当てる。

内蔵デバイスは機種プロファイルから存在を決める。Pythonから判断できない初期化属性が見つかった場合だけ、
厳密なJSONコメントを追加する。

## 実装順序

### 段階1: 画面出力と単純な出力デバイス

- `M5Label`、`M5TextArea`、`M5Line`の静的配置
- ラベルとTextAreaの文字設定
- Speakerの`begin`、音量、`tone`、`stop`、`end`
- 既存RGB UnitとSleepとの混在

この段階は、リテラルと直列処理を中心に現在の変換器を拡張できる。

### 段階2: 入力デバイスと値式

- BtnA／BtnB／BtnCの状態取得
- 単純な`if`／`if else`
- Touchの個数、X、Y
- IMUの加速度・角速度と軸選択
- 変数、比較、文字列化、ラベル表示

ここで中間表現を本格的に導入する。

### 段階3: イベントと図形

- ボタンのコールバックイベント
- UI部品のイベント
- Canvasの四角形、円弧、線、三角形
- TextAreaとオンスクリーンキーボードの連携

### 段階4: バッファとストレージ

- Mic録音、録音完了待ち、Speaker再生
- SDカード初期化、一覧、読み書き
- 音声・画像など外部リソースの扱い

## 機能ごとの完成条件

各APIまたは画面部品は、次をすべて満たしたときだけ対応済みとする。

1. 公式タグ2.5.3のランタイムまたは文書でPython APIを確認する。
2. Core2／UiFlow2 V2.5.3で最小ブロックを作成し、`.m5f2`と生成Pythonを採取する。
3. 一属性または一引数だけ変えたfixture差分から保存位置を特定する。
4. 入力Pythonを実行せずASTから変換できる。
5. 自動テストで対応入力と拒否入力、値域、参照IDを検査する。
6. UiFlow2 V2.5.3へImportし、ブロックまたは画面部品として編集できる。
7. UiFlow2から再生成したPythonが対象プロファイルと一致する。
8. Core2 v1.3実機で動作を確認し、使用したfixtureと結果を記録する。

## 実機確認項目

| 機能 | 最小確認 |
| --- | --- |
| Label／TextArea／Line | 指定位置、文字列、色、寸法、線の点列を目視確認 |
| BtnA／BtnB／BtnC | 各ボタンのクリックが一回ずつ区別される |
| Speaker | 指定周波数・時間のtone、停止、音量変更 |
| IMU | 静止時と傾斜時の3軸値、回転時の角速度変化 |
| Touch | rotation 1で画面四隅のX/Yとタッチ数 |
| Mic | 固定秒数録音、録音終了、内蔵Speakerで再生 |
| SDカード | 専用試験ディレクトリで一覧、作成、読み戻し、削除 |

実機試験後は、RGB Unitの検証と同様に本体を通常のUiFlow2起動状態へ戻す。
