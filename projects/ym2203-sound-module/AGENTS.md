# YM2203公開用プロジェクト

- 公開範囲は採用済みRev C、C SDK0.5.0-alpha.4、P2 T/T/N・FAB Uと、その再現に必要な資料。
- 未採用案・詳細な比較・個人の調達/注文管理は内部作業先で行い、公開差分へ混ぜない。内部作業先のURLは記載しない。
- GPIO・HOST I2C v2・USB-MIDI・STOP/leaseの契約を保持する。変更する場合は利用者の承認と回帰検証を行う。
- 本プロジェクトの独自ソースとCADはMIT。THIRD_PARTY_NOTICES.mdと各ライセンス全文を保持する。
- 楽曲・録音・曲入りBIN/UF2・注文原本・認証情報をGitへ入れない。既定ビルドは独自の13秒診断音階。
- 過去の実機受入、製造・取り込み記録は当時の根拠として保持し、新しい検証結果とは区別する。
- 現在のソース整合性はrelease-manifest.jsonとtools/verify_export.pyで確認する。provenanceの旧ハッシュを現構成に合わせて再計算しない。
- 検証手順はREADME.mdとhardware/p2/README.md。旧レビューや内部作業先を必須依存にしない。
- P2は発注済み・HAL未移植・実機未受入。Rev CのUF2をP2へそのまま使わない。
- Node/pnpmは.node-versionとpackage.jsonを正本とし、Nodeコマンドはscripts/use-node.sh経由とする。
- 公開履歴を書き換えず、通常のcommit/pushで更新する。
