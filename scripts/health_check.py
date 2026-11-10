#!/usr/bin/env python3
"""project-health-check の「点検項目を集める」を1回で実行し、短い要約だけを出す（読み取り専用）。

AIが gh / git / audit を1つずつ叩いて長い出力を読む代わりに使う。
判断（優先度の最終決定・ライセンス変更の扱い・secret-scanの真偽）はAIと人間が行う。

  python3 scripts/health_check.py            # 要約
  python3 scripts/health_check.py --json     # 機械向け
  python3 scripts/health_check.py --no-audit # 依存の脆弱性検査を省く（遅いとき）

見られなかった項目は SKIP として理由つきで出す（「見ていない」を「問題なし」にしない）。
"""
import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from detect_stack import detect  # noqa: E402


def run(cmd, timeout=60):
    try:
        r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout,
                           stdin=subprocess.DEVNULL)
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, "", str(e)


class Report:
    def __init__(self):
        self.items = []  # (level, label, detail)

    def add(self, level, label, detail=""):
        self.items.append({"level": level, "label": label, "detail": detail})


def safety_net(rep):
    code, out, _ = run([sys.executable, "scripts/verify_safety_net.py"], timeout=120)
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    if code == 0:
        rep.add("ok", "安全網の自己点検", "全項目OK")
    else:
        rep.add("now", "安全網の自己点検に失敗", "; ".join(fails) or out[-300:])


def github(rep):
    if not shutil.which("gh"):
        rep.add("skip", "GitHub側の点検", "gh が無い")
        return
    if run(["gh", "auth", "status"])[0] != 0:
        rep.add("skip", "GitHub側の点検", "gh が未認証（gh auth login）")
        return
    code, out, _ = run(["gh", "pr", "list", "--author", "app/dependabot", "--state", "open",
                        "--json", "number,title"])
    if code == 0:
        prs = json.loads(out or "[]")
        if prs:
            rep.add("week", f"未処理のDependabot PR {len(prs)}件",
                    ", ".join(f"#{p['number']}" for p in prs[:10]))
    code, out, _ = run(["gh", "api", "repos/{owner}/{repo}/dependabot/alerts",
                        "--jq", '[.[] | select(.state=="open") | .security_advisory.severity]'])
    if code == 0:
        sev = json.loads(out or "[]")
        high = [s for s in sev if s in ("high", "critical")]
        if high:
            rep.add("now", f"high/critical のセキュリティアラート {len(high)}件", "")
        if len(sev) > len(high):
            rep.add("week", f"その他のセキュリティアラート {len(sev) - len(high)}件", "")
    else:
        rep.add("skip", "セキュリティアラート", "APIの権限が無い")
    code, out, _ = run(["gh", "run", "list", "--limit", "10", "--json", "conclusion,name,headBranch"])
    if code == 0:
        runs = json.loads(out or "[]")
        failed = [r for r in runs if r.get("conclusion") == "failure"]
        secret = [r for r in failed if "secret" in (r.get("name") or "").lower()]
        if secret:
            rep.add("now", "secret-scan が失敗している（一括対応しない。本物かを個別に確認）",
                    ", ".join(r["name"] for r in secret))
        others = [r for r in failed if r not in secret]
        if others:
            names = sorted({f"{r['name']}@{r['headBranch']}" for r in others})
            rep.add("now" if len(others) >= 3 else "week", f"直近10回中 CI失敗 {len(others)}件", ", ".join(names))
    code, out, _ = run(["gh", "pr", "list", "--state", "open", "--json", "number,updatedAt,title"])
    if code == 0:
        prs = json.loads(out or "[]")
        if prs:
            oldest = sorted(prs, key=lambda p: p["updatedAt"])[:5]
            rep.add("week", f"Open PR {len(prs)}件（更新が古い順）",
                    ", ".join(f"#{p['number']}({p['updatedAt'][:10]})" for p in oldest))


def local(rep, do_audit):
    if run(["git", "rev-parse", "--git-dir"])[0] != 0:
        rep.add("skip", "ローカルのgit点検", "gitリポジトリではない")
        return
    _, hooks_path, _ = run(["git", "config", "core.hooksPath"])
    if (ROOT / ".githooks/pre-commit").exists() and hooks_path not in (".githooks", "./.githooks"):
        rep.add("week", "コミット前の検査（.githooks/pre-commit）が無効",
                "このクローンで `git config core.hooksPath .githooks` を実行すると、秘密情報・不可視文字の検査がコミットごとに走る（ローカル設定の変更なので、実行は人間の了承を得てから）")
    _, out, _ = run(["git", "status", "--porcelain"])
    if out:
        rep.add("watch", f"未コミットの変更 {len(out.splitlines())}ファイル", "次の作業と混ざる前に片付ける")
    code, out, _ = run(["git", "rev-list", "--count", "@{u}..HEAD"])
    if code == 0 and out not in ("", "0"):
        rep.add("watch", f"未pushのコミット {out}件", "")
    _, out, _ = run(["git", "branch", "--merged"])
    merged = [b.strip() for b in out.splitlines() if b.strip() and not b.startswith("*")
              and b.strip() not in ("main", "master", "develop")]
    if merged:
        rep.add("watch", f"マージ済みのローカルブランチ {len(merged)}本（削除はしない。/clean_gone を案内）",
                ", ".join(merged[:8]))

    stack = detect(ROOT)
    if not do_audit:
        rep.add("skip", "依存の脆弱性", "--no-audit 指定")
    elif not stack["audit"]:
        rep.add("skip", "依存の脆弱性", "検査コマンドを判定できない（スタック未検出）")
    else:
        tool = stack["audit"].split()[0]
        if not shutil.which(tool):
            rep.add("skip", "依存の脆弱性", f"{tool} が無い")
        else:
            code, out, err = run(["sh", "-c", stack["audit"]], timeout=300)
            if code == 0:
                rep.add("ok", "依存の脆弱性", f"{stack['audit']} で検出なし")
            else:
                tail = (out or err).splitlines()[-3:]
                rep.add("week", "依存の脆弱性あり（深刻度を確認して並べ替える）", " / ".join(tail))
    for key in ("lint", "test"):
        if key not in stack["commands"]:
            rep.add("skip", f"{key} の実行", "コマンドが未検出（CLAUDE.mdの記載を確認）")


def template_blanks(rep):
    """派生プロジェクトでの埋め忘れ。テンプレート自身（実装マニフェストが無い）では未記入が正常なので見ない。"""
    claude = ROOT / "CLAUDE.md"
    manifests = ("package.json", "pyproject.toml", "go.mod", "Cargo.toml", "Gemfile")
    if not claude.exists() or not any((ROOT / m).exists() for m in manifests):
        return
    blanks = [l.strip() for l in claude.read_text(encoding="utf-8").splitlines()
              if l.strip().startswith("- ") and l.strip().endswith(":")]
    if blanks:
        rep.add("watch", f"CLAUDE.md の未記入欄 {len(blanks)}件", " ".join(blanks))
    _, out, _ = run(["grep", "-rln", "TODO", "night-run/", ".claude/skills/night-run-hearing/"])
    if out:
        rep.add("watch", "night-run の未記入（使う予定があるなら動かす前に埋める）", ", ".join(out.splitlines()[:6]))


LEVELS = [("now", "今すぐ対応"), ("week", "今週中に対応"), ("watch", "気に留めておく"),
          ("skip", "見ていない項目"), ("ok", "問題なし")]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-audit", action="store_true")
    args = ap.parse_args()
    rep = Report()
    safety_net(rep)
    github(rep)
    local(rep, not args.no_audit)
    template_blanks(rep)
    if args.json:
        print(json.dumps(rep.items, ensure_ascii=False, indent=2))
        return 0
    for level, title in LEVELS:
        rows = [i for i in rep.items if i["level"] == level]
        if not rows:
            continue
        print(f"## {title}")
        for i in rows:
            print(f"- {i['label']}" + (f" — {i['detail']}" if i["detail"] else ""))
    if not any(i["level"] in ("now", "week", "watch") for i in rep.items):
        print("異常なし")
    return 0


if __name__ == "__main__":
    sys.exit(main())
