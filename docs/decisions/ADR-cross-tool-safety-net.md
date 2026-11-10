---
id: ADR-cross-tool-safety-net
title: 安全網をツールごとのhookとgit hook・CIで重ねる
status: accepted
supersedes: []
depends_on: []
created_at: 2026-11-10T00:28:35+09:00
updated_at: 2026-11-10T11:19:12+09:00
effective_at: 2026-11-10T11:19:12+09:00
---

# 安全網をツールごとのhookとgit hook・CIで重ねる

## 背景

整理前の安全網（破壊的コマンドの拒否・秘密情報の読み取りの拒否）は Claude Code の中でしか効かず、Codex・Cursor では指示だけだった。コミット時に秘密情報を検査する仕組みも無く、`--no-verify` での回避も止まらなかった。2026-11-09〜10 の会話（`WORK-slim-ai-harness`）で決めた。依頼の原文はその Work Item にある。

## 決定

- 同じ hook スクリプト（`.claude/hooks/deny_dangerous_bash.py`・`stop_verify.py`）を、`--provider` で入出力の形式を切り替えて Claude Code・Codex（`.codex/hooks.json`）・Cursor（`.cursor/hooks.json`）から呼ぶ
- 終了時 hook は、安全網のファイルや記録が変わっていれば整合性検査を走らせ、失敗なら1回だけ差し戻す（2回目は差し戻さず、未通過として止める）
- ツールに依らない層として `.githooks/pre-commit`（秘密情報・不可視文字・記録の決まり・安全網の整合性）を置き、hook は `--no-verify`・`git commit -n`・`-c core.hooksPath=`・`core.hooksPath` を外す操作を止める
- 最後の砦は CI とブランチ保護

## 理由

- hook はそのツールの中でしか効かないので、ツールごとに設定する必要がある。スクリプトを1つにすれば検出の規則は二重管理にならない
- 秘密情報は履歴に入ると消せないので、公開前ではなくコミット前に止める
- 比べた案: (a) 指示だけに頼る → 確率的で、検査の回避も止められない。(b) CI だけに頼る → push されるまで気づけず、秘密情報は既に履歴に入っている
- 参考: 参考にした別プロジェクト の `hooks/agent-stop.py`（ツールごとのプロトコル変換と再試行の上限）、`.codex/hooks.json`・`.cursor/hooks.json`

## 影響

- Codex は hook 機能を有効にしないと読まない。Codex・Cursor の hook は実機で未検証（入出力は参考プロジェクトに合わせた）
- pre-commit は `git config core.hooksPath .githooks` を各クローンで実行しないと効かない（未設定なら健康診断が知らせる）
- ブロックリスト方式なので完全ではない。コミットメッセージに `--no-verify` と書くだけでも止まる（安全側の誤検知として許容。仮決め）
