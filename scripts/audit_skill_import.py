#!/usr/bin/env python3
"""import-skills の Step 2〜3（スキルの発見と監査）を機械的に行う（読み取り専用）。

  python3 scripts/audit_skill_import.py <cloneしたディレクトリ> [--name <スキル名>]

出力はスキルごとの判定（安全 / 要注意 / 取り込まない）と理由。コピーはしない。
判定が「安全」でも、AIは SKILL.md 本文を読んで中身を確かめてからユーザーに提示する
（機械検査は言い換えられた指示を見落とす）。
"""
import argparse
import os
import re
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from scan_agent_content import is_text, scan_text  # noqa: E402

EXEC_EXT = {".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts", ".rb", ".pl", ".ps1", ".bat", ".exe"}
CONFIG_NAMES = {"settings.json", "settings.local.json", "hooks.json", ".mcp.json", "package.json"}
SECRET_FILE = re.compile(r"(^|/)(\.env(\.[\w.-]+)?|id_(rsa|dsa|ecdsa|ed25519)|.*\.pem|.*\.key|credentials(\.json)?)$")
SECRET_OK = re.compile(r"\.env\.(example|sample|template)$")
SAMPLE_DIR = re.compile(r"(?i)(^|[-_/])(template|example|sample|skeleton)s?($|[-_/])")


def frontmatter_name(skill_md):
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^name:\s*(.+)$", text.split("---", 2)[1] if text.startswith("---") else "", re.M)
    return m.group(1).strip().strip("\"'") if m else skill_md.parent.name


def audit(skill_dir, src_root):
    danger, caution = [], []
    for f in sorted(p for p in skill_dir.rglob("*") if p.is_file() and ".git" not in p.parts):
        rel = f.relative_to(skill_dir).as_posix()
        if SECRET_FILE.search(rel) and not SECRET_OK.search(rel):
            danger.append(f"秘密情報らしきファイル: {rel}")
            continue
        if f.suffix.lower() in EXEC_EXT or "hooks" in f.parts or f.name in CONFIG_NAMES:
            caution.append(f"実行コード/設定: {rel}（中身をユーザーに見せて明示承認が要る）")
        elif os.stat(f).st_mode & (stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH):
            caution.append(f"実行ビット付き: {rel}")
        if f.is_symlink():
            danger.append(f"シンボリックリンク: {rel} → {os.readlink(f)}（取り込み先の外を指しうる）")
        if is_text(f) and f.stat().st_size <= 2 * 1024 * 1024:
            for _, n, col, sev, rid, msg in scan_text(rel, f.read_text(encoding="utf-8", errors="replace")):
                (danger if sev == "error" else caution).append(f"{rid} {rel}:{n} {msg}")
    return danger, caution


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("source")
    ap.add_argument("--name", help="対象スキル名（ディレクトリ名または frontmatter の name）")
    args = ap.parse_args()
    src = Path(args.source).resolve()
    found = sorted(p for p in src.rglob("SKILL.md") if ".git" not in p.parts)
    if not found:
        print("SKILL.md が見つからない")
        return 1
    dest = ROOT / ".claude/skills"
    rows = []
    for md in found:
        d = md.parent
        name = frontmatter_name(md)
        if args.name and args.name not in (name, d.name):
            continue
        rel = d.relative_to(src).as_posix()
        if SAMPLE_DIR.search(rel) and not args.name:
            rows.append((name, rel, "除外", ["雛形・サンプルと思われる（明示的に指名すれば対象にする）"]))
            continue
        danger, caution = audit(d, src)
        if (dest / name).exists():
            caution.append(f"名前が衝突: .claude/skills/{name} が既にある（上書きしない）")
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name):
            caution.append(f"name が規約外: {name!r}")
        verdict = "取り込まない" if danger else "要注意" if caution else "安全"
        rows.append((name, rel, verdict, danger + caution))
    for name, rel, verdict, reasons in rows:
        print(f"## {name}  [{verdict}]  ({rel})")
        for r in reasons[:15]:
            print(f"- {r}")
        if len(reasons) > 15:
            print(f"- ...ほか{len(reasons) - 15}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
