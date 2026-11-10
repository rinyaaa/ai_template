#!/usr/bin/env python3
"""safe-rollback の Step 1（凍結・把握）と Step 3（退避）を1コマンドで行う。

  python3 scripts/rollback_snapshot.py          # 把握だけ（読み取り専用）
  python3 scripts/rollback_snapshot.py --save   # 把握 + 今の状態を backup/ ブランチに退避

退避は「作業ツリー丸ごと（未コミット・未追跡を含む）を1コミットにして、新しいブランチを指させる」だけ。
作業ツリー・index・今のブランチは一切変わらない（stash の push/pop も使わない）。
戻すときは `git switch -c <名前> backup/...` や `git checkout backup/... -- <ファイル>` で取り出せる。
"""
import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from _gitutil import git, snapshot_tree  # noqa: E402


def summary():
    branch = git("branch", "--show-current").strip() or "(detached HEAD)"
    status = git("status", "--porcelain").splitlines()
    print(f"ブランチ: {branch}")
    print(f"未コミットの変更: {len(status)}ファイル")
    for line in status[:20]:
        print(f"  {line}")
    if len(status) > 20:
        print(f"  ...ほか{len(status) - 20}件")
    stat = git("diff", "--stat", "HEAD", check=False).strip().splitlines()
    if stat:
        print(f"差分の規模: {stat[-1].strip()}")
    print("最近のコミット:")
    for line in git("log", "--oneline", "--date=short", "--format=%h %ad %s", "-15").splitlines():
        print(f"  {line}")
    stashes = git("stash", "list").splitlines()
    if stashes:
        print(f"退避済みの stash: {len(stashes)}件（消さない）")
        for line in stashes[:5]:
            print(f"  {line}")
    backups = git("branch", "--list", "backup/*").split()
    if backups:
        print(f"既存の退避ブランチ: {', '.join(b for b in backups if b != '*')}")
    upstream = git("rev-parse", "--abbrev-ref", "@{u}", check=False).strip()
    if upstream:
        ahead = git("rev-list", "--count", f"{upstream}..HEAD", check=False).strip()
        print(f"上流 {upstream} より先のコミット（未push）: {ahead}件")
    return status


def _ident_env():
    """退避コミットの作者。git が名前・メールを決められない環境（CI・初期設定前の PC）でも退避を止めない。"""
    ok = all(git("var", v, check=False, env=os.environ).strip()
             for v in ("GIT_AUTHOR_IDENT", "GIT_COMMITTER_IDENT"))
    if ok:
        return None
    fallback = {"NAME": "rollback_snapshot", "EMAIL": "rollback-snapshot@localhost"}
    return dict(os.environ, **{f"GIT_{who}_{k}": v for who in ("AUTHOR", "COMMITTER") for k, v in fallback.items()})


def save(dirty):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"backup/before-rollback-{stamp}"
    head = git("rev-parse", "HEAD").strip()
    if dirty:
        tree = snapshot_tree()
        target = git("commit-tree", tree, "-p", head, "-m", f"rollback前の作業ツリー退避 {stamp}",
                     env=_ident_env()).strip()
    else:
        target = head
    git("branch", name, target)
    print(f"\n退避した: {name} → {target[:8]}" + ("（未コミット・未追跡の変更を含む）" if dirty else ""))
    print("作業ツリーと今のブランチは変えていない。この後の操作で何が起きても、この時点には戻れる。")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--save", action="store_true", help="backup/ ブランチに退避する")
    args = ap.parse_args()
    dirty = summary()
    if args.save:
        save(bool(dirty))
    return 0


if __name__ == "__main__":
    sys.exit(main())
