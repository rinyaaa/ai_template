"""スクリプト間で共有するgitの小道具。作業ツリー・index・既存のブランチを書き換える操作は持たない。"""
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def git(*args, check=True, root=ROOT):
    r = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True, stdin=subprocess.DEVNULL)
    if check and r.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} に失敗: {r.stderr.strip()}")
    return r.stdout


def snapshot_tree(root=ROOT):
    """作業ツリー（未コミット・未追跡を含む。.gitignore は除く）を tree オブジェクトにして返す。

    一時的な index を使うので、作業ツリー・本来の index・ブランチには触れない。
    """
    with tempfile.TemporaryDirectory() as tmp:
        env = dict(os.environ, GIT_INDEX_FILE=str(Path(tmp) / "index"))
        has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"], cwd=root,
                                  capture_output=True).returncode == 0
        steps = ([["git", "read-tree", "HEAD"]] if has_head else []) + [["git", "add", "-A"], ["git", "write-tree"]]
        for cmd in steps:
            r = subprocess.run(cmd, cwd=root, env=env, capture_output=True, text=True)
            if r.returncode != 0:
                raise SystemExit(f"{' '.join(cmd)} に失敗: {r.stderr.strip()}")
        return r.stdout.strip()
