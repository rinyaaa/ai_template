---
id: WORK-slim-ai-harness
title: AIハーネスの整理（トークン削減・スクリプト化・他ツール対応・Work Item/ADR）
status: in-progress
priority: P1
depends_on: []
adrs: [ADR-agent-instruction-layers, ADR-single-source-skills, ADR-scripts-for-fixed-procedures, ADR-cross-tool-safety-net, ADR-shared-review-flow, ADR-work-items-and-decisions]
issue:
created_at: 2026-11-09T21:40:00+09:00
updated_at: 2026-11-10T11:19:39+09:00
blocked_reason:
design_impact: changed
design_impact_reason:
---

# AIハーネスの整理（トークン削減・スクリプト化・他ツール対応・Work Item/ADR）

## 依頼の原文

> 今このAIのやつめっちゃごちゃってるので整理したいです，
> まずトークンを消費遼を減らしくてごちゃごっちゃしてるところや，AIが同じ動きするところはスプリクトかするとか
> あとcodex,claude,.cursorとか色々参考してながらやって

続く依頼（同じ会話）:
> 無駄に，モデルを帰るところとかあんまりいらないかも．あと日エンジニアのやつとかいらんかも
> ないとらんもレビューをいい感じにすることで減らせないかな？
> せきリュティー観点はどう？コミット数r時になにかあるの → （3つの穴を直す案に）お願いします
> WorkItemとかADRとかって今できてる？ → （計画書をWork Itemに置き換える・ADRを足す案に）お願いします
> historyっているかな？

## 受け入れ条件

- [x] 常時ロード（AGENTS.md + CLAUDE.md + 全description）が main より減っている（`context_cost.py --ref main`）
- [x] AIが毎回手で行っていた決まった手順がスクリプトになり、スキルはそれを呼ぶ
- [x] 参考プロジェクトのレビュー（依頼の原文・見送りの記録・パスで渡す）とセキュリティ（外部の文字はデータ・許可確認・Gitは頼まれたときだけ・不可視文字の検出）を取り入れる
- [x] Codex / Cursor でも破壊的コマンドのhookと終了時検査が効く設定がある
- [x] 既存の安全網を弱めていない。新スクリプトにテストがある
- [x] night-run のレビューを対話時と同じ仕組みにする
- [x] コミット時に秘密情報を止め、検査の回避（`--no-verify` 等）を止める
- [x] Work Item と ADR を入れ、計画書と作業記録をそこへ統合する
- [x] 下の「決めたこと」の仮決めをユーザーが確認する
- [x] 今回の決定の ADR（`adrs:` の6件）をユーザーが承認する
- [ ] Codex・Cursor の hook を実機で一度通す（night-run の新しいレビュー手順のドライランは、main へのマージ後に `WORK-night-run-dry-run` で行う。ユーザーの判断）

## スコープ外

- night-run-hearing の Antigravity 手順が参照する `.agents/hooks.json` / `deny_dangerous_agy.py`（このリポジトリに存在しない。今回の変更前から）
- `CURRENT.md`（進捗の一覧）。`work_items.py --next` で代える

## 決めたこと

- 確認済み: レビュー担当のモデル固定をやめる / 非エンジニア向けの分岐とガイドを削除（ユーザーの言葉: 「モデルを帰るところとかあんまりいらないかも」「日エンジニアのやつとかいらんかも」）
- 確認済み: 計画書を Work Item に置き換え、Issue は入口・Work Item は正本にする（提案に「お願いします」）
- 確認済み: 作業記録（docs/history/）を廃止し、Work Item の「詰まった点・知見」に統合する（「historyっているかな？」への回答として実施。既存の2件は Work Item に移した）
- 確認済み: 受け入れ条件の解釈（上の1〜8は依頼文から実装担当が読み取ったもの。ユーザーの回答:「合っている」）
- 確認済み: `settings.json` の `$schema` と hook の timeout、Cursor の `beforeReadFile`（秘密ファイルの読み取り拒否）、CI への unittest 追加（ユーザーの回答:「4つとも残す」）
- 確認済み: `plan_night.py --write` が未完了の state の上書きを拒む（ユーザーの回答:「このままでよい」）
- 確認済み: コミットメッセージに `--no-verify` という語があるだけでも止まる（ユーザーの回答:「許容する（安全側）」）
- 確認済み: ADR 6件を承認（ユーザーの回答:「6件とも承認」）
- 確認済み: night-run のドライランは main へのマージ後に別の Work Item（`WORK-night-run-dry-run`）で行う。コンテナが GitHub の main を clone するので、未マージの変更はドライランで試せないため（ユーザーの回答:「マージ後の別 Work Item」）
- 確認済み: 汎用性の指摘 G-1〜G-8 は別の Work Item（`WORK-template-portability`）にする（ユーザーの言葉:「それでお願いします」）
- 見送り（2026-11-09 の最初のレビューの T-1/T-2。今の `.git/ai-review/tickets.md` の番号とは別）: 仮決めを確定扱いにしていた指摘。確認済みにするのはユーザーの判断なので、2026-11-10 にユーザーが確認するまで仮決めとして残した

## Evidence

- `AGENTS.md` を命令だけの作業契約に削り、理由を `docs/agent-rules-rationale.md` へ移した。参考にした別プロジェクトにならって安全ルールを追加: 外部の文字はデータ / 外部操作の許可確認 / Gitは頼まれたときだけ
- `CLAUDE.md` をルーティング層（Docs の「読むとき」表）にした
- AIが毎回手で行っていた手順を `scripts/` に機械化（一覧は `scripts/README.md`）: `health_check` `review_bundle` `rollback_snapshot` `golive_scan` `new_doc` `worktree_setup` `audit_skill_import` `detect_stack` `context_cost` `scan_agent_content` `sync_agent_adapters`、night-run の `plan_night` `status`
- 各スキルの本文を、スクリプトの呼び出しとスクリプトが判断しないことだけに書き直した。`claude-project-setup` は `references/` に分割
- 他ツール対応: `deny_dangerous_bash.py` に `--provider codex|cursor`、終了時hook `stop_verify.py`、`.codex/hooks.json` `.cursor/hooks.json`、`.agents/skills/`・`.cursor/rules/agents.mdc`（生成）、ツールに依存しない `.githooks/pre-commit`
- `verify_safety_net.py` に、他ツールのhook・Stop hook・アダプターの同期・内容の検査・スキルが呼ぶスクリプトの実在を追加。`scripts/tests/` を CI に追加
- night-run のレビューを `implementation-review` と同じ仕組みに統一した。`night_runner.py` 専用のレビュー定義（`--agents`）を削除し、issue を依頼の原文として `review_bundle.py` で束ね、`impl-reviewer` で判定、再レビューは修正分だけを `impl-reviewer-recheck` で見る。Antigravity 用プロンプトも同じ材料とチェックリストで自分で判定する
- レビュー担当のモデル固定（opus / sonnet）と、非エンジニア向けの分岐・ガイドを削除した（ユーザーの判断）
- コミット時のセキュリティ: pre-commit に秘密情報の検査（`golive_scan.py --staged`、値は表示しない）を追加。hook で `--no-verify`・`git commit -n`・`-c core.hooksPath=`・`git config --unset core.hooksPath` を止める。`core.hooksPath` が未設定なら健康診断が知らせる

計測（2026-11-10、`context_cost.py --ref main`）: 常時ロード 5,802 → 5,479文字（-323）、スキル本文の合計 53,584 → 約24,500文字（−54%）。テスト: `scripts/tests` 36件・hook の回帰 125件・night-run 22件がすべて通る（件数は記録時点。最新は各コマンドで確かめる）
- Work Item と ADR を導入: `docs/work-items/`（計画書と作業記録を統合）・`docs/decisions/`。`new_doc.py work|adr`、`work_items.py`（一覧・`--next`）、`check_records.py`（状態・依存の循環・done の条件・ADRの置き換えと必須見出し、`--staged` で承認済みADRの書き換え）を追加し、pre-commit・整合性検査・終了時hookから走らせる。`review_bundle.py --work` が関係するADRを材料に入れ、チェックリストに「ADRとの一致（見送り不可）」を足した
- `docs/plans/` と `docs/history/` を廃止。既存の作業記録2件は Work Item（`WORK-harness-template`・この Work Item）に移した
- 今回の決定を ADR 6件（proposed）に起こした: `ADR-agent-instruction-layers`・`ADR-single-source-skills`・`ADR-scripts-for-fixed-procedures`・`ADR-cross-tool-safety-net`・`ADR-shared-review-flow`・`ADR-work-items-and-decisions`

- 2026-11-10: 仮決め4件をユーザーが確認し、ADR 6件を承認した（status: accepted・effective_at 2026-11-10T11:19:39+09:00）。ユーザーの了承を得て `git config core.hooksPath .githooks` を設定した。未コミットの変更は `rollback_snapshot.py --save` でローカルブランチ `backup/before-rollback-20261110-111905`（1d052fdb）に退避した（push はしていない）
- レビュー（2026-11-10）の指摘で、hook の `core.hooksPath` の検査を「読む・.githooks にする以外は止める」形にまとめ、`--config-env`・`git config unset`・`GIT_CONFIG_KEY_n` の抜け道を塞いだ

## 詰まった点・知見

- **AGENTS.md のルールを1つ落としていた**（「変えたら verify を実行」）。Stop hook で強制したので不要と判断したが、hook が効かないツールでは指示ごと消える。レビューで指摘され戻した。**hook で強制したルールも、指示は消さない** → `docs/agent-rules-rationale.md` に昇格
- **スキャナが安全網自身を誤検知した**（deny の `Read(**/.env)`、「hook を削除しない」）。英語は送信系の動詞だけに絞り、日本語は否定（しない・せず）を除外、検出パターンの定義とテスト検体だけを allowlist に入れた
- **未コミットのまま初回レビューすると、再レビューに初回の変更まで混ざる**。作業ツリーを一時 index で tree オブジェクトにし、tree 同士を比べる方式にした（`_gitutil.snapshot_tree`。作業ツリー・index・ブランチに触れない）
- **抜け道を変種ごとに塞ぐと漏れる**（`-c` だけ塞いで `--config-env`・`config unset`・環境変数が残った）。許す形を列挙し、それ以外を止める書き方にする
- セッションを親ディレクトリで起動していたため `.claude/agents/` の impl-reviewer が読み込まれなかった。general-purpose に定義ファイルを読ませて代用した

- **未検証**: night-run の新しいレビュー手順を実際の夜間実行（`claude -p`）で通していない。プロンプトの組み立てはテスト済み。コンテナは GitHub の main を clone するので、マージ前にはドライランできない → `WORK-night-run-dry-run`
- **未検証**: Codex・Cursor の hook の実機での発動（入出力の形式は参考プロジェクトの実装に合わせたが、実機では動かしていない）。導入時に「`git push --force` して」で止まるか確かめる
- night-run-hearing の Antigravity 手順が参照する `.agents/hooks.json` / `deny_dangerous_agy.py` は、このリポジトリに存在しない（今回の変更前から）。必要なら別タスクで
- 仮決めのまま実装していたこと（受け入れ条件の解釈・`$schema` と timeout・Cursor の `beforeReadFile`・CI の unittest・`plan_night.py --write` の上書き拒否・`--no-verify` という語での誤検知）は、2026-11-10 にユーザーがすべて確認した
