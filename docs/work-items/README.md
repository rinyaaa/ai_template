# Work Item

実装する作業1件ごとの正本。`WORK-<slug>.md` に、依頼の原文・受け入れ条件・スコープ・決めたこと・結果（Evidence）・詰まった点を書く。**作業の記録も兼ねる**（別の作業ログは置かない）。

- 作る: `python3 scripts/new_doc.py work <slug> --title "..." [--priority P2] [--issue <URL>] [--depends-on WORK-a]`
- 次にやるもの: `python3 scripts/work_items.py --next`（一覧は引数なし）
- 検査: `python3 scripts/check_records.py`（pre-commit・CI・整合性検査からも走る）
- 過去に同じことがあったか: 開いて読まずに `python3 scripts/new_doc.py grep "<語>|<言い換え>"`

## 決まり

- ID は意味のある固定の slug（`WORK-login-rate-limit`）。連番・日付を入れない。改名しない
- `status`: `backlog`（未整理）→ `ready`（着手できる）→ `in-progress` → `done`。外的な理由で止まったら `blocked` と `blocked_reason`。やめたら `cancelled`
- 並びの制約は `depends_on` に書く。`priority`（P0〜P3）は、依存が片付いたもの同士の順番にだけ使う
- `done` にするのは、受け入れ条件が全部 `[x]` で、`design_impact` を決めたとき（`changed` なら承認済みのADRを `adrs` に、`none` なら `design_impact_reason` に理由）
- GitHub Issue は「やりたいことの入口」、Work Item は「実装の正本」。Issue があれば `issue:` に URL を書く
- 一覧は frontmatter から生成するので、このファイルに索引を書き足さない
