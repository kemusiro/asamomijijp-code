# 同梱ライブラリ

## Planck.js 1.3.0

- 出典：<https://github.com/piqnt/planck.js>
- npm固定版：<https://www.npmjs.com/package/planck/v/1.3.0>
- 取得元：`https://registry.npmjs.org/planck/-/planck-1.3.0.tgz`
- tarball SHA-256：`36741b664e1e5b779313c246778c8ac9ac2679309c0094d10f671513ded956be`
- 同梱：`package/dist/planck.mjs` → `vendor/planck.mjs`、`package/LICENSE.txt` → `vendor/PLANCK-LICENSE.txt`
- 変更：未同梱のsource mapを指す末尾の`//# sourceMappingURL=`行だけを除いた。物理エンジン本体は変更していない。
- ライセンス：MIT。Erin Catto、Ali Shakibaの著作権表示と許諾文を[そのまま同梱](vendor/PLANCK-LICENSE.txt)。

1.3.0のNode.js対応は14以上。既存展示のNode.js 22に合わせてこの版を固定した。
testbed・stage-js・画像・外部フォントは使用しない。Node.jsとブラウザで同じcore ES moduleを読み込む。
アプリ、コース生成、遺伝的アルゴリズム、画面は本リポジトリで実装した。

概念上の参考例：[HTML5 Genetic Cars](https://github.com/red42/HTML5_Genetic_Cars)。この既存デモのコード・画像はコピーしていない。
