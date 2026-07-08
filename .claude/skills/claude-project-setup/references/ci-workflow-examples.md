# CIワークフロー・依存メンテナンスの雛形集

claude-project-setupスキルのStep 3（GitHub利用時）で `.github/workflows/ci.yml` や `.github/dependabot.yml` を生成する際の参照テンプレート。**そのままコピーせず、Step 1で検出した実際のコマンド（lint/test/build）に必ず置き換える**こと。検出できていないコマンドをCIに書くと、初回から赤いバツが付き続けて「CIは壊れているのが普通」という最悪の学習をユーザーに与えてしまう。lintが無いならlintジョブを削る。

## 共通の方針

- トリガーは `pull_request` と `push`（デフォルトブランチ）の両方。PRを使わない運用でもpushで検査が走るようにする。
- ジョブは「lint」「test」「依存の脆弱性チェック」の3種を基本とし、検出できたものだけ入れる。加えて「シークレットスキャン」（後述）は技術スタックに依存しないので、**検出結果に関係なく常に入れる**。
- 非エンジニアモードのプロジェクトでは、CIは「ローカルのhookをすり抜けた変更を最後に止める層」なので、生成をスキップしない。CIが失敗したときに何を意味するかをStep 6で平易に説明する（「GitHub上で自動チェックが失敗すると、その変更は取り込まない約束になっています」等）。

## Node.js（npm の例。yarn/pnpm はコマンドを読み替える）

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with:
          node-version: 22        # プロジェクトの .nvmrc / package.json engines に合わせる
          cache: npm
      - run: npm ci
      - run: npm run lint         # scripts.lint が存在する場合のみ
      - run: npm test             # scripts.test が存在する場合のみ
      - run: npm audit --audit-level=high   # 依存の既知脆弱性チェック
```

## Python（uv の例。Poetry/pip はコマンドを読み替える）

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run ruff check .        # ruffを検出した場合
      - run: uv run pytest              # pytestを検出した場合
      - run: uv run pip-audit           # pip-audit未導入なら `uvx pip-audit` でも可
```

## Go

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - run: go vet ./...
      - run: go test ./...
      - uses: golang/govulncheck-action@v1   # 依存の脆弱性チェック
```

## Rust

```yaml
name: CI
on:
  pull_request:
  push:
    branches: [main]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo clippy -- -D warnings
      - run: cargo test
      - run: cargo install cargo-audit && cargo audit
```

## シークレットスキャン（全スタック共通・常に入れる）

security-guidanceプラグインは「Claudeがコードを書くとき」、go-live-checklistは「公開の直前」を見るが、人間がGitHub上で直接コミットした秘密情報を継続的に見張る層はCIにしか置けない。gitleaksのジョブを `ci.yml` に追加する。

```yaml
  secret-scan:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0        # コミット履歴全体を検査する
      - uses: gitleaks/gitleaks-action@v2
        env:
          GITHUB_TOKEN: ${{ github.token }}
```

注意点：

- gitleaks-action は個人リポジトリでは無料だが、**Organizationのリポジトリではライセンスキー（無料申請可）を `GITLEAKS_LICENSE` シークレットに設定する必要がある**。Organizationで使う場合はその手順を案内し、すぐ用意できないなら gitleaks CLI を直接実行する形（`docker run --rm -v $PWD:/repo zricethezav/gitleaks:latest detect --source /repo`）に差し替える。
- 検出があった場合にやるべきことは「履歴の掃除」より先に「**そのキーの無効化・再発行**」。この順序をCLAUDE.mdの運用ルールに書いておく（go-live-checklistのStep 2と同じ方針）。

あわせて、GitHub本体のシークレット防御も案内する（CIより手前で効く層）：

- **Secret scanning / Push protection**: リポジトリの Settings → Code security and analysis で有効化。秘密情報を含むpush自体をGitHub側が拒否してくれる。**公開リポジトリでは無料**。プライベートリポジトリでは GitHub Advanced Security（有料）が必要なので、契約が無ければ上のgitleaksジョブが実質的な代替になる——どちらが効いているかをStep 6の報告で明確にする。

## Dependabot（`.github/dependabot.yml`）

依存パッケージの脆弱性・更新を、誰も見ていなくてもGitHub側から自動でPRとして届けてくれる仕組み。エコシステムはStep 1の検出結果に合わせて選ぶ（npm / pip / gomod / cargo / bundler 等）。GitHub Actionsを使うなら `github-actions` のエントリも足しておくと、上のCIで使うaction自体の更新も追従できる。

```yaml
version: 2
updates:
  - package-ecosystem: npm          # 検出したエコシステムに置き換える
    directory: /
    schedule:
      interval: weekly
  - package-ecosystem: github-actions
    directory: /
    schedule:
      interval: weekly
```

非エンジニアモードでは、DependabotのPRを「誰がどう扱うか」まで決めないと放置される。Step 6で「週に一度、届いた更新PRをClaude Codeに『DependabotのPRを確認して』と依頼し、CIが通っていれば取り込む」のような運用文をCLAUDE.mdに残すことを提案する。

## ブランチ保護（CIを「強制」に変える設定）

CIワークフローを置いただけでは「失敗しても取り込める」状態のまま。デフォルトブランチへの直pushを防ぎ、CI成功をマージ条件にするには、リポジトリ側の設定が必要になる。これはリポジトリ内のファイルでは完結しないので、次のどちらかを案内する。

- **GitHub UIから**: リポジトリの Settings → Rules → Rulesets で、デフォルトブランチを対象に「Require a pull request before merging」と「Require status checks to pass」（上のCIの `check` ジョブを指定）を有効にする。
- **gh CLIから**（ユーザーの合意を得てから実行する）:

```bash
gh api repos/{owner}/{repo}/rulesets -X POST --input - <<'EOF'
{
  "name": "protect-default-branch",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["~DEFAULT_BRANCH"], "exclude": [] } },
  "rules": [
    { "type": "pull_request", "parameters": { "required_approving_review_count": 0, "dismiss_stale_reviews_on_push": false, "require_code_owner_review": false, "require_last_push_approval": false, "required_review_thread_resolution": false } },
    { "type": "required_status_checks", "parameters": { "strict_required_status_checks_policy": false, "required_status_checks": [ { "context": "check" } ] } }
  ]
}
EOF
```

`required_approving_review_count` はチームに人間のレビュアーがいるなら1以上に、非エンジニアのみのチームなら0にして代わりに「マージ前に `/security-review` を実行する」運用をCLAUDE.mdに明記する。無料プランのプライベートリポジトリではルールセット/ブランチ保護が使えない場合がある——その場合は設定できない事実を隠さず、「直pushをしない」を運用ルールとしてCLAUDE.mdに書くにとどめる。