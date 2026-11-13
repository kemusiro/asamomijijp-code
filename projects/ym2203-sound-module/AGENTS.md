# YM2203実基板プロジェクト

- 本ディレクトリが実基板・診断・ファームウェアの正本。WebLabアプリの変更を混ぜない。
- 最終目標はWebLabと同じYs IIの全曲再生。現行のMicroPython初期受入は途中段階。
  C SDK移行の方針は`hardware/ym2203-single-board/firmware/YSII-PLAYBACK-PLAN.md`を読む。
- GPIOはユーザー承認済み。変更する場合は実装前に確認する。
- プロジェクト全体はMIT。移行先ルートの既定ライセンスで元の表示を置換しない。
- 楽曲、曲入りUF2、BIN/VGM/VGZ/ZIPは`local-test-data/`などGit管理外へ置く。
- 過去の配布物・実機記録を上書きして結果を捏造しない。モデル試験と実機確認を分ける。
- Node版は`.node-version`、pnpm版は`package.json`を正本とし、Nodeコマンドは
  `./scripts/use-node.sh`を使う。変更に関係する検査はREADMEの手順に従う。
- `migration.json`は取り込み時点のスナップショット。今後の機能変更では取り込みハッシュを
  書き換えず、`tools/verify-migration.py`は移行時コミットでの照合用と理解する。
