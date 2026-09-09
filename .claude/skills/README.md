# Skills

このディレクトリには、このリポジトリ専用のClaude Codeスキル（`SKILL.md`）を置く。各スキルはサブディレクトリとして配置し、`<skill-name>/SKILL.md` にfrontmatter（`name`, `description`）と手順を記述する。

スキルの作成・改善・評価には `skill-creator` スキル（`/example-skills:skill-creator`）を使うと良い。

## 一覧

| スキル | 概要 |
|---|---|
| [claude-project-setup](claude-project-setup/SKILL.md) | プロジェクトにClaude Code用の`.claude/`環境（権限・hooks・プラグイン設定、CLAUDE.md、必要に応じたskill/command/agentの雛形）を対話形式でセットアップする。GitHub利用時はCI・Dependabot・ブランチ保護の整備にも対応。 |
| [safe-rollback](safe-rollback/SKILL.md) | 「壊れた」「元に戻したい」となったときの復旧ワークフロー。破壊的コマンドを使わず、退避→切り分け→revert/切り戻しの順で安全に回復する。 |
| [go-live-checklist](go-live-checklist/SKILL.md) | アプリを公開・リリースする前の監査。リスクレベルを判定し、秘密情報・認証認可・露出面・データ運用を棚卸しして `/security-review` まで実行する。 |
| [project-health-check](project-health-check/SKILL.md) | 「健康診断して」で発動する定期点検。Dependabot PR・セキュリティアラート・CI失敗・依存の脆弱性・放置ブランチを棚卸しし、優先度付きで報告する。週1回の実行を推奨。 |
| [import-skills](import-skills/SKILL.md) | 外部Gitリポジトリからスキルを取り込む。信用できないコード前提で監査し、危険なものは人間の確認を得るまでコピーしない。 |
| [task-intake](task-intake/SKILL.md) | 着手前にスコープ・受け入れ条件を人間と固め、GitHub Issue または計画書(`docs/plans/`)として出力する。ヒアリングは共通で、最後の出力先だけを選ぶ。 |
| [night-run-hearing](night-run-hearing/SKILL.md) | 夜間自律タスク実行(`night-run/`)の対象issue・締切をヒアリングし、実行用のstateファイルまたは実行プロンプトを生成する（実装・PR作成は行わない）。 |
| [night-run-status](night-run-status/SKILL.md) | 夜間自律タスク実行の進捗・結果(done/failed/draft PR)を読み取り専用で棚卸しして報告する。 |
| [implementation-review](implementation-review/SKILL.md) | 実装差分を計画書・スコープと突き合わせて受け入れ判定する。変更規模に応じてセッション内レビューと `.claude/agents/` の専用レビュー担当を使い分け、観点ごとに満たす/満たさないを判定する。再レビューはチケットの範囲だけを軽いモデルで確認する。 |
| [work-log](work-log/SKILL.md) | 終わったタスクを `docs/history/` に日報形式で残し、効く知見を1行に削ってCLAUDE.mdやスキルへ昇格させる。history自体は読まれない前提の置き場所。 |
| [parallel-worktree](parallel-worktree/SKILL.md) | 複数機能を git worktree に分けて並列実装するときの、分割判定・ツリーのセットアップ・後始末の手順。既定は直列で、ユーザーが明示的に並列を求めたときだけ使う。 |
| [ui-guidelines](ui-guidelines/SKILL.md) | UI実装時のタッチ操作対応（ホバー依存の禁止・44×44px）とコントラストの規範。配色は差し替え前提の初期パレットを持つ。 |
| [doc-index](doc-index/SKILL.md) | ドキュメント索引の1行の型（参照タイミングか扱わない範囲を必ず書く）と適用手順。ドキュメントを追加・削除したら同じコミットで索引を更新する。 |

新しいスキルを追加したら、この表にも1行追記すること。frontmatterの `description` は**トリガー条件（いつ発動すべきか）だけ**に絞り、手順や説明は本文に書く。理由はトークン量ではなく**発動精度**——全スキル分のdescriptionが並んだ中から1つを選ぶので、説明で膨らむほど「どれを呼ぶべきか」の判断材料が薄まる。文字数そのものは気にしなくてよい（常時ロード全体でもレビュー1回の数%）。

短縮するときに削ってよいのは説明文だけで、**口語のトリガー語（「壊れた」「公開したい」「issueを切りたい」等）は残す**。発動条件そのものなので、削ると呼ばれなくなる。
