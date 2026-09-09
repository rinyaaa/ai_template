# CLAUDE.md

安全ルールを含む全AIエージェント共通の指示は以下からインポートされる。**ルールの本体はAGENTS.md側にあり、変更もそちらで行う**——このファイルにはClaude Code固有の事項だけを書くこと（二重管理による食い違いを防ぐため）。

@AGENTS.md

## プロジェクト固有の情報

AIを活用したアプリケーション開発用のテンプレート。中身は空なので、**このプロジェクトでしか通用しないこと**を以下の欄に書いて埋める（共通ルールはAGENTS.md側にある）。

### ビルド / 実行 / テスト

<!-- ポートの変え方も書く（parallel-worktree がここを読む） -->

- インストール:
- 起動:
- テスト:
- lint / format:

### アーキテクチャ概要

### レイヤー構成（各層に置くもの / **置かないもの**）

<!-- 記入例: router/ には受け取り・検証・レスポンス整形だけ。業務ロジックは useCase/、DBアクセスは
     repository/ に置き、SQLを router / useCase に直接書かない。「置かないもの」を書かないと境界は溶ける。 -->

### 固有の約束事

<!-- 命名・コミット規約など。配色が決まっているなら、ui-guidelines の初期パレットではなくここの表を正とする。
     ここに書いた約束は implementation-review がレビュー観点として拾う。 -->

## Claude Code固有の補足（このセクションはテンプレートを埋めた後も残すこと）

- AGENTS.mdの安全ルール1（破壊的コマンド。`git worktree remove` / `prune` を含む）は、Claude Codeでは `.claude/settings.json` の `permissions.deny` と `.claude/hooks/deny_dangerous_bash.py`（PreToolUse hook）により**強制**される。hookの検出パターンを変更したら `python3 .claude/hooks/test_deny_dangerous_bash.py` で回帰テストを必ず実行する。
- AGENTS.mdの「作業の進め方」が指すスキル（task-intake / implementation-review / work-log）と、ランブック（safe-rollback / go-live-checklist / project-health-check）は、Claude Codeではスキルとして自動発動する。「公開して」と言われても go-live-checklist の監査を通さずにデプロイへ進まない。「壊れた」と言われたら safe-rollback に従い、`git reset --hard` や force push で回復しない。
- テンプレートリポジトリでは `.github/workflows/verify-template.yml` が安全網の整合性（`scripts/verify_safety_net.py`）を毎push検査する。