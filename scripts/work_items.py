#!/usr/bin/env python3
"""Work Item の一覧と、次にやる作業を出す（読み取り専用）。

  python3 scripts/work_items.py          # 状態ごとの一覧
  python3 scripts/work_items.py --next   # 次の1件（進行中があればそれ。無ければ着手できる ready の先頭）

着手できる = status が ready で、depends_on が全部 done。並びは priority → created_at → ID。
この並びは表示のためのもので、優先度の判断そのものではない。
"""
import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import records as R  # noqa: E402


def order_key(item):
    m = item[1]["meta"]
    p = m.get("priority")
    return (R.PRIORITY.index(p) if p in R.PRIORITY else 9, m.get("created_at") or "", item[0])


def waiting_on(works, wid):
    return [d for d in R.as_list(works[wid]["meta"].get("depends_on"))
            if works.get(d, {}).get("meta", {}).get("status") != "done"]


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--next", action="store_true")
    args = ap.parse_args()
    works = R.load_work()
    rows = sorted(works.items(), key=order_key)
    in_progress = [(k, v) for k, v in rows if v["meta"].get("status") == "in-progress"]
    ready = [(k, v) for k, v in rows if v["meta"].get("status") == "ready" and not waiting_on(works, k)]

    def line(k, v):
        m = v["meta"]
        extra = ""
        if waiting_on(works, k):
            extra = f"  依存待ち: {', '.join(waiting_on(works, k))}"
        if m.get("status") == "blocked":
            extra += f"  止まっている理由: {m.get('blocked_reason')}"
        return f"- {k} [{m.get('priority')}] {m.get('title', '')}{extra}  ({v['path'].relative_to(ROOT)})"

    if args.next:
        pick = (in_progress or ready or [None])[0]
        if pick is None:
            print("着手できる Work Item が無い（ready が無いか、全部が依存待ち）")
            return 0
        print(("続き（進行中）: " if in_progress else "次: ") + line(*pick)[2:])
        return 0
    if not works:
        print("Work Item はまだ無い（作るときは python3 scripts/new_doc.py work <slug> --title ...）")
        return 0
    for status in R.WORK_STATUS:
        items = [(k, v) for k, v in rows if v["meta"].get("status") == status]
        if status in ("done", "cancelled"):
            if items:
                print(f"## {status}: {len(items)}件")
            continue
        if items:
            print(f"## {status}")
            print("\n".join(line(k, v) for k, v in items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
