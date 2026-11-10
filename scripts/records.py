"""Work Item（docs/work-items/）と ADR（docs/decisions/）の読み取り。check_records・work_items・review_bundle が共有する。

frontmatter は YAML の小さな部分集合だけを扱う（`key: value`、1行の配列 `[a, b]`、空・null）。
依存を増やさないため PyYAML は使わない。
"""
import re
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK_DIR = ROOT / "docs/work-items"
ADR_DIR = ROOT / "docs/decisions"

WORK_STATUS = ("backlog", "ready", "in-progress", "blocked", "done", "cancelled")
PRIORITY = ("P0", "P1", "P2", "P3")
DESIGN_IMPACT = ("pending", "changed", "none")
ADR_STATUS = ("proposed", "accepted", "rejected", "superseded")
ADR_SECTIONS = ("背景", "決定", "理由", "影響")
SLUG = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*")


def parse_value(raw):
    raw = raw.strip()
    if raw in ("", "null", "~"):
        return None
    if raw.startswith("[") and raw.endswith("]"):
        return [v.strip().strip("\"'") for v in raw[1:-1].split(",") if v.strip()]
    return raw.strip("\"'")


def parse(text):
    """(frontmatter の dict, 本文) を返す。frontmatter が無ければ ({}, text)。"""
    if not text.startswith("---\n"):
        return {}, text
    end = text.find("\n---", 4)
    if end == -1:
        return {}, text
    meta = {}
    for line in text[4:end].splitlines():
        m = re.match(r"^([a-z_]+):(.*)$", line)
        if m:
            meta[m.group(1)] = parse_value(m.group(2))
    body = text[end + 4:].lstrip("\n")
    return meta, body


def sections(body):
    """## 見出し → 本文（HTMLコメントを除いて strip したもの）。"""
    out, name, buf = {}, None, []
    for line in body.splitlines():
        m = re.match(r"^##\s+(.+?)\s*$", line)
        if m:
            if name is not None:
                out[name] = "\n".join(buf)
            name, buf = m.group(1), []
        elif name is not None:
            buf.append(line)
    if name is not None:
        out[name] = "\n".join(buf)
    return {k: re.sub(r"<!--.*?-->", "", v, flags=re.S).strip() for k, v in out.items()}


def acceptance(body):
    """受け入れ条件のチェックボックス [(checked, text)]。"""
    sec = sections(body).get("受け入れ条件", "")
    return [(m.group(1).lower() == "x", m.group(2).strip())
            for m in re.finditer(r"^\s*-\s*\[([ xX])\]\s*(.+)$", sec, re.M)]


def parse_time(value):
    if not value:
        return None
    try:
        t = datetime.fromisoformat(value)
    except ValueError:
        return False
    return t if t.tzinfo else False


def load(directory, prefix):
    """{id: {"path", "meta", "body"}}。ID はファイル名から取る。"""
    items = {}
    if not directory.exists():
        return items
    for path in sorted(directory.glob(f"{prefix}-*.md")):
        meta, body = parse(path.read_text(encoding="utf-8"))
        items[path.stem] = {"path": path, "meta": meta, "body": body}
    return items


def load_work(root=ROOT):
    return load(root / "docs/work-items", "WORK")


def load_adrs(root=ROOT):
    return load(root / "docs/decisions", "ADR")


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]
