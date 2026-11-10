# scripts

AIが毎回同じ手順を手で繰り返す代わりに使うスクリプト。どれも出力は数行の要約で、AIはそれだけを読む。標準ライブラリだけで動く（`python3` があればよい）。

| スクリプト | 使う場面 | 書き換えるもの |
| --- | --- | --- |
| `verify_safety_net.py` | 安全網（deny・hook・スキル・CI・アダプター）の整合性。Stop hook・pre-commit・CIからも走る | なし |
| `scan_agent_content.py` | 不可視文字・双方向制御文字・指示の乗っ取りの検出（`--all` / `--staged` / パス） | なし |
| `sync_agent_adapters.py` | スキルを足し引きしたあと。Codex（`.agents/skills/`）・Cursor（`.cursor/rules/`）の入口を生成（`--check` で検査だけ） | 生成物だけ |
| `context_cost.py` | AGENTS.md・CLAUDE.md・スキルを変えたあと。常時ロードの文字量を測る（`--ref main` で比較） | なし |
| `detect_stack.py` | スタック・パッケージマネージャ・lint/test/audit コマンドの検出（claude-project-setup） | なし |
| `health_check.py` | 定期点検の収集と仕分け（project-health-check） | なし |
| `review_bundle.py` | レビュー材料の束ねと深さの判定、再レビューの材料（implementation-review） | `.git/ai-review/` だけ |
| `rollback_snapshot.py` | 壊れたときの把握と退避（safe-rollback。`--save` で backup/ ブランチを作る） | ブランチの追加だけ |
| `golive_scan.py` | 公開前の機械的な棚卸し（go-live-checklist）。`--staged` でコミットする中身の秘密情報だけを見る（pre-commit） | なし |
| `new_doc.py` | Work Item・ADR を型どおりに作る / 過去の Work Item の検索（task-intake・work-log） | `docs/work-items/` `docs/decisions/` |
| `work_items.py` | Work Item の一覧と、次にやる作業（`--next`） | なし |
| `check_records.py` | Work Item と ADR の決まり（状態・依存・置き換え・必須の見出し）。`--staged` で承認済みADRの書き換えも（pre-commit） | なし |
| `worktree_setup.py` | 並列実装のワークツリー作成と依存のインストール / 後始末の候補の列挙（parallel-worktree） | ワークツリーとブランチの追加だけ |
| `audit_skill_import.py` | 外部スキルの取り込み前の監査（import-skills） | なし |

night-run 用は `night-run/plan_night.py`（ヒアリングの成果物）と `night-run/status.py`（進捗の棚卸し）。

テストは `python3 -m unittest discover -s scripts/tests`。スクリプトを足したらこの表に1行足す。
