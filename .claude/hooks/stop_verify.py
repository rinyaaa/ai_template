#!/usr/bin/env python3
"""終了時hook: 安全網に関わるファイルが変わっていたら、AIが止まる前に整合性検査を自動で走らせる。

AGENTS.md 安全ルール6の「安全網のファイルを変えたら verify_safety_net.py を実行する」を、AIの記憶に頼らず強制する。
変更が無ければ何もしない（普段のターンではトークンも時間も使わない）。

失敗したら1回だけ「直してから止まる」ように差し戻す。2回目も失敗なら差し戻さず、
未通過のまま止める（無限ループにしない）。検証が通らないことを成功扱いにしない。

  Claude: .claude/settings.json の Stop   → {"decision": "block", "reason": ...}
  Codex : .codex/hooks.json の Stop       → 同上
  Cursor: .cursor/hooks.json の stop      → {"followup_message": ...}（loop_limit: 1）
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # 入力の cwd ではなく、このファイルの位置から決める
SAFETY = ("AGENTS.md", "CLAUDE.md", ".claude/", ".codex/", ".cursor/", ".agents/", ".githooks/",
          "scripts/verify_safety_net.py", "scripts/scan_agent_content.py", "scripts/sync_agent_adapters.py",
          "config/agent-security-allowlist.json", ".github/workflows/", "docs/work-items/", "docs/decisions/")
TIMEOUT = 60


def changed_safety_files():
    r = subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], cwd=ROOT,
                       capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if r.returncode != 0:
        return []
    paths = [line[3:].split(" -> ")[-1].strip('"') for line in r.stdout.splitlines()]
    return [p for p in paths if p.startswith(SAFETY) or p in SAFETY]


def run_checks(files):
    problems = []
    checks = [[sys.executable, "-B", "scripts/verify_safety_net.py"]]
    texts = [f for f in files if (ROOT / f).is_file()]
    if texts:
        checks.append([sys.executable, "-B", "scripts/scan_agent_content.py", *texts])
    for cmd in checks:
        try:
            r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=TIMEOUT,
                               stdin=subprocess.DEVNULL)
        except (OSError, subprocess.TimeoutExpired) as e:
            problems.append(f"{cmd[2]} を実行できない: {e}")
            continue
        if r.returncode != 0:
            lines = [l for l in r.stdout.splitlines() if l.startswith(("FAIL", "ERROR", "WARNING"))]
            problems.append(f"{cmd[2]}: " + ("; ".join(lines[:5]) or r.stdout.strip()[-300:]))
    return problems


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=("claude", "codex", "cursor"), default="claude")
    args = ap.parse_args()
    try:
        payload = json.load(sys.stdin)
        if not isinstance(payload, dict):
            raise ValueError
    except Exception:
        payload = {}

    if args.provider == "cursor":
        if payload.get("status") in ("aborted", "error"):
            print("{}")
            return 0
        already = (payload.get("loop_count") or 0) >= 1
    else:
        already = bool(payload.get("stop_hook_active"))

    files = changed_safety_files()
    problems = run_checks(files) if files else []
    if not problems:
        print("{}" if args.provider == "cursor" else "")
        return 0

    reason = ("安全網の整合性検査が通っていない: " + " / ".join(problems)
              + "。許可された作業範囲の中で直し、python3 scripts/verify_safety_net.py が通ることを確かめてから終える。"
              + "検査や安全網を弱めて通さない。範囲外の修正が要るなら、未通過のまま理由を報告する。")
    if already:
        print(f"安全網の検査が未通過のまま終了: {' / '.join(problems)}", file=sys.stderr)
        print("{}" if args.provider == "cursor" else "")
        return 0
    if args.provider == "cursor":
        print(json.dumps({"followup_message": reason}, ensure_ascii=False))
    else:
        print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
