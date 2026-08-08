# micro:bit 5-queen

2018年に初代micro:bitで5-queen問題を解く実験を行った際の、Python版とC++版のソースコードです。

- 新サイトの記事（公開予定）: [micro:bitで5-queen問題を解いた記録（2018年）](https://asamomiji.jp/articles/microbit-five-queens/)
- 旧記事: [micro:bitで5-queen問題を解く](https://asamomiji.jp/blog/solve-5-queen-problem-using-microbit/)
- 旧公開日: 2018年1月20日
- Git収録日: 2026年8月9日
- 当時の対象: 初代micro:bit
- 当時の環境: micro:bit用Pythonエディターv1、Arm Mbed Online Compiler、micro:bitランタイム（正確な版は不明）

これは2018年の歴史的な実験コードです。現在のmicro:bit開発環境向けに保守された作例ではなく、現行環境でのビルドと実機動作は確認していません。

## 収録内容

```text
microbit-five-queens/
├─ .gitattributes
├─ .gitignore
├─ README.md
├─ SHA256SUMS
├─ SOURCE_PROVENANCE.md
├─ original/
│  ├─ cpp/main.cpp
│  └─ python/main.py
└─ corrected/
   └─ python/main.py
```

- `original/`: 旧WordPress記事のコードブロックをHTML実体参照から復号した原版
- `corrected/python/main.py`: 移行レビューで確認した2点だけを直したPython修正版

C++原版には同じ2点の不備がないため、C++修正版は作成していません。

## Python修正版の変更

`corrected/python/main.py`には、原版に対して次の変更だけを加えています。

1. 再試行時の初期化で、乱数が0以下のマスを`v[i] = 0`へ戻す。
2. 1試行を100反復とする総反復数の計算に合わせ、`range(1, 100)`を`range(1, 101)`へ変更する。

実機動画は原版で撮影されたものとして扱います。修正版の性能や実機動作を示すものではありません。

## 検査

2026年8月9日に次の検査を行いました。

- Python 3.14.6の`py_compile`による原版・修正版の構文検査: 合格
- 原版と修正版の差分: 上記2変更だけであることを確認
- APIキー、トークン、パスワード、秘密鍵、ネットワーク接続先: 該当なし
- ハードウェア表示を除いて更新処理を独立に再現した補助検査: 決定的な疑似乱数seed 1〜1000の停止時配置が、原版相当・修正版相当とも5-queen条件を満たすことを確認

`py_compile`は`microbit`モジュールの存在や実行を確認しません。C++原版は旧`MicroBit.h`と当時のランタイムへ依存するため、現行コンパイラーでは検査していません。補助検査も元の処理系、乱数、浮動小数、実機表示を再現するものではなく、収束や性能を保証しません。

## 既知の制約

- 当時のMicroPython、micro:bitランタイム、C++コンパイラーの正確な版は不明です。
- C++原版は可変長配列などGNU拡張に依存します。
- C++原版の`error()`置換は、当時バイナリサイズを減らそうとした実験であり、現在推奨する方法ではありません。
- Arm Mbed Online Compilerは廃止されています。
- Python版とC++版の動画は、条件を統制して時間を測ったベンチマークではありません。

## ライセンス

このプロジェクトは、リポジトリのルートにある[BSD 2-Clause License](../../LICENSE)に従います。
