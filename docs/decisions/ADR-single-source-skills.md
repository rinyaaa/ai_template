---
id: ADR-single-source-skills
title: スキルの正本を1か所にし、他ツールには入口だけを生成する
status: accepted
supersedes: []
depends_on: [ADR-agent-instruction-layers]
created_at: 2026-11-10T00:28:35+09:00
updated_at: 2026-11-10T11:19:12+09:00
effective_at: 2026-11-10T11:19:12+09:00
---

# スキルの正本を1か所にし、他ツールには入口だけを生成する

## 背景

Claude Code・Codex・Cursor を併用したい。スキルを各ツールの置き場所に写すと、片方だけ直されて食い違う。2026-11-09〜10 の会話（`WORK-slim-ai-harness`）で決めた。依頼の原文はその Work Item にある。

## 決定

- スキルの正本は `.claude/skills/<name>/SKILL.md` の1か所
- Codex 向け `.agents/skills/<name>/SKILL.md` と Cursor 向け `.cursor/rules/agents.mdc` は、正本を読めと書いた薄い入口として `python3 scripts/sync_agent_adapters.py` が生成する。手で編集しない
- 生成物のずれは `sync_agent_adapters.py --check` で検出し、整合性検査・pre-commit・CI から走らせる

## 理由

- 中身を1か所にすれば二重管理にならない。入口は name と description だけを持つので、各ツールの発動の仕組みはそのまま使える
- 比べた案: (a) シンボリックリンク → Windows や一部のツールで扱いが不安定。(b) 参考にした別プロジェクトのように正本をトップレベルの `skills/` に移す → ツールに依らない名前で筋は良いが、既存の参照（スキル・スクリプト・検査）を大きく書き換えるので今回は見送った
- 参考: 参考にした別プロジェクト の `skills/` 正本 + `sync_agent_adapters.py`

## 影響

- スキルを足し引きしたら `sync_agent_adapters.py` を実行する必要がある（忘れると検査で止まる）
- Cursor が `.agents/skills/` を読むかは未確認。Cursor は AGENTS.md と `.cursor/rules/` から正本へ辿る前提
- 正本が `.claude/` の下にあるので、Claude Code 以外の利用者には場所が直感的でない
