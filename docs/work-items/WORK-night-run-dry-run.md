---
id: WORK-night-run-dry-run
title: マージ後に night-run の新しいレビュー手順をドライランで通す
status: ready
priority: P2
depends_on: [WORK-slim-ai-harness]
adrs: [ADR-shared-review-flow]
issue: 
created_at: 2026-11-10T11:19:18+09:00
updated_at: 2026-11-10T11:19:18+09:00
blocked_reason:
design_impact: pending
design_impact_reason:
---

# マージ後に night-run の新しいレビュー手順をドライランで通す

## 依頼の原文

WORK-slim-ai-harness の受け入れ条件「Codex・Cursor の hook と、night-run の新しいレビュー手順を実機で一度通す」のうち、night-run の部分をここへ分けた。質問「受け入れ条件『実機で一度通す』の night-run 部分をどうしますか？」へのユーザーの回答:

> マージ後の別 Work Item

## 背景・なぜやるか

WORK-slim-ai-harness で、night-run のレビューを対話時と同じ仕組みにした（`ADR-shared-review-flow`。`review_bundle.py` で束ね、`impl-reviewer` / `impl-reviewer-recheck` で判定する）。プロンプトの組み立てはテスト済みだが、実際の夜間実行（`claude -p`）ではまだ通していない。

night-run のコンテナは `NIGHT_RUN_REPO_URL` を clone して `origin/main` に reset する（`night-run/docker/entrypoint.sh`）。そのため、WORK-slim-ai-harness の変更が main にマージされるまで、ドライランでは新しい手順を試せない。

## 受け入れ条件

- [ ] WORK-slim-ai-harness の変更が main にマージされている（マージはユーザーが頼んだときだけ行う）
- [ ] `night-run/README.md` の「ドライラン」の手順どおりに1回通す。締切は現在時刻の5〜10分後、タスクは軽いもの1件
- [ ] レビューが `review_bundle.py` の材料で `impl-reviewer` によって行われ、修正があれば `impl-reviewer-recheck` が修正分だけを見ることを、ログで確かめる
- [ ] README の確認項目（firewall の自己検証・ソフトカットオフとハードリミット・締切超過時の診断ブランチと draft PR の本文・正常完走時の `gh pr view` での確認）を確かめる
- [ ] 結果（日付・使ったタスク・確かめた項目・問題）を Evidence に書く。問題があれば直して、もう一度ドライランする

## スコープ

ドライランの実行と、そこで見つかった night-run の不具合の修正。

## スコープ外

- 派生プロジェクト向けの汎用化（既定ブランチ `main` の決め打ちなど）は `WORK-template-portability` の G-3 で扱う

## 決めたこと

- 確認済み: マージ後の別 Work Item にする（ユーザーの回答:「マージ後の別 Work Item」）
- 仮決め: 優先度 P2

## 実装方針

1. マージ済みであることを確かめる
2. ドライランは GitHub に実際のブランチと draft PR を作るので、AGENTS.md ルール4の形で許可を取ってから `night-run/run.sh start` を実行する
3. `night-run/run.sh logs` と `python3 night-run/status.py` で経過を見る
4. ドライランで作ったブランチ・draft PR を片付けるかは、ユーザーに頼む（削除はしない）

## 並列化の単位

直列（機能が1つ / 依存があるため）

## 想定リスク・確認事項

- Docker・GitHub のトークン・Claude の認証が要る。どれかが無ければ、準備をユーザーに頼む
- 実際の GitHub リポジトリに draft PR ができる

## Evidence

<!-- 完了時に: 変えたファイル・検証したコマンドと結果・PR -->

## 詰まった点・知見

<!-- 完了時に: 詰まった点となぜそうなったか / 次に同じ領域を触る人が知っていると得をすること。効くものは CLAUDE.md かスキルへ昇格させ「→ 昇格」と添える -->
