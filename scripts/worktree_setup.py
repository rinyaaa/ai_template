#!/usr/bin/env python3
"""parallel-worktree の Step 2〜3（ワークツリー作成と依存のインストール）を1コマンドで行う。

  python3 scripts/worktree_setup.py <機能名>             # 作成 + 依存インストール
  python3 scripts/worktree_setup.py <機能名> --no-install
  python3 scripts/worktree_setup.py --list               # 後始末の候補を列挙（削除はしない）

置き場所はリポジトリ外の兄弟ディレクトリ ../<repo>-worktrees/<機能名>、ブランチは feature/<機能名>。
追加する操作だけを行う。ワークツリーの削除（git worktree remove / prune）は人間に依頼する。
.env などgit管理外の設定ファイルはコピーしない（必要なファイル名だけを出す）。
"""
import argparse
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _gitutil import git  # noqa: E402
from detect_stack import detect  # noqa: E402

MAX_TREES = 5


def default_base():
    ref = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False).strip()
    return ref.replace("origin/", "", 1) if ref else "main"


def worktrees():
    trees, cur = [], {}
    for line in git("worktree", "list", "--porcelain").splitlines():
        if line.startswith("worktree "):
            cur = {"path": line[9:]}
            trees.append(cur)
        elif line.startswith("branch "):
            cur["branch"] = line[7:].replace("refs/heads/", "")
    return trees[1:]  # 先頭は本体


def list_cleanup():
    base = default_base()
    merged = set(git("branch", "--merged", base, "--format=%(refname:short)", check=False).split())
    rows = []
    for t in worktrees():
        dirty = subprocess.run(["git", "-C", t["path"], "status", "--porcelain"],
                               capture_output=True, text=True).stdout.strip()
        state = "マージ済み" if t.get("branch") in merged else "未マージ"
        state += "・未コミットの変更あり" if dirty else "・未コミットの変更なし"
        rows.append(f"- {t['path']} / ブランチ {t.get('branch', '?')}（{state}）")
    if not rows:
        print("追加のワークツリーは無い")
        return 0
    print(f"ワークツリー一覧（{base} 基準）。削除してよいのは「マージ済み・未コミットの変更なし」のものだけ:")
    print("\n".join(rows))
    print("削除は人間が行う: git worktree remove <パス> / git branch -d <ブランチ>")
    return 0


def create(name, install):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", name):
        raise SystemExit("機能名は英小文字・数字・ハイフンだけにする（ブランチ名とディレクトリ名に使う）")
    if len(worktrees()) >= MAX_TREES:
        raise SystemExit(f"ワークツリーが既に{MAX_TREES}つある。増やす前に人間に確認する（レビューが追いつかない）")
    repo = ROOT.name
    path = ROOT.parent / f"{repo}-worktrees" / name
    base = default_base()
    git("worktree", "add", str(path), "-b", f"feature/{name}", base)
    print(f"作成: {path}（ブランチ feature/{name}、起点 {base}）")
    info = detect(path)
    if install and info["install"]:
        print(f"依存のインストール: {info['install']}")
        r = subprocess.run(info["install"], shell=True, cwd=path)
        if r.returncode != 0:
            print("依存のインストールに失敗した。ここを直さずに並列実装を始めない", file=sys.stderr)
            return 1
    elif install:
        print("依存のインストール方法を判定できない（ロックファイルなし）。必要なら人間に確認する")
    ignored = [p for p in (".env", ".env.local", ".env.development") if (ROOT / p).exists()]
    if ignored:
        print(f"git管理外の設定ファイルは新しいツリーに無い（中身はコピーしない）: {', '.join(ignored)}")
    print("devサーバを同時に起動するなら、CLAUDE.md の起動コマンド欄にあるポートの変え方でずらす")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("name", nargs="?")
    ap.add_argument("--no-install", action="store_true")
    ap.add_argument("--list", action="store_true")
    args = ap.parse_args()
    if args.list:
        return list_cleanup()
    if not args.name:
        ap.error("機能名か --list を指定する")
    return create(args.name, not args.no_install)


if __name__ == "__main__":
    sys.exit(main())
