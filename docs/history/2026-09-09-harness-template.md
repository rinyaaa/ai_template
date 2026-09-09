# 2026-09-09 作業ルール（ハーネス）のテンプレート化

## やったこと

実プロジェクトで使っていた作業ルール `CLAUDE.md`（計画→実装→レビュー→完了の5フェーズ、worktree並列、レビュー採点、UI配色仕様、ドキュメント索引の型／約5,000〜6,000トークン）を、このテンプレートの「薄い常時ロード＋必要時ロードのスキル」構造に載せ替えた。

- `AGENTS.md` に「作業の進め方」を約15行で追加。安全ルール1に `git worktree remove` / `prune` を追加
- 新規スキル5本: `implementation-review` / `work-log` / `parallel-worktree` / `ui-guidelines` / `doc-index`
- `github-task-intake` → `task-intake` に改名し、出力先（GitHub Issue / 計画書 / 両方）で分岐する形に統合
- 既存8スキルの `description` をトリガー条件だけに短縮（2,153 → 1,422文字）
- `.claude/settings.json` の deny・hook・`verify_safety_net.py` に worktree 削除を追加
- `CLAUDE.md` にプロジェクト固有の穴埋め欄（ビルド/実行/テスト・アーキテクチャ・レイヤー構成・固有の約束事）を新設
- `docs/plans/` `docs/history/` を新設

常時ロード量（`AGENTS.md` + `CLAUDE.md` + 全description）は **5,206 → 5,115文字（−91）**。スキルは8本→13本。

## 詰まった点 / 解決方法

- **新スキルを足すと常時ロードが増える。** 追加した中核（AGENTS.md +671文字）と新規5本の description が、既存短縮分を食い潰して一度 +43文字になった。**原因は description に本文と同じ説明を書いていたこと**。description は発動条件だけに絞り、説明は本文へ移して −91文字に転じた。スキルを足すときは毎回この計測をする（`AGENTS.md` + `CLAUDE.md` + 全descriptionの文字数を `git show HEAD:<path>` と比較）
- **「型を決める側」と「型を参照する側」がずれた。** `task-intake` が出力する欄は「スコープ: 含むこと / 含まないこと」の1欄だったのに、`AGENTS.md` と `docs/plans/README.md` は「スコープ / スコープ外」と呼び、しかも「欄名を変えるな」と書いていた。生成されない見出しを名指しで固定していたことになる。**出力側を2欄に分割して解消。** 型を決めたら、それを参照する箇所を grep して実際の出力と突き合わせる
- **deny の追加を片方にしか入れていなかった。** `settings.json` には2件（remove / prune）、`verify_safety_net.py` の `REQUIRED_DENY` には1件しか入れておらず、派生プロジェクトで `prune` の deny が消えても検査が素通りする穴を作っていた。**安全網は「実際に効く場所」と「消えていないか検査する場所」の両方を必ず対で更新する**

## 次回への申し送り・知見

- **description は全スキル分が毎セッション常時ロードされる固定費、本文は発動時にしか読まれない。** スキルが増えるほど description の肥大が効いてくるので、追加時は必ずトリガー条件だけに絞る
- **description からトリガー語を削ると発動精度が落ちる。** 短縮は説明文だけを対象にし、口語のトリガー語（「壊れた」「公開したい」「issueを切りたい」等）は残す → `.claude/skills/README.md` に昇格済み
- **未検証**: 新規セッションでの発動確認（description短縮と改名の副作用）、`task-intake` の計画書出力の実走、空ディレクトリでの `claude-project-setup` 通し。いずれも静的検査では代替できないので、次に触るときに実施する
- `ui-guidelines` の初期パレットは移植元のものをそのまま使っている。ブランドカラーが決まっているプロジェクトでは差し替える前提（手順はスキル内）
