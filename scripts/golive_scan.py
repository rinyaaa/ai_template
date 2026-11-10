#!/usr/bin/env python3
"""go-live-checklist の Step 2 のうち、機械的に確かめられる部分をまとめて走らせる（読み取り専用）。

  python3 scripts/golive_scan.py            # 公開前の棚卸し（追跡中の全ファイルと履歴）
  python3 scripts/golive_scan.py --staged   # コミット前（.githooks/pre-commit から）: コミットする中身の秘密情報だけ

見るもの: ハードコードされた秘密情報らしき文字列 / .env 系の追跡・履歴への混入 /
CORS の全開設定 / デバッグ設定 / 依存の脆弱性コマンドの有無。
**ここで何も出なくても「安全」ではない。** 認証・認可の設計、他人のデータに届かないか、
露出面の妥当性はAIがコードを読んで判断する（スキルの Step 2 の残り）。

秘密情報らしき文字列は、値を伏せて「ファイル:行 と 種類」だけを出す（出力に秘密を含めない）。
"""
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from detect_stack import detect  # noqa: E402

SECRET_PATTERNS = [
    ("AWSアクセスキー", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GitHubトークン", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("OpenAI/Anthropic系キー", re.compile(r"\bsk-(?:ant-)?[A-Za-z0-9_-]{20,}\b")),
    ("Slackトークン", re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b")),
    ("Google APIキー", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("秘密鍵", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----")),
    ("直書きの認証情報", re.compile(
        r"""(?i)\b(?:api[_-]?key|secret|password|passwd|token|access[_-]?key)\b\s*[:=]\s*["'][^"'\s]{8,}["']""")),
]
CORS_OPEN = re.compile(r"""(?i)(access-control-allow-origin["']?\s*[:,]\s*["']\*|origin\s*[:=]\s*["']\*["']|cors\(\s*\))""")
DEBUG_ON = re.compile(r"""(?i)^\s*(?:DEBUG\s*=\s*True|app\.debug\s*=\s*True|debug\s*:\s*true)\b""")
SKIP_DIRS = ("node_modules/", "vendor/", "dist/", "build/", ".venv/")
SKIP_SELF = {"scripts/golive_scan.py", "scripts/tests/test_scripts.py"}
ENV_OK = re.compile(r"\.env\.(example|sample|template|dist)$")


def git(*args):
    r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True)
    return r.stdout if r.returncode == 0 else ""


def tracked_text_files():
    for path in git("ls-files").splitlines():
        if path.startswith(SKIP_DIRS) or path in SKIP_SELF:
            continue
        p = ROOT / path
        try:
            if p.stat().st_size > 1_000_000:
                continue
            yield path, p.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue


def staged_files():
    for path in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        if path.startswith(SKIP_DIRS) or path in SKIP_SELF:
            continue
        r = subprocess.run(["git", "show", f":{path}"], cwd=ROOT, capture_output=True)
        if r.returncode != 0 or len(r.stdout) > 1_000_000:
            continue
        try:
            yield path, r.stdout.decode("utf-8")
        except UnicodeDecodeError:
            continue


def staged_main():
    """コミットされる中身（index）だけを見る。秘密情報があれば exit 1。値は出さない。"""
    found = []
    for path in git("diff", "--cached", "--name-only", "--diff-filter=ACMR").splitlines():
        if re.search(r"(^|/)\.env(\.|$)", path) and not ENV_OK.search(path):
            found.append(f"{path}: .env 系のファイルをコミットしようとしている")
    for path, text in staged_files():
        for n, line in enumerate(text.splitlines(), 1):
            for kind, rx in SECRET_PATTERNS:
                if rx.search(line):
                    found.append(f"{path}:{n} 秘密情報らしき文字列（{kind}）")
    if found:
        print("コミットを止めた: 秘密情報らしきものが含まれている（値は表示しない）", file=sys.stderr)
        for f in dict.fromkeys(found):
            print(f"- {f}", file=sys.stderr)
        print("本物なら: コミットから外し、環境変数などへ移す。既に共有・pushしたキーなら無効化・再発行する。", file=sys.stderr)
        print("誤検知なら: 値をダミーに置き換える（例: テストでは文字列を連結して組み立てる）。--no-verify で回避しない。", file=sys.stderr)
        return 1
    return 0


def main():
    if "--staged" in sys.argv[1:]:
        return staged_main()
    findings = {"直してから公開": [], "要確認": [], "情報": []}
    for path, text in tracked_text_files():
        for n, line in enumerate(text.splitlines(), 1):
            for kind, rx in SECRET_PATTERNS:
                if rx.search(line):
                    findings["直してから公開"].append(f"{path}:{n} 秘密情報らしき文字列（{kind}）")
            if CORS_OPEN.search(line):
                findings["要確認"].append(f"{path}:{n} CORSが全開の可能性")
            if DEBUG_ON.search(line):
                findings["要確認"].append(f"{path}:{n} デバッグ設定が有効の可能性（本番設定か確認）")

    tracked_env = [p for p in git("ls-files").splitlines()
                   if re.search(r"(^|/)\.env(\.|$)", p) and not ENV_OK.search(p)]
    for p in tracked_env:
        findings["直してから公開"].append(f"{p} が Git で追跡されている（中のキーは漏れたものとして無効化・再発行）")
    history = sorted({p for p in git("log", "--all", "--diff-filter=A", "--name-only", "--format=").splitlines()
                      if re.search(r"(^|/)\.env(\.|$)", p) and not ENV_OK.search(p)} - set(tracked_env))
    for p in history:
        findings["直してから公開"].append(f"{p} が過去のコミット履歴に入っていた（キーの無効化・再発行を先に）")

    stack = detect(ROOT)
    if stack["audit"]:
        findings["情報"].append(f"依存の脆弱性は `{stack['audit']}` で確認する")
    else:
        findings["情報"].append("依存の脆弱性検査コマンドを判定できない（スタック未検出）")

    for title, rows in findings.items():
        if rows:
            print(f"## {title}")
            for r in dict.fromkeys(rows):
                print(f"- {r}")
    if not findings["直してから公開"] and not findings["要確認"]:
        print("機械的な検査では検出なし。認証・認可・露出面はコードを読んで確認する。")
    return 1 if findings["直してから公開"] else 0


if __name__ == "__main__":
    sys.exit(main())
