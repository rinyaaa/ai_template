#!/usr/bin/env python3
"""AIに毎回読み込まれる文字量（常時ロード）と、スキル本文の大きさを測る。

スキルやルールを足し引きしたときに、手で wc や git show を回す代わりに使う。

  python3 scripts/context_cost.py              # 今の作業ツリーを測る
  python3 scripts/context_cost.py --ref main   # 指定したgitの版と比べる
  python3 scripts/context_cost.py --json       # 機械向け出力

常時ロード = AGENTS.md + CLAUDE.md + 全スキルの name/description + サブエージェントの description。
トークン数は目安（ASCII 4文字=1、それ以外 1.3文字=1 で概算）。
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALWAYS_FILES = ["AGENTS.md", "CLAUDE.md"]


def est_tokens(text):
    ascii_n = sum(1 for c in text if ord(c) < 128)
    return round(ascii_n / 4 + (len(text) - ascii_n) / 1.3)


def frontmatter(text):
    if not text.startswith("---"):
        return ""
    parts = text.split("---", 2)
    return parts[1] if len(parts) > 2 else ""


def meta_text(text):
    """frontmatterのうち常時ロードされる name / description だけを取り出す。"""
    head = frontmatter(text)
    out, keep = [], False
    for line in head.splitlines():
        if re.match(r"^(name|description):", line):
            keep = True
            out.append(line)
        elif keep and line.startswith((" ", "\t")):
            out.append(line)
        else:
            keep = False
    return "\n".join(out)


class Source:
    """作業ツリー または git の特定の版からファイルを読む。"""

    def __init__(self, ref=None):
        self.ref = ref

    def list(self, pattern):
        if self.ref is None:
            return sorted(p.relative_to(ROOT).as_posix() for p in ROOT.glob(pattern))
        out = subprocess.run(
            ["git", "ls-tree", "-r", "--name-only", self.ref],
            cwd=ROOT, capture_output=True, text=True, check=True,
        ).stdout.splitlines()
        rx = re.compile("^" + re.escape(pattern).replace(r"\*", "[^/]*") + "$")
        return sorted(p for p in out if rx.match(p))

    def read(self, path):
        if self.ref is None:
            p = ROOT / path
            return p.read_text(encoding="utf-8") if p.exists() else ""
        r = subprocess.run(["git", "show", f"{self.ref}:{path}"], cwd=ROOT, capture_output=True, text=True)
        return r.stdout if r.returncode == 0 else ""


def measure(src):
    always = {f: src.read(f) for f in ALWAYS_FILES}
    skills, bodies = {}, {}
    for path in src.list(".claude/skills/*/SKILL.md"):
        text = src.read(path)
        name = path.split("/")[2]
        skills[name] = meta_text(text)
        bodies[name] = text
    agents = {p: meta_text(src.read(p)) for p in src.list(".claude/agents/*.md")}
    always_text = "".join(always.values()) + "".join(skills.values()) + "".join(agents.values())
    return {
        "always": {
            "chars": len(always_text),
            "tokens": est_tokens(always_text),
            "files": {k: len(v) for k, v in always.items()},
            "skill_descriptions": sum(len(v) for v in skills.values()),
            "agent_descriptions": sum(len(v) for v in agents.values()),
        },
        "skill_bodies": {k: {"chars": len(v), "tokens": est_tokens(v)} for k, v in sorted(bodies.items())},
    }


def print_report(now, base, base_label):
    a = now["always"]
    line = f"常時ロード: {a['chars']:,}文字（約{a['tokens']:,}トークン）"
    if base:
        d = a["chars"] - base["always"]["chars"]
        line += f"  {base_label}比 {d:+,}文字"
    print(line)
    for f, n in a["files"].items():
        print(f"  {f:<28}{n:>7,}")
    print(f"  {'スキルのdescription合計':<24}{a['skill_descriptions']:>7,}")
    print(f"  {'エージェントのdescription合計':<21}{a['agent_descriptions']:>7,}")
    print("スキル本文（発動したときだけ読まれる）:")
    for name, v in sorted(now["skill_bodies"].items(), key=lambda kv: -kv[1]["chars"]):
        extra = ""
        if base and name in base["skill_bodies"]:
            extra = f"  {v['chars'] - base['skill_bodies'][name]['chars']:+,}"
        elif base:
            extra = "  (新規)"
        print(f"  {name:<28}{v['chars']:>7,}文字{extra}")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--ref", help="比較するgitの版（例: main, HEAD）")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    now = measure(Source())
    base = measure(Source(args.ref)) if args.ref else None
    if args.json:
        json.dump({"now": now, "base": base}, sys.stdout, ensure_ascii=False, indent=2)
        print()
    else:
        print_report(now, base, args.ref)


if __name__ == "__main__":
    main()
