#!/usr/bin/env python3
"""night-run-status の棚卸しを1回で行う（読み取り専用）。stateを読み、要約だけを出す。

  python3 night-run/status.py

何も変更しない（再実行・コンテナの起動停止はしない）。
"""
import datetime
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
STATE_DIR = HERE / "state"


def main():
    state_file = STATE_DIR / "night-run-state.json"
    if not state_file.exists():
        print("未セットアップ: state が無い（night-run-hearing が未実行）")
        return 0
    state = json.loads(state_file.read_text(encoding="utf-8"))
    now = datetime.datetime.now(datetime.timezone.utc)
    for key in ("deadline", "hard_limit"):
        if state.get(key):
            t = datetime.datetime.fromisoformat(state[key])
            print(f"{key}: {state[key]}（{'過ぎている' if t <= now else 'まだ'}）")
    tasks = state.get("tasks", [])
    counts = {}
    for t in tasks:
        counts[t.get("status", "?")] = counts.get(t.get("status", "?"), 0) + 1
        line = f"- [{t.get('status')}] {t.get('title')}"
        if t.get("status") == "done":
            line += f" — PR {t.get('pr_url')}（{t.get('pr_status')}）"
        elif t.get("status") == "in_progress":
            line += f" — 段階 {t.get('step')} / レビュー {t.get('review_round', 0)}回目"
        elif t.get("status") == "failed":
            line += f" — 原因 {t.get('failure_reason')} / 診断ブランチ {t.get('diagnostic_branch')}"
        print(line)
    print("集計: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())))

    alerts = STATE_DIR / "alerts.log"
    if alerts.exists():
        tail = alerts.read_text(encoding="utf-8", errors="replace").splitlines()[-10:]
        print("alerts.log（末尾10行）:")
        print("\n".join(f"  {l}" for l in tail))
    summary = STATE_DIR / "summary.txt"
    if summary.exists():
        print("summary.txt:")
        print(summary.read_text(encoding="utf-8", errors="replace").strip())

    running = None
    if shutil.which("docker"):
        r = subprocess.run(["docker", "ps", "--filter", "name=night-runner", "--format", "{{.Status}}"],
                           capture_output=True, text=True)
        running = r.stdout.strip() if r.returncode == 0 else None
    left = counts.get("pending", 0) + counts.get("in_progress", 0)
    if running:
        overall = f"実行中（{running}）。経過は night-run/run.sh logs"
    elif running is None:
        overall = "コンテナの状態は確認できない（docker が無い・動いていない）"
    elif left:
        overall = "途中停止の可能性（コンテナが無いのに未完了のタスクがある）。night-run/README.md のトラブルシュートへ"
    else:
        overall = "完走"
    print(f"全体: {overall}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
