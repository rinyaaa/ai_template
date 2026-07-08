# Skills

このディレクトリには、このリポジトリ専用のClaude Codeスキル（`SKILL.md`）を置く。各スキルはサブディレクトリとして配置し、`<skill-name>/SKILL.md` にfrontmatter（`name`, `description`）と手順を記述する。

スキルの作成・改善・評価には `skill-creator` スキル（`/example-skills:skill-creator`）を使うと良い。

## 一覧

| スキル | 概要 |
|---|---|
| [claude-project-setup](claude-project-setup/SKILL.md) | プロジェクトにClaude Code用の`.claude/`環境（権限・hooks・プラグイン設定、CLAUDE.md、必要に応じたskill/command/agentの雛形）を対話形式でセットアップする。エンジニアが常駐しない組織向けの保守的な権限設計やセキュリティレビュー体制の構築にも対応。 |

新しいスキルを追加したら、この表にも1行追記すること。
