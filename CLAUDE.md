# CLAUDE.md
<!-- メタルール: ここはルーティング層。説明・例・理由を書かない（毎回読み込まれるため）。
     全ツール共通のルールは AGENTS.md、詳しい説明は docs/ に置き、下の表に1行で指す。80行以内。 -->

@AGENTS.md

## プロジェクト固有の情報（派生プロジェクトで埋める）

### ビルド / 実行 / テスト
<!-- ポートの変え方も書く（parallel-worktree が読む） -->
- インストール:
- 起動:
- テスト:
- lint / format:

### アーキテクチャ / レイヤー構成
<!-- 各層に置くものと「置かないもの」（例: SQLは repository/ だけ） -->

### 固有の約束事
<!-- 命名・コミット規約・配色など。レビュー観点になる -->

## Docs

| 内容 | パス | 読むとき |
| --- | --- | --- |
| スキル一覧と発動条件 | `.claude/skills/README.md` | スキルを足す・どれを使うか迷う時 |
| ルールの理由・ツールごとの強制力 | `docs/agent-rules-rationale.md` | 安全ルールや hook を変える時 |
| Work Item | `docs/work-items/` | 作業を始める時（該当する1件だけ。次の作業は `work_items.py --next`） |
| ADR | `docs/decisions/` | 構成・ツール・ワークフローを変える時 |
| 夜間の自律実行 | `night-run/README.md` | night-run を設定・実行する時 |

## Claude Code での強制

- 安全ルール1・2と検査の回避（`--no-verify` 等）は `.claude/settings.json` の deny と `.claude/hooks/deny_dangerous_bash.py`（PreToolUse）で止まる。パターンを変えたら `python3 .claude/hooks/test_deny_dangerous_bash.py`。
- 安全網のファイルを変えたまま止まると、`.claude/hooks/stop_verify.py`（Stop）が整合性検査を走らせ、失敗なら1回差し戻す。
- スキルは発動条件で自動的に読まれる。スキルを足し引きしたら `python3 scripts/sync_agent_adapters.py`。
