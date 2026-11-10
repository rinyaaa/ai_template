---
name: claude-project-setup
description: 「セットアップして」「環境構築して」「init」「このプロジェクトでClaude Codeを使えるようにして」「開発を始めたいので準備して」「事故らないようにしたい」「危険な操作を防ぎたい」「lint/testの放置を防ぎたい」で発動。AI用の設定（権限・hooks・CLAUDE.md・必要な skill/command/agent）を対話でセットアップする。
---

# Claude Project Setup

テンプレートを機械的に流し込むのではなく、**そのプロジェクトの開発フローに合った設定を対話で見極めて反映する**。自動検出できることは聞かず、分からないことだけを段階的に聞く。組み込みの `/init` は CLAUDE.md の説明書きに特化しているので、権限・hook・スキルが絡むならこちら。

詳しい判断基準は必要になったときだけ読む:

| ファイル | 読むとき |
| --- | --- |
| `references/settings-and-plugins.md` | Step 3（allow の決め方・deny ベースラインの扱い・プラグイン・GitHub の CI・`.gitignore`） |
| `references/ci-workflow-examples.md` | Step 3 で GitHub の CI・Dependabot を作るとき |

## Step 1: 自動検出

```bash
python3 scripts/detect_stack.py
```

スタック・パッケージマネージャ・dev/build/test/lint コマンド・linter 設定・フロントエンドの有無・`.gitignore` に無いもの・要確認（gaps）が出る。あわせて既存の `.claude/`・`CLAUDE.md` の中身を読む。**gaps（ロックファイルが無い、lint コマンドはあるが設定が無い等）は推測で埋めず**、Step 2 で聞くか報告に書く（「動く」と偽って書かない）。

## Step 2: 対話で補う

AskUserQuestion（使えなければ普通の質問文）で、検出できなかったことだけを聞く。必ず確かめる2つ:

1. **他のAIツール（Codex・Cursor）も使うか。** 使うなら `.codex/hooks.json`・`.cursor/hooks.json` が同梱されていることを伝え、Codex は hook 機能の有効化が要ること、ツールを問わず効くのは `.githooks/`（`git config core.hooksPath .githooks`）と CI だけであることを伝える。GitHub の CI・ブランチ保護の優先度を一段上げる
2. **繰り返す作業**（デプロイ・決まった形のレビュー・マイグレーション・定型の調査など）。あれば形を決める:
   - 手順が決まっていて判断が要らない → **スクリプト**（`scripts/`。AIは出力の要約だけを読む。トークンが最も少ない）
   - 引数を取ってすぐ実行する短い定型操作 → **Command**（`.claude/commands/*.md`）
   - 判断を伴う複数ステップ・トリガーで自動発動してほしい → **Skill**（決まった部分はスクリプトにして呼ぶ）
   - 役割・ツールを絞って別の文脈で動かしたい → **Subagent**（`.claude/agents/*.md`）
   作りたいものが無ければ作らない

## Step 3: 設定を作る・更新する

`references/settings-and-plugins.md` を読んでから行う。要点:

- `permissions.allow` には状態を壊さず すぐ終わるコマンドだけ。破壊的な操作は決して入れない。常駐プロセス（dev サーバ）は一言確認してから
- deny ベースラインと hook（`deny_dangerous_bash.py`・`stop_verify.py`）は**消さない**。明示的に頼まれたときだけ、何が守れなくなるかを説明してルール単位で緩める。hook を変えたら回帰テストを更新して実行する
- 既存の `settings.json` は上書きせずマージする（`enabledPlugins` 等を消さない）
- `security-guidance` と `commit-commands` は常に有効にする。GitHub でチーム開発なら `github` と `pr-review-toolkit` も。その他は検出結果から判断する
- GitHub を使うなら CI・Dependabot・ブランチ保護（`references/ci-workflow-examples.md`）
- `.gitignore` は Step 1 の「無いもの」を、既存の記述を消さずに末尾へ足す
- `git config core.hooksPath .githooks` でコミット前の検査（秘密情報・不可視文字）を有効にするかを聞き、了承を得てから実行する

## Step 4: 雛形を作る

Step 2 で決めたものだけ。中身が空の雛形は使われないので、聞き取った手順と判断基準を書き込む。決まった手順の部分はスクリプトにする。レビュー担当（`impl-reviewer` / `impl-reviewer-recheck`）は同梱済みなので作らない。スキルを足したら `.claude/skills/README.md` に1行足し、`python3 scripts/sync_agent_adapters.py` を実行する。

**デプロイ・DBマイグレーション**の雛形には必ず入れる: 冒頭でテストを実行し失敗なら中止 / 前のバージョンに戻す方法（ユーザーから聞き出して明記）/ マイグレーションは実行前に影響を平易に説明して承認を得る・down migration かバックアップを確かめてから。

`docs/work-items/`（作業1件ごとの正本。記録も兼ねる）と `docs/decisions/`（設計の決定＝ADR）の置き場所を伝える。

## Step 5: CLAUDE.md を埋める

「プロジェクト固有の情報」の3欄を埋める。既に具体的な記述があれば上書きしない。CLAUDE.md は**ルーティング層**なので、説明・例・理由は書かず `docs/` に置いて Docs の表に1行足す（80行以内）。

- **ビルド / 実行 / テスト**: Step 1・2 のコマンド。**dev サーバのポートの変え方も書く**（parallel-worktree が読む）
- **アーキテクチャ / レイヤー構成**: コードがまだ無ければ分かる範囲だけ。層があるなら**各層に置かないもの**まで確かめる（書かないと境界は溶ける）
- **固有の約束事**: 命名・コミット規約・配色（`ui-guidelines` の初期パレットより優先）。ここに書いた約束はレビュー観点になる

書き終えたら `python3 scripts/context_cost.py --ref HEAD` で常時ロードの増え方を確かめる。

## Step 6: 変更点を伝える

作成・変更したファイルと狙い、特に何を許可したかを明示する。「何を防げるようになったか」「何は防げないか」（ツールごとの強制力の差を含む。`docs/agent-rules-rationale.md`）を平易に伝え、無い安全網（lint/test が未検出等）は隠さない。運用スキルの紹介:「壊れたら『壊れたので戻したい』」（safe-rollback）・「公開したくなったら『公開したい』」（go-live-checklist）・「計画を立てて」（task-intake）・「レビューして」（implementation-review）・「記録して」（work-log）。

## Step 7: 扱わなかった範囲を伝える

該当するものだけを名指しで:

- UI があるなら、`ui-guidelines` の初期パレットはテンプレートの色。ブランドカラーがあれば同スキルの手順で差し替える
- night-run を使うなら、`night-run/README.md` のカスタマイズ欄（Dockerfile・init-firewall.sh・entrypoint.sh・`build_prompt`・run.sh・night-run-hearing のタイムゾーン）を**動かす前に**埋める（失敗するのが夜中のため）

使わない機能は触らなくてよい。一覧は README の「派生プロジェクトで埋めるもの」、埋め忘れは project-health-check が棚卸しする。
