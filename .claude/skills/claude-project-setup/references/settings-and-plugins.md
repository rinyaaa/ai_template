# settings.json・プラグイン・CIの詳細

claude-project-setup の Step 3 で読む。

検出したツールチェーンに応じて、安全に許可してよいコマンドを `permissions.allow` に提案する。例えば Node.js プロジェクトなら `Bash(npm test:*)`, `Bash(npm run lint:*)`, `Bash(npm install:*)` や、読み取り系のgitコマンド（`git status`, `git diff`, `git log` 等）のように、実行しても状態を壊さない・すぐ終わるコマンドを中心に許可する。破壊的な操作（`rm -rf`, `git push --force` など）は決して自動で許可リストに入れない。

このテンプレートの `settings.json` には、スタックを問わず危険な操作（`rm -rf`, `git push --force`, `git reset --hard`, `git clean` 等）と秘密情報の読み取り（`.env`, 秘密鍵, `~/.ssh` 等）をブロックする `permissions.deny` のベースラインが最初から入っている。さらに、permissionルールは前方一致なのでフラグ後置の変種（例: `git push origin main --force`）をすり抜けてしまうことへの対策として、コマンドをトークン解析してフラグの位置に関係なく破壊的操作をブロックする `PreToolUse` hook（`.claude/hooks/deny_dangerous_bash.py`、回帰テスト同梱）も設定済みである（同じスクリプトを `.codex/hooks.json`・`.cursor/hooks.json` からも呼ぶ）。安全網のファイルを変えたまま終えると検査が走る Stop hook（`.claude/hooks/stop_verify.py`）もある。

このベースラインの扱い：

- 編集はマージで行う。プロジェクト固有の危険操作（本番DBへのマイグレーション実行コマンド、破壊的なデプロイコマンド等）が分かったら、denyとhookに**追加する**。
- ベースラインは初期値であって聖域ではない。このブロックは正当なワークフロー（rebase後の `git push --force-with-lease`、実験を捨てる `git reset --hard`、`git clean` 等）とぶつかることがあるので、**ユーザーから明示的な依頼があれば、そのルールを外すと何が守れなくなるかを説明した上で個別に緩和してよい**。典型例: force-with-lease だけ許可したい → hookの `--force` 判定を「`--force-with-lease` は除外」に修正し、denyの `Bash(git push --force:*)` はそのまま残す（with-leaseはprefix不一致なので通る）。緩和はこのように**依頼されたルール単位**で行い、「邪魔だから」と一括で消さない。セットアップの対話で先回りして緩和を提案する必要はない——実際にブロックに当たってから調整すれば十分。

どちらのモードでも、hookの検出パターンを変更した場合は `.claude/hooks/test_deny_dangerous_bash.py` のテストケースを緩和内容に合わせて更新し、`python3 .claude/hooks/test_deny_dangerous_bash.py` で回帰テストを必ず実行する（緩和した挙動も「ブロックされないこと」をテストとして固定する）。

`npm run dev` や `npm start` のようにサーバーを起動して常駐させるコマンドは、壊れはしないが「終了しないプロセスを勝手に立ち上げてよいか」という別種の判断が入るので、機械的に他のコマンドと同列に許可リストへ入れず、必要そうであれば一言確認してから加えるくらいの慎重さでよい。

`hooks` はユーザーから明示的な要望（「コミット前に必ずlintを走らせたい」等）があれば追加し、無ければ触らない。hookは自動化された振る舞いを強制する仕組みなので、要望のないhookを勝手に仕込むとユーザーの意図しない動作を引き起こしかねない。

既存の `settings.json` がある場合は中身を読み、上書きではなくマージする形で編集する。特に `enabledPlugins` のような既存フィールドを消さないよう注意する。

`enabledPlugins` の `"security-guidance@claude-plugins-official"` と `"commit-commands@claude-plugins-official"` は、プロジェクトの性質を問わず常に `true` にする（該当キーが無ければ追加する）。他のプラグインと違って、これらは検出結果やユーザーの体制に応じて要否が変わるものではなく、どんなプロジェクトでも入れておいて損がない基礎的な安全網・作業効率化なので、判断や確認を挟まず毎回有効化してよい。

- **`security-guidance@claude-plugins-official`**: 編集・保存のたびに危険なコード パターン（`yaml.load`, `pickle.load`, 生の `innerHTML`, ハードコードされた秘密情報など）を即座に警告し、ターン終了時にはLLMによる差分レビュー、`git commit`時にはコードベース横断のエージェント的レビューまで行う3層構成のセキュリティチェック。独自のhookを組むより検出範囲が広く保守の手間も無いので、セキュリティレビューはこのプラグインを主軸にする。プロジェクト固有に気をつけたいルールがあれば `.claude/claude-security-guidance.md` に書くとレビューで加味される。
- **`commit-commands@claude-plugins-official`**: `/commit` `/commit-push-pr` `/clean_gone` などのコミット・PR作成・ブランチ整理コマンドを提供する。生のgitコマンドを手打ちする場面を減らせる。

また、GitHubを使ってチーム開発をするかどうかをユーザーに確認する。する場合は、PRベースのレビューが発生する前提になるので、`enabledPlugins` の `"github@claude-plugins-official"` と `"pr-review-toolkit@claude-plugins-official"` を `true` にする（該当キーが無ければ追加する）。個人開発でGitHubを使わない、あるいはPRレビューをClaude Codeに任せる予定が無い場合は、無効のままにしてよい——使わない機能を有効化しても混乱を招くだけなので、必要性を確認してから有効化する。

## GitHubを使う場合: CI・依存メンテナンス・ブランチ保護

hookやセキュリティレビューのプラグインは、すべて「Claude Codeのセッションの中」でしか効かない。設定が同期されていない別環境やGitHub上での直接編集はすり抜けるので、GitHubを使うプロジェクトではリポジトリ側にも検査の層を作る。具体的な雛形と注意点は [references/ci-workflow-examples.md](ci-workflow-examples.md) を読んでから作業すること。やることは3つ：

1. **`.github/workflows/ci.yml` の生成**: Step 1で検出したlint/test/auditコマンドからCIワークフローを作る。検出できていないコマンドを想像で書かない——初回から失敗し続けるCIは無いより悪い。lint/testが何も検出できていない場合でも、スタックに依存しないシークレットスキャン（gitleaks）のジョブだけは入れる（詳細は参照ファイルの「シークレットスキャン」節）。あわせてGitHubのSecret scanning / Push protectionの有効化も案内する。
2. **`.github/dependabot.yml` の生成**: 依存パッケージの脆弱性・更新を自動でPRとして届けさせる。誰もCVE情報を見ない体制でも、更新が「届く」状態にはなる。届いたPRを誰がどう処理するかの運用文をStep 5でCLAUDE.mdに残す。
3. **ブランチ保護の案内**: CIを置いただけでは失敗しても取り込めてしまう。デフォルトブランチへの直push禁止とCI成功のマージ条件化を、GitHub UIの手順（または合意の上で `gh` CLI）で案内する。リポジトリ内のファイルだけでは完結しない設定なので、案内した/しなかった・設定できた/できなかったをStep 6の報告に含める。

この層はローカルの安全網をすり抜けた変更を最後に止める役割を持つ。既にCIが存在するなら重複して作らず、既存のCIにaudit系のジョブが無ければ追加を提案する程度にとどめる。

他にも以下のプラグインは、Step 1の検出結果からプロジェクトの性質がある程度読み取れるので、GitHubのケースと違って毎回ユーザーに確認する必要はなく、判断できるならこちらで決めてよい（迷う場合だけ聞く）：

- **`context7@claude-plugins-official`**: バージョン固有の最新ドキュメントを取得するプラグイン。外部ライブラリ・フレームワークに依存している（`package.json`の`dependencies`, `pyproject.toml`の依存関係等が一定数ある）プロジェクトなら基本的に有効化して問題ない。依存がほぼ無い学習用スクリプトのような場合は無理に有効化しなくてよい。
- **`feature-dev@claude-plugins-official`**: コードベース探索・設計・品質レビューを含む機能開発向けワークフロー。複数ファイル・複数レイヤーにまたがるアプリケーション（Webサービス、API、それなりの規模のCLIツール等）では有効化する価値が高い。単一ファイルのスクリプトのような最小構成のプロジェクトでは、有効化しても使う場面が少ないので見送ってよい。
- **`frontend-design@claude-plugins-official`**: UI/UX実装のためのフロントエンドデザイン支援。検出した技術スタックにフロントエンド要素（React/Vue/Next.js等のUIフレームワーク、`src/components`のようなディレクトリ構成等）が無ければ無効のままにする。バックエンドAPIのみ、CLIツールのみのプロジェクトでは基本的に不要。

これらを有効化した場合も、Step 6で「何を・なぜ有効にしたか」を必ず報告する——ユーザーが把握しないまま静かに増えていくのが一番良くない。

## `.gitignore` の整備

Step 1で検出した技術スタックに応じて、Gitで追跡すべきでないものを `.gitignore` に追記する。空のテンプレートのまま技術スタックが決まっていない場合は無理に埋めず、後述の「技術スタックを問わず追加してよいもの」だけにとどめる。

- 技術スタックを問わず追加してよいもの: `.env` / `.env.*`（秘密情報の誤コミット防止）、`.DS_Store`（macOS）、`.claude/settings.local.json`（個人用のローカル設定であり、コミット対象の `.claude/settings.json` とは役割が違う）
- Node.js系と分かったら: `node_modules/`, ビルド成果物（`dist/`, `.next/`, `build/` など、フレームワークに応じて）
- Python系と分かったら: `__pycache__/`, `*.pyc`, 仮想環境ディレクトリ（`.venv/`, `venv/`）, `*.egg-info/`
- Go/Rust/Ruby等も同様に、そのエコシステムで一般的なビルド成果物・依存キャッシュのディレクトリを追加する

既存の `.gitignore` に同じ内容がある行は重複させず、既存の記述（コメントや独自の除外設定）は消さずに末尾へ追記する形でマージする。何を追加したかはStep 6の報告に含める——ユーザーが把握していない変更を静かに紛れ込ませない。

`python3 scripts/detect_stack.py` の「.gitignore に無いもの」に、足すべき候補が出る。
