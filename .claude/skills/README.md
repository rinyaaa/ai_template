# Skills

手順書（スキル）の**正本**。各スキルは `<skill-name>/SKILL.md` に frontmatter（`name`, `description`）と手順を書く。Codex・Cursor 向けの入口（`.agents/skills/`・`.cursor/rules/agents.mdc`）は `python3 scripts/sync_agent_adapters.py` が生成するので、手で作らない。

スキルの作成・改善・評価には `skill-creator` スキル（`/example-skills:skill-creator`）を使うと良い。

## 一覧

| スキル | 概要 | 使うスクリプト |
|---|---|---|
| [claude-project-setup](claude-project-setup/SKILL.md) | AI用の設定（権限・hooks・CLAUDE.md・skill/command/agent）を対話でセットアップ。詳細は `references/` | `detect_stack.py` |
| [safe-rollback](safe-rollback/SKILL.md) | 壊れた・戻したいときの復旧。破壊的コマンドを使わず、退避→切り分け→revert/切り戻し | `rollback_snapshot.py` |
| [go-live-checklist](go-live-checklist/SKILL.md) | 公開前の監査。リスクレベル判定・棚卸し・`/security-review` | `golive_scan.py` |
| [project-health-check](project-health-check/SKILL.md) | 定期点検。Dependabot・アラート・CI失敗・脆弱性・放置ブランチを優先度付きで報告 | `health_check.py` |
| [import-skills](import-skills/SKILL.md) | 外部リポジトリのスキルを、信用できないコード前提で監査してから取り込む | `audit_skill_import.py` `scan_agent_content.py` |
| [task-intake](task-intake/SKILL.md) | 着手前に依頼の原文・スコープ・受け入れ条件を固め、Work Item（と必要なら Issue）にする。次の作業も出す | `new_doc.py work` / `adr`・`work_items.py` |
| [implementation-review](implementation-review/SKILL.md) | 差分を Work Item・依頼の原文・ADR と突き合わせて受け入れ判定。規模で深さを変え、再レビューは修正分だけ | `review_bundle.py` |
| [work-log](work-log/SKILL.md) | Work Item に結果と詰まった点を書いて完了にし、効く知見を CLAUDE.md・スキルへ昇格させる | `check_records.py`・`new_doc.py grep` |
| [parallel-worktree](parallel-worktree/SKILL.md) | 複数機能を git worktree で並列実装するときの分割判定・セットアップ・後始末。既定は直列 | `worktree_setup.py` |
| [night-run-hearing](night-run-hearing/SKILL.md) | 夜間自律実行の対象issue・締切をヒアリングし、stateファイルか実行プロンプトを作る | `night-run/plan_night.py` |
| [night-run-status](night-run-status/SKILL.md) | 夜間自律実行の進捗・結果を読み取り専用で棚卸し | `night-run/status.py` |
| [ui-guidelines](ui-guidelines/SKILL.md) | UI実装時のタッチ操作対応とコントラストの規範。初期パレットは差し替え前提 | — |
| [doc-index](doc-index/SKILL.md) | ドキュメント索引の1行の型と適用手順 | — |

## スキルを書くときの決まり

- **description は発動条件だけ。** 全スキル分が毎回読み込まれ、その中から1つを選ぶので、説明で膨らむと選ぶ精度が落ちる。口語のトリガー語（「壊れた」「公開したい」）は削らない
- **本文は手順と判断基準だけ。** 背景説明・場合分けの詳細は `references/` に分け、本文の表に「いつ読むか」を書く
- **毎回同じになる手順はスクリプトにする**（`scripts/`、一覧は `scripts/README.md`）。スキルにはコマンドと、スクリプトが判断しないことだけを書く
- 足したら: この表に1行 → `python3 scripts/sync_agent_adapters.py` → `python3 scripts/context_cost.py --ref main` で常時ロードの増減を確かめる
