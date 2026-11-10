#!/usr/bin/env python3
"""Work Item・ADR を型どおりに作る。

task-intake・設計の判断をするときに、ID・日時・frontmatter・見出しを手で書く代わりに使う。
中身（各見出しの本文）はAIが書く。

  python3 scripts/new_doc.py work <slug> --title "タイトル" [--priority P2] [--issue URL] [--depends-on WORK-a,WORK-b]
  python3 scripts/new_doc.py adr <slug> --title "タイトル" [--supersedes ADR-old]
  python3 scripts/new_doc.py grep "スコープ外|範囲外"     # 過去の Work Item に同じ傾向があるか（ファイル名だけ）

slug は意味のある英小文字・数字・ハイフン（連番や日付を入れない）。作ったファイルのパスを1行出す。
同じIDのファイルが既にあれば作らずに止まる。
"""
import argparse
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import records as R  # noqa: E402

WORK = """---
id: {id}
title: {title}
status: ready
priority: {priority}
depends_on: [{depends_on}]
adrs: []
issue: {issue}
created_at: {now}
updated_at: {now}
blocked_reason:
design_impact: pending
design_impact_reason:
---

# {title}

## 依頼の原文

<!-- 依頼文をそのまま引用する（要約しない）。会話の外にあるなら出どころのリンクも書く。レビューはここと差分を突き合わせる -->

## 背景・なぜやるか

## 受け入れ条件

<!-- テスト可能な形で。完了時に全部 [x] にする（check_records.py が done のときに検査する） -->
- [ ]

## スコープ

## スコープ外

<!-- やらないことと、なぜ対象外か -->

## 決めたこと

<!-- 原文に無い判断を1行ずつ。出どころを「原文 / 確認済み / 仮決め」のどれかで書く。見送った指摘もここに -->

## 実装方針

## 並列化の単位

直列（機能が1つ / 依存があるため）

## 想定リスク・確認事項

## Evidence

<!-- 完了時に: 変えたファイル・検証したコマンドと結果・PR -->

## 詰まった点・知見

<!-- 完了時に: 詰まった点となぜそうなったか / 次に同じ領域を触る人が知っていると得をすること。効くものは CLAUDE.md かスキルへ昇格させ「→ 昇格」と添える -->
"""

ADR = """---
id: {id}
title: {title}
status: proposed
supersedes: [{supersedes}]
depends_on: []
created_at: {now}
updated_at: {now}
effective_at: null
---

# {title}

## 背景

<!-- 解決したい課題。過去の経緯が分からないなら、調べた資料と分からない範囲を書く（今日の推測を当時の判断として書かない） -->

## 決定

## 理由

<!-- 比べた代替案と、選ばなかった理由も -->

## 影響

<!-- 制約・トレードオフ・やらなくなること -->
"""

def now():
    return datetime.now().astimezone().replace(microsecond=0).isoformat()


def check_slug(slug):
    if not R.SLUG.fullmatch(slug):
        raise SystemExit("slug は英小文字・数字・ハイフンだけ（例: login-rate-limit）。連番や日付は入れない")
    return slug


def write_new(path, text):
    if path.exists():
        raise SystemExit(f"既にある: {path.relative_to(ROOT)}（同じ概念なら既存を更新する。別物なら slug をより具体的にする）")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    print(path.relative_to(ROOT))


def create_work(args):
    wid = f"WORK-{check_slug(args.slug)}"
    if args.priority not in R.PRIORITY:
        raise SystemExit(f"--priority は {' / '.join(R.PRIORITY)}")
    deps = [d.strip() for d in (args.depends_on or "").split(",") if d.strip()]
    missing = [d for d in deps if d not in R.load_work()]
    if missing:
        raise SystemExit(f"depends_on の Work Item が無い: {', '.join(missing)}")
    write_new(R.WORK_DIR / f"{wid}.md", WORK.format(
        id=wid, title=args.title, priority=args.priority, depends_on=", ".join(deps),
        issue=args.issue or "", now=now()))


def create_adr(args):
    aid = f"ADR-{check_slug(args.slug)}"
    old = [s.strip() for s in (args.supersedes or "").split(",") if s.strip()]
    missing = [s for s in old if s not in R.load_adrs()]
    if missing:
        raise SystemExit(f"supersedes の ADR が無い: {', '.join(missing)}")
    write_new(R.ADR_DIR / f"{aid}.md", ADR.format(id=aid, title=args.title, supersedes=", ".join(old), now=now()))


def grep(pattern):
    rx = re.compile(pattern)
    hits = [p for p in sorted(R.WORK_DIR.glob("WORK-*.md")) if rx.search(p.read_text(encoding="utf-8"))]
    for p in hits:
        print(p.relative_to(ROOT))
    if not hits:
        print("0件（今回が1回目）")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="kind", required=True)
    w = sub.add_parser("work")
    w.add_argument("slug")
    w.add_argument("--title", required=True)
    w.add_argument("--priority", default="P2")
    w.add_argument("--issue")
    w.add_argument("--depends-on")
    a = sub.add_parser("adr")
    a.add_argument("slug")
    a.add_argument("--title", required=True)
    a.add_argument("--supersedes")
    g = sub.add_parser("grep")
    g.add_argument("pattern")
    args = ap.parse_args()
    {"work": create_work, "adr": create_adr, "grep": lambda a: grep(a.pattern)}[args.kind](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
