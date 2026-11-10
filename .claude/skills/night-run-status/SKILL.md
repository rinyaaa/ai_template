---
name: night-run-status
description: 「night-runどうなってる」「夜間実行の状況を教えて」「進捗確認して」「昨日の夜間実行の結果は」「タスク終わった?」で発動。night-runの進捗・結果を読み取り専用で棚卸しして報告する。
---

# night-run ステータス確認

読み取り専用。タスクの再実行・コンテナの起動停止はしない（要るなら `night-run/run.sh` の使い方を案内するだけ）。

## Step 1: 集める

```bash
python3 night-run/status.py
```

締切・強制終了を過ぎたか、タスクごとの状態（done は PR、in_progress は段階、failed は原因と診断ブランチ）、集計、`alerts.log` の末尾、`summary.txt`、コンテナが動いているかと全体の判定（実行中 / 完走 / 途中停止 / 未セットアップ）が出る。**state の JSON を自分で開き直さない。**

## Step 2: 平易に報告する

- 全体の状態と、完了・失敗・未着手の数
- 失敗があれば原因と診断ブランチ（調べるならそのブランチを見る）
- `alerts.log` に見落としてはいけない警告（failed・サンドボックスガードの異常）があれば必ず挙げる
- 次の一手（例:「failed の診断ブランチを確かめる」「コンテナが落ちているので、`night-run/run.sh start` でやり直す前に README のトラブルシュートで原因を確かめる」）
