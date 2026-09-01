#!/usr/bin/env python3
"""タスク実行中のClaude自身が呼び出す、進捗(step)書き込み専用の最小スクリプト
(docs/night-run-design.md 9.2節)。night_runner.py本体には依存しない、独立した
スクリプトとして分離している――タスクを実装するClaudeに渡すツール面を、
状態ファイルの該当タスクを更新するだけの最小機能に絞るため。

使い方: python3 night-run/update_step.py "<タスクタイトル>" "<段階名>" [レビューラウンド数]
"""
import datetime
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _state_io import atomic_write_json  # noqa: E402

STATE_FILE = os.environ.get("NIGHT_RUN_STATE_FILE", "/workdir/state/night-run-state.json")


def main():
    if len(sys.argv) < 3:
        print("usage: update_step.py <task_title> <step> [review_round]", file=sys.stderr)
        return 1

    title, step = sys.argv[1], sys.argv[2]
    review_round = None
    if len(sys.argv) > 3:
        try:
            review_round = int(sys.argv[3])
        except ValueError:
            print(f"エラー: review_round は整数で指定する ({sys.argv[3]!r})", file=sys.stderr)
            return 1

    with open(STATE_FILE) as f:
        state = json.load(f)

    for task in state["tasks"]:
        if task["title"] == title:
            task["status"] = "in_progress"
            task["step"] = step
            if review_round is not None:
                task["review_round"] = review_round
            break
    else:
        print(f"エラー: タスク「{title}」がstateに見つからない", file=sys.stderr)
        return 1

    state["last_updated"] = datetime.datetime.now().isoformat()
    atomic_write_json(STATE_FILE, state)  # 9.7節: night_runner.pyのsave_stateと同じアトミック書き込み
    return 0


if __name__ == "__main__":
    sys.exit(main())
