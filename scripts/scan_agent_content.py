#!/usr/bin/env python3
"""AIが読むテキストに紛れた「見えない文字」と「指示の乗っ取り」を検出する。

AGENTS.md・スキル・hook・外部から取り込むスキルなど、AIへの指示として読まれるものは
見た目と中身が違う（不可視文字・双方向制御文字）と人間のレビューをすり抜ける。
また、外部テキストに埋め込まれた命令（「以前の指示を無視して…」）はプロンプトインジェクションになる。

  python3 scripts/scan_agent_content.py --all                  # 追跡中＋未追跡のファイル
  python3 scripts/scan_agent_content.py --staged               # コミット予定の差分（pre-commit用）
  python3 scripts/scan_agent_content.py <パス...>              # 指定ファイル・ディレクトリ（取り込み前の監査）
  --fail-on-warning を付けると warning でも exit 1

意図的な出現は config/agent-security-allowlist.json に「ファイル・ルール・理由」で登録する。
**検出ゼロは安全の証明ではない。** 1つの防御層にすぎない。
"""
import argparse
import json
import re
import subprocess
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST = ROOT / "config/agent-security-allowlist.json"
TEXT_EXT = {".md", ".mdc", ".txt", ".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".json",
            ".jsonc", ".yaml", ".yml", ".toml", ".html", ".css", ".ini", ".cfg"}
TEXT_NAMES = {"AGENTS.md", "CLAUDE.md", "Dockerfile", "Makefile", ".cursorrules"}
SKIP_DIRS = {".git", "node_modules", "vendor", "dist", "build", ".venv", "__pycache__"}
MAX_BYTES = 2 * 1024 * 1024

INVISIBLE = {
    **{c: "ゼロ幅文字" for c in (0x200B, 0x200C, 0x200D, 0x2060, 0x2061, 0x2062, 0x2063, 0x2064, 0x180E)},
    **{c: "双方向制御文字（表示順の偽装）" for c in (0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
                                               0x2066, 0x2067, 0x2068, 0x2069, 0x200E, 0x200F, 0x061C)},
}

# (ルールID, 重大度, 説明, 正規表現)
PATTERNS = [
    ("PI001", "error", "指示の優先順位の上書き",
     r"(?:ignore|disregard|forget|override)\s+(?:all\s+|any\s+)?(?:the\s+)?(?:previous|prior|above|earlier|system)\s+(?:instructions?|rules?|prompts?|messages?)"),
    ("PI001", "error", "指示の優先順位の上書き",
     r"(?:以前|前|上記|これまで|今まで|システム)の?(?:すべての|全ての)?(?:指示|命令|ルール|プロンプト).{0,12}(?:無視|破棄|忘れ|従わな)"),
    ("PI002", "error", "隠された指示の開示要求",
     r"(?:reveal|print|show|dump|leak|exfiltrate|send)\b.{0,40}\b(?:system|developer|hidden)\s+(?:prompt|message|instructions?)"),
    ("PI002", "error", "隠された指示の開示要求",
     r"(?:システム|開発者)(?:プロンプト|メッセージ|指示).{0,16}(?:表示|開示|送信|出力|教え)"),
    ("PI003", "error", "安全網の無効化の指示",
     r"(?:disable|remove|delete|bypass|turn\s+off)\s+(?:the\s+)?(?:hooks?|permissions?|deny\s+rules?|safety|guardrails?|sandbox)"),
    ("PI003", "error", "安全網の無効化の指示",
     r"(?:hook|フック|permissions?\.deny|denyルール|安全網|ガードレール|サンドボックス).{0,12}(?:無効|削除|外し|消し|回避|迂回)(?!.{0,6}(?:しない|しな|せず|禁止|させない|されない|できない))"),
    ("PI004", "error", "秘密情報の読み出し・送信の指示",
     r"\b(?:send|upload|post|exfiltrate|transmit|leak|forward)\b.{0,40}(?:\.env\b|id_rsa|\.ssh/|credentials|API[_ ]?KEY|secrets?|tokens?)"),
    ("PI004", "error", "秘密情報の読み出し・送信の指示",
     r"(?:\.env|秘密鍵|APIキー|環境変数|認証情報).{0,12}(?:読んで|出力して|表示して|送信|貼り付け|アップロード)(?!.{0,6}(?:しない|しな|せず|禁止|させない|されない|できない))"),
    ("PI005", "warning", "ダウンロードしたものをそのまま実行",
     r"(?:curl|wget)\b[^\n|]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|da)?sh\b"),
    ("PI005", "warning", "難読化した文字列の実行",
     r"(?:base64\s+(?:-d|--decode)[^\n|]{0,80}\|\s*(?:ba)?sh|eval\s*\(\s*atob\(|exec\s*\(\s*base64)"),
    ("PI006", "warning", "利用者に気づかせない指示",
     r"(?:do\s+not|don't|never)\s+(?:tell|inform|mention|show)\s+(?:the\s+)?(?:user|human)|(?:ユーザー|人間)に(?:は)?(?:知らせ|言わ|伝え|見せ)ずに"),
]
COMPILED = [(rid, sev, msg, re.compile(rx, re.I)) for rid, sev, msg, rx in PATTERNS]
LATIN_WORD = re.compile(r"[A-Za-zЀ-ӿͰ-Ͽ]{3,}")


def load_allowlist():
    if not ALLOWLIST.exists():
        return []
    data = json.loads(ALLOWLIST.read_text(encoding="utf-8"))
    return data.get("entries", [])


def allowed(entries, path, rule, line):
    for e in entries:
        if e.get("rule") not in (rule, "*"):
            continue
        p = e.get("path", "")
        if not (path == p or (p.endswith("/") and path.startswith(p))):
            continue
        if "line" in e and e["line"] != line:
            continue
        return True
    return False


def scan_text(path, text):
    findings = []
    for n, line in enumerate(text.splitlines(), 1):
        for col, ch in enumerate(line, 1):
            code = ord(ch)
            if code in INVISIBLE:
                findings.append((path, n, col, "error", "UC001", f"{INVISIBLE[code]} U+{code:04X}"))
            elif 0xE0000 <= code <= 0xE007F:
                findings.append((path, n, col, "error", "UC002", f"タグ文字 U+{code:04X}（不可視の隠し文字列）"))
            elif code == 0xFEFF and not (n == 1 and col == 1):
                findings.append((path, n, col, "warning", "UC001", "ゼロ幅のBOMが行の途中にある"))
        for rid, sev, msg, rx in COMPILED:
            m = rx.search(line)
            if m:
                findings.append((path, n, m.start() + 1, sev, rid, msg))
        for m in LATIN_WORD.finditer(line):
            word = m.group(0)
            scripts = {unicodedata.name(c, "?").split()[0] for c in word}
            if "LATIN" in scripts and scripts & {"CYRILLIC", "GREEK"}:
                findings.append((path, n, m.start() + 1, "warning", "UC003", f"ラテン文字と他の文字が混ざった語: {word!r}"))
    return findings


def is_text(path):
    return path.suffix.lower() in TEXT_EXT or path.name in TEXT_NAMES


def git_files(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return [p for p in r.stdout.splitlines() if p] if r.returncode == 0 else []


def iter_targets(args):
    if args.staged:
        for rel in git_files("diff", "--cached", "--name-only", "--diff-filter=ACMR"):
            r = subprocess.run(["git", "show", f":{rel}"], cwd=ROOT, capture_output=True)
            if r.returncode == 0 and is_text(Path(rel)) and len(r.stdout) <= MAX_BYTES:
                yield rel, r.stdout.decode("utf-8", "replace")
        return
    if args.all:
        rels = git_files("ls-files", "--cached", "--others", "--exclude-standard")
        paths = [ROOT / p for p in rels]
    else:
        paths = []
        for raw in args.paths:
            p = Path(raw).resolve()
            if p.is_dir():
                paths += [q for q in sorted(p.rglob("*")) if q.is_file() and not (set(q.parts) & SKIP_DIRS)]
            else:
                paths.append(p)
    for p in paths:
        if not p.is_file() or not is_text(p) or p.stat().st_size > MAX_BYTES:
            continue
        try:
            rel = p.relative_to(ROOT).as_posix()
        except ValueError:
            rel = str(p)
        yield rel, p.read_text(encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--staged", action="store_true")
    ap.add_argument("--fail-on-warning", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if not (args.all or args.staged or args.paths):
        ap.error("--all / --staged / パス のどれかを指定する")
    entries = load_allowlist()
    findings, scanned = [], 0
    for rel, text in iter_targets(args):
        scanned += 1
        findings += [f for f in scan_text(rel, text) if not allowed(entries, f[0], f[4], f[1])]
    if args.json:
        print(json.dumps([dict(zip(("path", "line", "col", "severity", "rule", "message"), f)) for f in findings],
                         ensure_ascii=False, indent=2))
    else:
        for path, n, col, sev, rid, msg in findings:
            print(f"{sev.upper():7} {rid} {path}:{n}:{col} {msg}")
        errors = sum(1 for f in findings if f[3] == "error")
        print(f"{scanned}ファイルを検査: error {errors}件 / warning {len(findings) - errors}件"
              + ("（検出ゼロでも安全の証明ではない）" if not findings else ""))
    fail = any(f[3] == "error" for f in findings) or (args.fail_on_warning and findings)
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
