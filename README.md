# asamomijijp-code

[asamomiji.jp](https://asamomiji.jp/)の記事に付随する公開用ソースコードを管理するリポジトリです。記事中の短いコード例ではなく、複数ファイルからなる完全版、検証用コード、過去にGitで管理されていなかった自作プログラムを主な対象とします。

コードは記事単位で`projects/<article-slug>/`へ配置します。歴史的コードについては、原作成時期、収録時の変換、検証環境、既知の制約を各プロジェクトのREADMEに記録します。

詳細は[リポジトリ運用方針](docs/repository-policy.md)を参照してください。

## 収録プロジェクト

- [MMLプレイヤー](projects/mml-player/README.md) — 2002年に作成したJava製MMLプレイヤーの歴史的ソースコード
- [micro:bit 5-queen](projects/microbit-five-queens/README.md) — 2018年にPythonとC++で5-queen問題を解いた実験コード

## ライセンス

所有者が作成して本リポジトリで公開するコードは、個別の明示がない限り[BSD 2-Clause License](LICENSE)に従います。第三者コードや別ライセンスの対象は、各プロジェクトで個別に明示します。
