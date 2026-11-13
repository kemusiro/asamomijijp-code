# ChatGPTへの楽曲変換依頼の例

ChatGPTなどへVGM／VGZファイルを添付し、下の文章をコピーして曲名・機種名を書き換えます。
Codexやリポジトリの取得は不要です。イースIIなどでも機種まで指定してください。
録音や曲名だけでは、元のFM音色とレジスタ列を正確に復元する入力として不足します。

参照資料は次の3つです。プロンプトにも同じリンクを含めています。

- [WYM1 BIN仕様書](https://raw.githubusercontent.com/kemusiro/micropython-web-lab/main/docs/devices/ym2203-bin-format.md)
- [汎用BINプレイヤー：web_lab_ym2203_bin_v1.py](https://raw.githubusercontent.com/kemusiro/micropython-web-lab/main/src/drivers/web_lab_ym2203_bin_v1.py)
- [音源ドライバー：web_lab_ym2203_v1.py](https://raw.githubusercontent.com/kemusiro/micropython-web-lab/main/src/drivers/web_lab_ym2203_v1.py)

リンクを読めないと回答された場合は、リンク先を保存して3ファイルを添付します。
ファイル生成を実行できない場合は、その制約を確認してください。

~~~text
添付のVGM/VGZを、MicroPython WebLabで再生できるWYM1形式のBINへ変換してください。
曲名: <曲名>
機種: <機種名>
目的: 手元での再生テスト。入力ログを先頭から終端まで1回再生します。

次の仕様と既存プレイヤーを読み、仕様に従って変換・検証してください。
仕様: https://raw.githubusercontent.com/kemusiro/micropython-web-lab/main/docs/devices/ym2203-bin-format.md
プレイヤー: https://raw.githubusercontent.com/kemusiro/micropython-web-lab/main/src/drivers/web_lab_ym2203_bin_v1.py
ドライバー: https://raw.githubusercontent.com/kemusiro/micropython-web-lab/main/src/drivers/web_lab_ym2203_v1.py

成果物はダウンロード可能なproject.zipにしてください。
main.py、music/song.bin、lib/の上記2ファイル、conversion.json、取り込み手順のREADME.txtを含めます。
既存プレイヤーをそのまま使い、元の音色・時刻・書き込み順序を保持してください。
出典、SHA-256、検証結果、再現できない点も報告してください。
リンクを読めない、変換を実行できない、入力が仕様に対応しない場合は、理由と不足資料を示してください。
~~~

生成されたZIP・変換記録を確認し、手元のWebLabでも再生を試します。
ZIP取り込みは既存プロジェクトを置き換えるため、先にZIPで保存してください。
再生時はYM2203を結線し、スピーカーのミュートを解除します。
この例は個人の再生テスト用です。生成ファイルの公開・再配布条件は別途確認してください。

リポジトリで作業する場合の保存先は`local-test-data/ym2203/<test-name>/`です。
BIN、入力ログ、再生用コード、変換記録、ZIPをまとめて置きます。このディレクトリ全体は
Gitの追跡対象外です。ZIP内の`music/song.bin`はMicroPython側のパスです。
