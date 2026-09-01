---
name: night-run-status
description: 夜間自律タスク実行(night-run)の進捗・結果を確認する。「night-runどうなってる」「夜間実行の状況を教えて」「進捗確認して」「昨日の夜間実行の結果は」「タスク終わった?」といった依頼で発動する。night-run-state.json・alerts.log・summary.txt・実行中コンテナの有無をまとめて棚卸しして報告する(読み取りのみ、状態やコンテナの変更は行わない)。
---

# night-run ステータス確認

`night-run/` の状態ファイル群と、稼働中コンテナの有無を読み取り専用で棚卸しし、平易な言葉で報告するスキル。ここでは何も変更しない(タスクの再実行・コンテナの起動停止はしない。それらが必要なら `night-run/run.sh` の使い方を案内するだけに留める)。

## Step 1: state ファイルの有無を確認する

`night-run/state/night-run-state.json` が無ければ、「まだnight-runが一度もセットアップされていない(ヒアリングSkillが未実行)」と伝えて終わる。

## Step 2: タスクごとの状況をまとめる

`night-run/state/night-run-state.json` を読み、`deadline` / `hard_limit` / 各タスクの `status` を確認する。タスクごとに:

- `done`: `pr_url` と `pr_status`(ready/draft)を提示する
- `in_progress`: `step`(最後に記録された作業段階)と `review_round` を提示する
- `failed`: `failure_reason` と `diagnostic_branch` を提示する(調査するなら診断ブランチを見るよう案内する)
- `pending`: まだ着手されていないことを伝える

締切(`deadline`)・ハードリミット(`hard_limit`)が既に過ぎているかどうかも、現在時刻と比較して伝える。

## Step 3: アラート・サマリを確認する

- `night-run/state/alerts.log` が存在すれば末尾を読み、`failed`やサンドボックスガードの異常など、見落としてはいけない警告が無いか確認する
- `night-run/state/summary.txt` が存在すれば(全タスク完走後に書かれる最終サマリ)、その内容をそのまま提示する

## Step 4: コンテナが今も動いているか確認する

```sh
docker ps --filter name=night-runner --format '{{.Status}}'
```

動いていれば「まだ実行中。`night-run/run.sh logs` でリアルタイムログを追える」と伝える。動いていなければ、state上の`pending`/`in_progress`タスクが残っているかどうかで「完走した」のか「途中で止まった(コンテナが落ちた・stopされた)」のかを判断し、後者なら`night-run/README.md`のトラブルシュートを参照するよう案内する。

## Step 5: 平易な言葉で報告する

以下を簡潔にまとめて報告する。

- 全体のステータス(実行中 / 完走 / 未セットアップ / 途中停止)
- 完了タスク数・失敗タスク数・未着手タスク数
- 失敗タスクがあれば、原因と診断ブランチ
- 次にユーザーがとるべきアクション(あれば): 例えば「`failed`タスクの診断ブランチを確認する」「コンテナが落ちているので`night-run/run.sh start`でやり直す前に原因を確認する」等
