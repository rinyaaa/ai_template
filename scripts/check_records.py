#!/usr/bin/env python3
"""Work Item と ADR の決まりを機械的に検査する（読み取り専用）。

  python3 scripts/check_records.py            # 全件
  python3 scripts/check_records.py --staged   # 上に加え、承認済みADRの「決定」「理由」の書き換えを検査（pre-commit用）

検査するのは記録の形と関係（状態・依存・置き換え・必須の見出し）だけ。
判断が正しいか・理由が妥当かは、レビューで見る。
"""
import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import records as R  # noqa: E402

PLACEHOLDER = ("TODO", "TBD", "FIXME", "未記入")


def cycles(graph):
    """依存グラフの循環を1つずつ返す。"""
    found, state = [], {}

    def visit(node, stack):
        state[node] = 1
        for nxt in graph.get(node, []):
            if state.get(nxt) == 1:
                found.append(stack[stack.index(nxt):] + [nxt] if nxt in stack else [node, nxt])
            elif state.get(nxt) is None and nxt in graph:
                visit(nxt, stack + [nxt])
        state[node] = 2

    for n in graph:
        if state.get(n) is None:
            visit(n, [n])
    return found


def filled(text):
    return bool(text) and not any(p in text for p in PLACEHOLDER)


def check_times(errors, rid, meta, keys):
    times = {}
    for key in keys:
        t = R.parse_time(meta.get(key))
        if t is False:
            errors.append(f"{rid}: {key} はタイムゾーン付きのISO-8601で書く（例 2026-11-09T21:00:00+09:00）")
        times[key] = t or None
    if times.get("created_at") is None and "created_at" in keys:
        errors.append(f"{rid}: created_at が無い")
    for key in keys:
        if key != "created_at" and times.get(key) and times.get("created_at") and times[key] < times["created_at"]:
            errors.append(f"{rid}: {key} が created_at より前")


def check_work(works, adrs, errors):
    for wid, w in works.items():
        m, body = w["meta"], w["body"]
        if not R.SLUG.fullmatch(wid[5:]):
            errors.append(f"{wid}: ID は WORK-<英小文字・数字・ハイフン>（連番や日付を入れない）")
        if m.get("id") != wid:
            errors.append(f"{wid}: frontmatter の id がファイル名と違う（{m.get('id')}）")
        if m.get("status") not in R.WORK_STATUS:
            errors.append(f"{wid}: status は {' / '.join(R.WORK_STATUS)}")
        if m.get("priority") not in R.PRIORITY:
            errors.append(f"{wid}: priority は {' / '.join(R.PRIORITY)}")
        if m.get("design_impact") not in R.DESIGN_IMPACT:
            errors.append(f"{wid}: design_impact は {' / '.join(R.DESIGN_IMPACT)}")
        check_times(errors, wid, m, ("created_at", "updated_at"))
        for dep in R.as_list(m.get("depends_on")):
            if dep == wid:
                errors.append(f"{wid}: 自分自身に依存している")
            elif dep not in works:
                errors.append(f"{wid}: depends_on の {dep} が存在しない")
        for a in R.as_list(m.get("adrs")):
            if a not in adrs:
                errors.append(f"{wid}: adrs の {a} が存在しない")
        if m.get("status") == "blocked" and not m.get("blocked_reason"):
            errors.append(f"{wid}: blocked なら blocked_reason に具体的な理由を書く")
        if m.get("status") == "done":
            checks = R.acceptance(body)
            if not checks:
                errors.append(f"{wid}: done なのに受け入れ条件のチェックボックス（- [ ]）が1つも無い")
            elif not all(c for c, _ in checks):
                left = [t for c, t in checks if not c]
                errors.append(f"{wid}: done なのに未チェックの受け入れ条件がある: {left[0]}" + (f" ほか{len(left) - 1}件" if len(left) > 1 else ""))
            impact = m.get("design_impact")
            if impact == "pending":
                errors.append(f"{wid}: done にする前に design_impact を changed か none に決める")
            if impact == "none" and not m.get("design_impact_reason"):
                errors.append(f"{wid}: design_impact が none なら design_impact_reason に理由を書く")
            if impact == "changed" and not any(
                    adrs.get(a, {}).get("meta", {}).get("status") in ("accepted", "superseded") for a in R.as_list(m.get("adrs"))):
                errors.append(f"{wid}: design_impact が changed なら、承認済みのADRを adrs に1つ以上書く")
    graph = {wid: [d for d in R.as_list(w["meta"].get("depends_on")) if d in works] for wid, w in works.items()}
    for c in cycles(graph):
        errors.append(f"depends_on が循環している: {' → '.join(c)}")


def check_adrs(adrs, errors):
    for aid, a in adrs.items():
        m, body = a["meta"], a["body"]
        status = m.get("status")
        if not R.SLUG.fullmatch(aid[4:]):
            errors.append(f"{aid}: ID は ADR-<英小文字・数字・ハイフン>")
        if m.get("id") != aid:
            errors.append(f"{aid}: frontmatter の id がファイル名と違う（{m.get('id')}）")
        if status not in R.ADR_STATUS:
            errors.append(f"{aid}: status は {' / '.join(R.ADR_STATUS)}")
        check_times(errors, aid, m, ("created_at", "updated_at", "effective_at"))
        if status in ("accepted", "superseded"):
            if not m.get("effective_at"):
                errors.append(f"{aid}: {status} なら effective_at（有効になった日時）が要る")
            secs = R.sections(body)
            for name in R.ADR_SECTIONS:
                if not filled(secs.get(name, "")):
                    errors.append(f"{aid}: {status} なら「## {name}」に本文が要る（空・TODOは不可）")
        for key in ("supersedes", "depends_on"):
            for ref in R.as_list(m.get(key)):
                if ref == aid:
                    errors.append(f"{aid}: {key} に自分自身がある")
                elif ref not in adrs:
                    errors.append(f"{aid}: {key} の {ref} が存在しない")
        if status == "accepted":
            for old in R.as_list(m.get("supersedes")):
                if old in adrs and adrs[old]["meta"].get("status") != "superseded":
                    errors.append(f"{aid}: 承認済みで {old} を置き換えるなら、{old} の status を superseded にする")
            for dep in R.as_list(m.get("depends_on")):
                if dep in adrs and adrs[dep]["meta"].get("status") not in ("accepted", "superseded"):
                    errors.append(f"{aid}: 依存先 {dep} が承認されていない")
        if status == "superseded":
            replacers = [x for x, v in adrs.items()
                         if aid in R.as_list(v["meta"].get("supersedes")) and v["meta"].get("status") in ("accepted", "superseded")]
            if not replacers:
                errors.append(f"{aid}: superseded なのに、これを置き換えた承認済みのADRが無い")
    graph = {aid: [r for k in ("supersedes", "depends_on") for r in R.as_list(a["meta"].get(k)) if r in adrs]
             for aid, a in adrs.items()}
    for c in cycles(graph):
        errors.append(f"ADR の supersedes / depends_on が循環している: {' → '.join(c)}")


def check_accepted_unchanged(errors):
    """承認済みADRの「決定」「理由」をコミットで書き換えていないか（置き換えは新しいADRで行う）。"""
    names = subprocess.run(["git", "diff", "--cached", "--name-only", "--diff-filter=M", "--", "docs/decisions/"],
                           cwd=ROOT, capture_output=True, text=True).stdout.split()
    for rel in names:
        if not Path(rel).name.startswith("ADR-"):
            continue
        old = subprocess.run(["git", "show", f"HEAD:{rel}"], cwd=ROOT, capture_output=True, text=True)
        new = subprocess.run(["git", "show", f":{rel}"], cwd=ROOT, capture_output=True, text=True)
        if old.returncode or new.returncode:
            continue
        old_meta, old_body = R.parse(old.stdout)
        if old_meta.get("status") != "accepted":
            continue
        _, new_body = R.parse(new.stdout)
        a, b = R.sections(old_body), R.sections(new_body)
        for name in ("決定", "理由"):
            if a.get(name, "") != b.get(name, ""):
                errors.append(f"{Path(rel).stem}: 承認済みADRの「## {name}」を書き換えている。変えるなら新しいADRを作り supersedes で置き換える")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--staged", action="store_true")
    args = ap.parse_args()
    works, adrs = R.load_work(), R.load_adrs()
    errors = []
    check_work(works, adrs, errors)
    check_adrs(adrs, errors)
    if args.staged:
        check_accepted_unchanged(errors)
    for e in errors:
        print(f"ERROR {e}")
    print(f"Work Item {len(works)}件・ADR {len(adrs)}件を検査: error {len(errors)}件")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
