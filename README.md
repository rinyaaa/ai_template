# ai_template

AIを活用したアプリケーション開発用のテンプレートリポジトリ。現時点ではプロジェクトの中身は空で、これから実装を追加していく段階。

## セットアップ

**既存のプロジェクトに入れる場合** — Claude Codeに「**セットアップして**」と伝える。`claude-project-setup` スキルがコードを見てビルド/実行/テストコマンドを検出し、[CLAUDE.md](./CLAUDE.md) の「プロジェクト固有の情報」の空欄を埋め、`.claude/` 環境（権限・hooks・プラグイン設定）と、GitHubを使うならCI・Dependabot・ブランチ保護を整える。

**新規（まだコードが無い）場合** — 先に一度動くところまで作る。**空の状態で無理に埋めない**——検出できるものが何も無いので、埋めても推測が並ぶだけになる。コマンドと構成が決まってから「セットアップして」と伝えれば、その時点の実態で埋まる。

どちらの場合も、空欄が残っているうちは、Claude Codeがコマンドを推測せずに聞いてくる。埋まっていない状態でも作業自体は進むが、プロジェクト固有の約束事は効かない。

- セットアップ後にコマンドや構成が変わったら、`CLAUDE.md` を同じコミットで更新する。
- **クローンごとに1回**: `git config core.hooksPath .githooks`（どのAIツール・人の手のコミットにも効く pre-commit 検査を有効にする）。
- **Codex も使う場合**: `.codex/hooks.json` を読ませるため、Codex 側で hook 機能を有効にする。Cursor は `.cursor/hooks.json` をそのまま読む。どちらも導入時に一度「`git push --force` して」と頼み、止まることを確かめる。

### 派生プロジェクトで埋めるもの

`claude-project-setup` が扱うのは最初の1行だけ。残りは**使う機能の分だけ**手で埋める（使わない機能は触らなくてよい）。

| 場所 | 何を | 埋めないとどうなるか |
| --- | --- | --- |
| `CLAUDE.md` の「プロジェクト固有の情報」 | コマンド・アーキテクチャ・レイヤー構成・約束事 | 質が落ちる（Claude Codeが推測せず聞いてくる） |
| `.claude/skills/ui-guidelines/SKILL.md` の初期パレット | ブランドカラー（UIがある場合） | テンプレート付属の色がそのまま使われる |
| `night-run/docker/Dockerfile` | 言語・フレームワークのツールチェーン | 夜間実行がビルドで落ちる |
| `night-run/docker/init-firewall.sh` | 使うパッケージレジストリの配信元 | 依存の取得がブロックされる |
| `night-run/docker/entrypoint.sh` | 既定値（テンプレートには無い） | コンテナが起動しない |
| `night-run/night_runner.py` の `build_prompt` | テスト・静的解析コマンド | 誤ったコマンドが実行される |
| `night-run/run.sh` | 既定のリポジトリ | 実行のたびに指定が必要 |
| `night-run/plan_night.py` のタイムゾーン（または環境変数 `NIGHT_RUN_TZ`） | プロジェクトのタイムゾーン | 締切がJST固定のまま |

`entrypoint.sh` と `run.sh` は同じ変数（`NIGHT_RUN_REPO_URL`）の話で、`run.sh` 側に既定値を書けば `entrypoint.sh` は触らなくてよい。

night-run（夜間の自律実行）を使わないなら、下6つは無視してよい。使う場合は [night-run/README.md](night-run/README.md) のカスタマイズ欄に手順がある。**失敗するのが夜中なので、動かす前に埋めること。**

埋め忘れは「健康診断して」（`project-health-check`）で棚卸しできる。
- セットアップ前の状態でも、`.claude/settings.json` に危険な操作（`rm -rf`, force push, `git reset --hard` 等）と秘密情報の読み取りをブロックする `permissions.deny` ベースラインが入っている。影響を理解した上でなら、ワークフローに合わせて個別ルールを緩和してよい（hookを変えたら回帰テストも更新する）。
- アプリやコードが壊れたときは、Claude Codeに「壊れたので戻したい」と伝えれば `safe-rollback` スキルが安全な手順で復旧する。
- アプリを公開・リリースする前は、Claude Codeに「公開したい」と伝えれば `go-live-checklist` スキルがリリース前監査を行う。
- Claude Code向けの開発ガイドラインは [CLAUDE.md](./CLAUDE.md) を参照。プロジェクトの中身が固まったら、ビルド/実行/テストコマンド・アーキテクチャ概要・レイヤー構成をそちらに追記する。

## 作業の進め方

タスク受け取り → 計画 → 実装 → レビュー → 完了記録、という流れをスキルとして組み込んである。ルールの中核（スコープ厳守・ループ上限5回・自分の実装を自分で承認しない）は [AGENTS.md](./AGENTS.md) の「作業の進め方」にあり、詳細な手順は各スキルにある。

| 言うこと | 起きること |
| --- | --- |
| 「計画を立てて」「issueを起票して」 | `task-intake` がスコープ・受け入れ条件を一緒に固め、Work Item（`docs/work-items/`）にする。必要なら GitHub Issue も作る |
| 「次なにやる？」 | `work_items.py --next` が、進行中の続きか、依存が片付いた ready の先頭を出す |
| 「レビューして」 | `implementation-review` が Work Item・依頼の原文・ADR と差分を突き合わせ、観点ごとに満たす/満たさないを判定する。承認済みADRとの食い違いは見送れない |
| 「記録して」「完了」 | `work-log` が Work Item に結果と詰まった点を書いて完了にし、**効く知見を1行に削って `CLAUDE.md`・スキルへ昇格させる** |
| 「並列で進めて」 | `parallel-worktree` が機能ごとにworktreeを分ける（**既定は直列**。明示的に頼んだときだけ） |

**手順そのものは常時読み込まれない。** 常時読み込むのは中核だけにして、詳細は必要になったスキルだけが読む構成にしてある。理由は分量ではなく**希釈**——ルールを `CLAUDE.md` に全部書くと、本当に守るべきものが些末なものに埋もれる。スキルを追加するときも同じ原則で、`description` はトリガー条件だけに絞る（理由は発動精度。[.claude/skills/README.md](.claude/skills/README.md) 参照）。

**やり取りのコストを下げたい場合、効くのは文書量より「AIに何回・どれだけ読ませるか」。** 消費の大半は、同じ `git`/`gh` の出力を毎回読むこと、diff をサブエージェントへのプロンプトに書き写すこと、サブエージェントを広い範囲で起動することで決まる。そこで:

- **毎回同じになる手順は `scripts/` のスクリプトにしてある**（一覧は [scripts/README.md](scripts/README.md)）。AIは数行の要約だけを読む
- **レビュー材料はファイルに束ねてパスだけを渡す**（`review_bundle.py`）。変更規模でレビューの深さを段階化し、再レビューは初回以降の修正分だけ
- **常時読み込まれる分は `python3 scripts/context_cost.py --ref main` で測ってから変える**

あわせて、1タスク1セッションに分ける、`/context` で何が読み込まれているか確認する、といった運用も効く。

## 安全網の範囲と限界

このテンプレートの安全網は多層構成になっているが、**事故の確率を下げる仕組みであって、安全を保証する仕組みではない**。何が守られていて何が守られていないかを理解した上で使うこと。

**守られていること**

- 破壊的なコマンドや、`.env`・秘密鍵などの秘密情報を直接読むコマンド（`cat`・`cp` 等）は、実行前にブロックされる（`permissions.deny` ＋ フラグ後置・ラッパー経由（`bash -c` 等）の変種もトークン解析で検出する `.claude/hooks/deny_dangerous_bash.py`）。ただしglob（`cat .e*`）やプログラム経由（`python3 -c "open('.env')"`）の読み取りまでは追いきれない（下記「守られていないこと」参照）
- 書いたコードは保存・コミットのたびに危険なパターンのチェックを受ける（`security-guidance` プラグイン）
- セットアップ後は、lint/testの強制やCI・ブランチ保護により、壊れたコードが取り込まれにくくなる（`claude-project-setup` で構築）
- 壊れたとき・公開するときは、専用スキル（`safe-rollback` / `go-live-checklist`）が安全な手順に誘導する
- 安全網のファイルを変えたままAIが作業を終えようとすると、終了時hookが整合性検査を走らせ、失敗なら1回差し戻す（`.claude/hooks/stop_verify.py`。Codex・Cursor も同じ）
- コミット前に、コミットする中身の秘密情報（APIキー・秘密鍵・`.env`）を検査して止める（`.githooks/pre-commit` → `golive_scan.py --staged`。値は表示しない）。AIが `--no-verify`・`git commit -n`・`-c core.hooksPath=...` でこの検査を飛ばそうとすると hook が止める
- AIが読むファイル（ルール・スキル・取り込むスキル）に紛れた不可視文字・双方向制御文字・指示の乗っ取りの文言を検出する（`scripts/scan_agent_content.py`。pre-commit・CI・取り込み時に走る）

**守られていないこと**

- **チェックはすべて確率的。** LLMによるレビューには見逃しがあり、テストはテストが書かれた範囲しか検査しない。「チェックが通った＝安全」ではない。
- **コマンド検査はブロックリスト方式で、原理的に完全ではない。** シェル経由・ラッパー・`cat`/`cp` での直接読み取りといった代表的な迂回は塞いであるが、シェルの全表現を列挙することはできない。例えばglob展開（`cat .e*`）、プログラム経由の読み取り（`python3 -c "open('.env')"`）、列挙外のコマンド（`setsid` 等）はすり抜けうる。hookは第一関門であり、最後の砦はCI・レビュー・ブランチ保護の層。またhookの動作には `python3` が必要で、入力を解釈できない場合は安全側に倒さず通す（フェイルオープン）設計になっている。
- **ドメイン固有の判断はできない。** 認証・認可の設計がそのサービスにとって妥当か、個人情報の扱いが法規制に適合しているかは、汎用チェックでは保証できない。
- **リポジトリの外は守れない。** GitHubやクラウドのアカウント自体の防御（2FA等）、APIキーの発行・保管、クラウド側のインフラ設定は管轄外。
- **運用は自動化されない。** Dependabotの更新PRやCIの失敗は、誰かが気にかけて初めて意味を持つ。週1回「健康診断して」と依頼すれば `project-health-check` スキルが棚卸しを代行するが、その依頼をする習慣自体は人間側の仕事として残る。

**使うAIツールによる強制力の違い**

hook はそのツールの中でしか効かない。同じ hook スクリプトを Claude Code・Codex・Cursor の3つに設定してあるが、強制力には差がある。

| 層 | Claude Code | Codex | Cursor | その他のツール |
| --- | --- | --- | --- | --- |
| 破壊的コマンドのブロック | 強制（deny + hook） | 強制（hook。**Codex 側で hook 機能の有効化が必要**） | 強制（hook） | 指示のみ |
| 秘密情報の読み取りのブロック | 強制（deny + hook） | シェル経由だけ強制 | 強制（読み取り hook + シェル） | 指示のみ |
| コミット前の検査の回避（`--no-verify` 等） | 強制（hook） | 強制（hook） | 強制（hook） | 指示のみ |
| 秘密情報のコミット | プラグイン + pre-commit | pre-commit | pre-commit | pre-commit |
| 安全網を変えたまま終える | 終了時 hook | 終了時 hook | 終了時 hook | pre-commit |
| コード保存・コミット時のセキュリティレビュー | 強制（プラグイン） | 無し | 無し | 無し |
| 復旧・公開監査・健康診断の手順 | スキルとして自動発動 | スキル（`.agents/skills/` の入口から正本へ） | ルール（`.cursor/rules/`）から正本へ | AGENTS.md 経由 |
| pre-commit（`.githooks/`）・CI・Dependabot・ブランチ保護 | 強制 | 強制 | 強制 | **強制**（ツールに依存しない層） |

Codex・Cursor の hook の仕様はツールのバージョンで変わりうるので、導入時に一度止まることを確かめる。ツールに依存せず効くのは pre-commit（`git config core.hooksPath .githooks` が必要。誰でも外せる）と GitHub 側（CI・ブランチ保護）だけ。他ツールを併用するなら CI とブランチ保護を必ず設定すること。詳しくは [docs/agent-rules-rationale.md](docs/agent-rules-rationale.md)。

個人情報・決済・健康情報などを扱うアプリを一般公開する場合は、この安全網に加えて**公開前に人間の専門家によるレビューを受けること**を強く推奨する。

## 構成

ドキュメントは **正本**（仕様・ルールの根拠になるもの）／**説明**（読み手向けの解説。根拠には使わない）／**記録**（起きたことの記録。仕様ではない）の3つに分かれている。**全部を読む必要はない**ので、各行の後半にある参照タイミングで判断すること。ドキュメントを追加・削除・移動したら、同じコミットでこの索引も更新する（索引と実体がずれた索引は、無い索引より悪い）。

**正本**

- `AGENTS.md` は全AIエージェント共通の指示と安全ルールの正本です。ルールを変えるときはこのファイルだけを編集し、CLAUDE.mdへ重複して書かないでください。
- `CLAUDE.md` はClaude Code固有の事項と、プロジェクト固有情報（ビルド/実行/テストコマンド・アーキテクチャ概要・レイヤー構成・固有の約束事）の正本です。実装を始める前に空欄を埋め、コマンドや構成が変わったら同じコミットで更新してください。
- `.claude/skills/` は各作業手順（計画・レビュー・復旧・公開監査・健康診断など）の正本です。常時読み込まれないので、該当する場面になったスキルだけを読みます。どれがあるかは `.claude/skills/README.md` から辿ってください。
- `.claude/agents/` は、スキルから起動される専用サブエージェント（レビュー担当）の定義の正本です。使えるツールを読み取り系に絞っているので、レビュー担当の権限や判定の原則を変えたいときだけ触ります。手順そのものは `.claude/skills/implementation-review/SKILL.md` にあります。
- `.claude/settings.json` と `.claude/hooks/` は、強制ブロック（`permissions.deny` ＋ PreToolUse / Stop hook）の正本です。hook スクリプトは `.codex/hooks.json`・`.cursor/hooks.json` からも呼ばれます。緩和を検討するときだけ触り、変更したら `python3 .claude/hooks/test_deny_dangerous_bash.py` と `python3 scripts/verify_safety_net.py` を実行してください。
- `config/agent-security-allowlist.json` は、`scan_agent_content.py` の検出のうち意図的なものの登録先の正本です。ファイル・ルール・理由を必ず書きます。
- `docs/work-items/` は作業1件ごとの正本です（依頼の原文・受け入れ条件・決めたこと・結果・詰まった点）。作業記録も兼ねます。該当する1件だけを読み、次の作業は `work_items.py --next` で選びます（[README](docs/work-items/README.md)）。
- `docs/decisions/` は設計の決定（ADR）の正本です。承認済みのものは書き換えず、変えるときは新しいADRで置き換えます。構成・ツール・ワークフローを変えるときに読みます（[README](docs/decisions/README.md)）。
- `docs/night-run-design.md` は夜間自律タスク実行の設計の正本です。night-runの制約や設計判断の根拠を確認するときだけ読み、日常運用の手順としては使いません。
- `.github/` はテンプレート自身のCI（`verify-template` が安全網の整合性を毎push検査）とDependabot設定の正本です。CIの挙動やaction固定（コミットSHA）を変えるときに参照します。

**説明**

- `README.md`（このファイル）はテンプレートの概要・安全網の範囲・ドキュメント索引の説明です。安全ルールや内部設計の根拠には使いません（根拠は `AGENTS.md`）。
- `night-run/README.md` は夜間自律タスク実行の使い方・初回セットアップ・派生プロジェクトでのカスタマイズ手順の説明です。夜間実行を実際に動かすときに読みます。設計判断の根拠には使いません（`docs/night-run-design.md`）。
- `docs/agent-rules-rationale.md` はAIの作業ルールの理由と、ツールごとの強制力の説明です。安全ルール・hook・スキルの構成を変えるときに読みます。普段の作業では読みません。
- `.claude/skills/README.md` はスキル一覧とスキル追加時の書き方の説明です。どのスキルがあるかを探す入口として使い、手順の中身は各 `SKILL.md` を見てください。

**ドキュメント以外**

- `night-run/` は夜間自律実行の実装（Dockerfile・runner・テスト）です。派生プロジェクトで使う前に `night-run/README.md` のカスタマイズ欄を埋めてください。
- `scripts/` は、AIが毎回同じ手順を手で繰り返す代わりに使うスクリプト群です（安全網の整合性検査 `verify_safety_net.py` を含む）。一覧と使う場面は [scripts/README.md](scripts/README.md)。テストは `python3 -m unittest discover -s scripts/tests`。
- `.agents/skills/` と `.cursor/rules/agents.mdc` は `scripts/sync_agent_adapters.py` が生成する Codex・Cursor 向けの入口です。直接編集せず、正本（`.claude/skills/`）を直して生成し直してください。
- `.codex/hooks.json`・`.cursor/hooks.json` は Codex・Cursor の hook 設定、`.githooks/pre-commit` はツールに依存しないコミット前検査です。

なお `.github/` にgitleaksによるシークレットスキャンを入れていないのは、テンプレート自身の内容（Markdown・スキル定義中心）にはリスクが薄く保守コストが見合わないため。実装が始まる派生プロジェクトには価値が高いので、`claude-project-setup` スキルがCI雛形として案内する。

## ライセンス

[MIT](./LICENSE)
