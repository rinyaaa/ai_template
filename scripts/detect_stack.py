#!/usr/bin/env python3
"""技術スタック・パッケージマネージャ・lint/test/audit コマンドを検出する（読み取り専用）。

claude-project-setup（Step 1）・parallel-worktree（依存のインストール）・
project-health-check（依存の脆弱性）が、AIに毎回ファイルを探させる代わりに使う。

  python3 scripts/detect_stack.py          # 人間向け
  python3 scripts/detect_stack.py --json   # スキルから使う
  python3 scripts/detect_stack.py --install-cmd   # 依存インストールのコマンドだけを1行で出す

「コマンドはあるが設定ファイルが無い」ような怪しい状態は gaps に出す。推測で埋めない。
"""
import argparse
import json
import sys
from pathlib import Path

# (ロックファイル, パッケージマネージャ, インストール, 脆弱性検査)
LOCKFILES = [
    ("pnpm-lock.yaml", "pnpm", "pnpm install --frozen-lockfile", "pnpm audit"),
    ("package-lock.json", "npm", "npm ci", "npm audit"),
    ("yarn.lock", "yarn", "yarn install --frozen-lockfile", "yarn audit"),
    ("bun.lockb", "bun", "bun install", None),
    ("bun.lock", "bun", "bun install", None),
    ("uv.lock", "uv", "uv sync", "uvx pip-audit"),
    ("poetry.lock", "poetry", "poetry install", "pip-audit"),
    ("Pipfile.lock", "pipenv", "pipenv install --dev", "pip-audit"),
    ("requirements.txt", "pip", "python3 -m venv .venv && .venv/bin/pip install -r requirements.txt", "pip-audit -r requirements.txt"),
    ("go.sum", "go", "go mod download", "govulncheck ./..."),
    ("Cargo.lock", "cargo", "cargo fetch", "cargo audit"),
    ("Gemfile.lock", "bundler", "bundle install", "bundle audit"),
]
MANIFESTS = {
    "package.json": "node", "pyproject.toml": "python", "requirements.txt": "python",
    "go.mod": "go", "Cargo.toml": "rust", "Gemfile": "ruby",
}
LINT_CONFIGS = {
    "eslint": ["eslint.config.js", "eslint.config.mjs", "eslint.config.ts", ".eslintrc", ".eslintrc.js", ".eslintrc.json", ".eslintrc.cjs"],
    "biome": ["biome.json", "biome.jsonc"],
    "ruff": ["ruff.toml", ".ruff.toml"],
    "flake8": [".flake8"],
    "golangci": [".golangci.yml", ".golangci.yaml"],
    "rubocop": [".rubocop.yml"],
}
FRONTEND_DEPS = {"react", "vue", "svelte", "next", "nuxt", "@angular/core", "solid-js", "astro"}
GITIGNORE = {
    "node": ["node_modules/", "dist/", "build/", ".next/"],
    "python": ["__pycache__/", "*.pyc", ".venv/", "venv/", "*.egg-info/"],
    "go": ["/bin/"],
    "rust": ["target/"],
    "ruby": [".bundle/", "vendor/bundle/"],
}
ALWAYS_IGNORE = [".env", ".env.*", ".DS_Store", ".claude/settings.local.json"]


def detect(root: Path) -> dict:
    found = {"stacks": [], "package_manager": None, "install": None, "audit": None,
             "commands": {}, "linters": [], "frontend": False, "gitignore_missing": [], "gaps": []}
    for name, stack in MANIFESTS.items():
        if (root / name).exists() and stack not in found["stacks"]:
            found["stacks"].append(stack)
    for lock, pm, install, audit in LOCKFILES:
        if (root / lock).exists():
            found.update(package_manager=pm, install=install, audit=audit)
            break
    if found["stacks"] and not found["package_manager"]:
        found["gaps"].append("ロックファイルが無く、パッケージマネージャを確定できない（ユーザーに聞く）")

    pkg = root / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
        except ValueError:
            data = {}
            found["gaps"].append("package.json がJSONとして読めない")
        run = {"npm": "npm run", "pnpm": "pnpm run", "yarn": "yarn", "bun": "bun run"}.get(found["package_manager"], "npm run")
        for key, cmd in (data.get("scripts") or {}).items():
            if key in ("dev", "start", "build", "test", "lint", "format", "typecheck", "type-check", "check"):
                found["commands"][key] = f"{run} {key}  # {cmd}"
        deps = set(data.get("dependencies") or {}) | set(data.get("devDependencies") or {})
        found["frontend"] = bool(deps & FRONTEND_DEPS)
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        body = pyproject.read_text(encoding="utf-8")
        if "[tool.pytest" in body or (root / "pytest.ini").exists():
            found["commands"].setdefault("test", "pytest")
        if "[tool.ruff" in body:
            found["linters"].append("ruff")
    if (root / "go.mod").exists():
        found["commands"].setdefault("test", "go test ./...")
        found["commands"].setdefault("lint", "go vet ./...")
    if (root / "Cargo.toml").exists():
        found["commands"].setdefault("test", "cargo test")
        found["commands"].setdefault("lint", "cargo clippy")

    for linter, files in LINT_CONFIGS.items():
        if any((root / f).exists() for f in files) and linter not in found["linters"]:
            found["linters"].append(linter)
    if "lint" in found["commands"] and not found["linters"] and "node" in found["stacks"]:
        found["gaps"].append("lint コマンドはあるが、lintの設定ファイルが見つからない（実行できるか未確認）")

    gi = root / ".gitignore"
    have = set(gi.read_text(encoding="utf-8").split()) if gi.exists() else set()
    wanted = ALWAYS_IGNORE + [p for s in found["stacks"] for p in GITIGNORE.get(s, [])]
    found["gitignore_missing"] = [p for p in dict.fromkeys(wanted) if p not in have]
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=".")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--install-cmd", action="store_true")
    args = ap.parse_args()
    info = detect(Path(args.root).resolve())
    if args.install_cmd:
        if not info["install"]:
            print("依存のインストール方法を判定できない（ロックファイルなし）", file=sys.stderr)
            return 1
        print(info["install"])
        return 0
    if args.json:
        print(json.dumps(info, ensure_ascii=False, indent=2))
        return 0
    print(f"スタック: {', '.join(info['stacks']) or '（検出なし）'}")
    print(f"パッケージマネージャ: {info['package_manager'] or '不明'}")
    print(f"インストール: {info['install'] or '不明'}")
    print(f"脆弱性検査: {info['audit'] or '不明'}")
    for k, v in info["commands"].items():
        print(f"  {k}: {v}")
    print(f"linter設定: {', '.join(info['linters']) or 'なし'} / フロントエンド: {'あり' if info['frontend'] else 'なし'}")
    if info["gitignore_missing"]:
        print(f".gitignore に無いもの: {' '.join(info['gitignore_missing'])}")
    for g in info["gaps"]:
        print(f"要確認: {g}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
