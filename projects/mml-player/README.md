# MMLPlayer

2002年に作成・公開したJava製MMLプレイヤーのソースコードを、歴史的資料として再収録したものです。

- 新サイトの記事（公開予定）: `https://asamomiji.jp/articles/mml-player-archive/`
- 旧記事: `https://asamomiji.jp/blog/mml-player/`
- 原作成期間: 2002年5月12日〜2002年6月30日
- Git収録日: 2026年8月8日
- 原テスト環境: J2SDK 1.4.1 Beta、Windows XP Home

これは現在保守されている音楽ソフトウェアではありません。古いJava APIと`JApplet`を含み、現行環境での実行、安全性、音声出力の正しさは保証しません。

## 収録内容

```text
mml-player/
├─ .gitattributes
├─ README.md
├─ SOURCE_PROVENANCE.md
├─ SHA256SUMS
├─ examples/
│  └─ fmparameters.txt
└─ src/
   └─ jp/or/rim/kt/kemusiro/sound/
```

- `src/`: UTF-8へ変換したJavaソース41件
- `examples/fmparameters.txt`: 旧配布物に含まれていたFM音源パラメータ例
- `SOURCE_PROVENANCE.md`: 原資料、文字コード変換、検査結果
- `SHA256SUMS`: `src/`と`examples/`にある公開ファイルのSHA-256

旧JAR、アプレット用HTML、原資料アーカイブ、コンパイル生成物は収録していません。

## コンパイル確認

2026年8月8日にJDK 20.0.2を使い、次の静的コンパイルを実施しました。

```sh
mkdir -p build/classes
find src -type f -name '*.java' -print0 \
  | xargs -0 javac -encoding UTF-8 -Xlint:all -d build/classes
```

結果はコンパイルエラー0件、警告27件、生成クラス45件でした。主な警告は次のとおりです。

- `JApplet`が削除予定であること
- `Window.show()`が非推奨であること
- raw型とunchecked操作
- `serialVersionUID`がないこと
- staticメソッドをインスタンス経由で呼び出していること

コンパイルできることだけを確認しており、生成クラスや旧JARは実行していません。

## ライセンス

このプロジェクトは、リポジトリのルートにある[BSD 2-Clause License](../../LICENSE)に従います。各Javaファイルの`@author`表示は原資料から保持しています。
