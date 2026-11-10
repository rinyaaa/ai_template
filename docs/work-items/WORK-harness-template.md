---
id: WORK-harness-template
title: 作業ルール（ハーネス）のテンプレート化
status: done
priority: P2
depends_on: []
adrs: []
issue:
created_at: 2026-09-09T00:00:00+09:00
updated_at: 2026-11-09T22:30:00+09:00
blocked_reason:
design_impact: none
design_impact_reason: ADRの仕組みを入れる前の作業。docs/history/2026-09-09-harness-template.md から移した記録で、当時の判断を遡ってADRにはしない（推測を当時の判断として書かないため）
---

# 作業ルール（ハーネス）のテンプレート化

<!-- 2026-11-09 に docs/history/ を廃止したとき、作業記録から移した。当時は Work Item の型が無かったため、受け入れ条件は記録から読み取れる範囲で書いている -->

## 依頼の原文

記録なし（作業記録には依頼文が残っていない）。

## 受け入れ条件

- [x] 実プロジェクトの作業ルール（計画→実装→レビュー→完了の5フェーズ等）を「薄い常時ロード＋必要時ロードのスキル」構造に載せ替える
- [x] 常時ロード量を増やさない（5,206 → 5,115文字）

## 決めたこと

- `github-task-intake` を `task-intake` に改名し、出力先（GitHub Issue / 計画書 / 両方）で分岐する形に統合（出どころ: 記録なし）

## Evidence

- `AGENTS.md` に「作業の進め方」を追加。安全ルール1に `git worktree remove` / `prune` を追加
- 新規スキル5本: `implementation-review` / `work-log` / `parallel-worktree` / `ui-guidelines` / `doc-index`
- 既存8スキルの `description` をトリガー条件だけに短縮（2,153 → 1,422文字）
- `.claude/settings.json` の deny・hook・`verify_safety_net.py` に worktree 削除を追加
- `CLAUDE.md` にプロジェクト固有の穴埋め欄を新設。`docs/plans/` `docs/history/` を新設

## 詰まった点・知見

- **新スキルを足すと常時ロードが増える。** 原因は description に本文と同じ説明を書いていたこと。description は発動条件だけに絞る → `.claude/skills/README.md` に昇格済み
- **型を決める側と参照する側がずれた**（「スコープ: 含む/含まない」の1欄と「スコープ / スコープ外」）。型を決めたら、参照する箇所を grep して実際の出力と突き合わせる
- **deny の追加を片方にしか入れていなかった。** 安全網は「実際に効く場所」と「消えていないか検査する場所」の両方を必ず対で更新する
- description からトリガー語を削ると発動精度が落ちる → `.claude/skills/README.md` に昇格済み
