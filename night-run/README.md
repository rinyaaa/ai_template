# night-run — 夜間自律タスク実行システム

`docs/night-run-design.md` に基づく実装。GitHub Issueのタスクを、人が寝ている間に実装〜PR作成まで自律的に進める。設計上の背景・未確定事項の解消方針は設計書と `AGENTS.md`/`CLAUDE.md` の安全ルールを参照。

タスクの起点はNotionではなくGitHub Issue（`.claude/skills/github-task-intake/`で起票）にしている。エンジニアのみで運用する前提なら、Notionの非対話認証（サーバー間トークン）を別途用意する手間がなく、`gh`のトークンをそのまま使い回せるため。

**このシステムは実在するリポジトリへ実際にPRを作成する。初回は必ずドライラン（下記）を通してから本番投入すること。**

## このテンプレートを使う前に(派生プロジェクトでのカスタマイズ)

night-runは元々Flutterプロジェクト向けに実装されたものを、このテンプレート用に汎用化している。派生プロジェクトで使う前に、以下を自分のプロジェクトに合わせて埋めること。

- `night-run/docker/Dockerfile`: `TODO`コメントの箇所に、自分のプロジェクトの言語・フレームワークのツールチェーンをインストールする処理を追加する
- `night-run/docker/init-firewall.sh`: `FIXED_DOMAINS`に、追加したツールチェーンが使うパッケージレジストリ等の配信元を追加する(無いと`flutter pub get`/`npm install`等の相当処理がネットワーク遮断で失敗する)
- `night-run/night_runner.py` の `build_prompt`: テスト・静的解析コマンドの例示部分を自分のプロジェクトのコマンドに合わせて調整する(CLAUDE.mdにコマンドが書いてあれば、そちらを参照させる指示のままでも動く)
- `night-run/run.sh` を起動する際、`NIGHT_RUN_REPO_URL`環境変数に自分のリポジトリのURLを指定する(下記セットアップ手順を参照)

## 使い方（日常運用）

night-runは3つのSkillと1つのスクリプトの組み合わせ。**コマンドを覚える必要はなく、日本語で自然に頼めば発動する。**

| 場面 | 使うもの |
|---|---|
| 直したい/作りたいことを思いついたとき | 「issueを起票して」→ `github-task-intake` Skillが観点を確認しながらissue化する |
| その日確定したissueをまとめて夜間に回したいとき | 「夜間実行して、6時まで」→ `night-run-hearing` Skillが対象issue・締切を確認 → `night-run/run.sh start`で起動 |
| 実行中/翌朝に様子を見たいとき | 「night-runどうなってる」→ `night-run-status` Skillが完了/失敗/draft PRを棚卸しして報告 |

1サイクルの例:

1. 「issueを起票して。○○の不具合を直したい」 → 関係する観点(Engineer/PM/PO/Designer等)を確認しながらissueが作られる
2. issueが十分たまったら「夜間実行して、6時まで」 → 対象issueと締切を確認 → 承認すると`night-run/run.sh start`で起動(コンテナはターミナルを閉じても動き続ける)
3. 翌朝「night-runどうなってる」 → 各issueの結果(done/failed)とPR URLが出る。**draft PRは必ず人間がレビューしてからマージする**(自動マージはしない設計)

## 初回セットアップ（メンバーごとに1回）

night-runは**メンバーごとに個別の認証情報**を使う(誰が実行したかがgit/GitHub側の記録に残る)。以下をそれぞれ自分のマシンで行う。

### 1. `gh` CLIのインストール・認証

```sh
brew install gh
gh auth login
```

これでヒアリング・起票Skill(ホスト側で動く部分)が使えるようになる。

### 2. Dockerイメージのビルド（初回、以後は`night-run/`が更新されたら都度）

```sh
night-run/run.sh build
```

### 3. 夜間実行(コンテナ内の`claude -p`)用の認証トークンを用意する

**方式A: サブスクリプションのトークンを使う(追加課金なし。個人のPro/Max等がある場合)**

```sh
claude setup-token
```

ブラウザでの認証後、長期トークンが表示される。これを`CLAUDE_CODE_OAUTH_TOKEN`として使う。**レート制限は人間の対話利用ペース想定なので、1晩に複数タスクを回すと途中で制限に達しやすい**(致命的ではない。backoffで数回リトライした上でそのタスクは`failed`として安全に終わる)。

**方式B: APIキーを使う（[Anthropic Console](https://console.anthropic.com/)で発行、従量課金）**

`ANTHROPIC_API_KEY`として使う。方式A/Bはどちらか一方でよい。

### 4. 秘密情報ファイルを作る(プロジェクトの外・git管理外)

```sh
cat > ~/.night-run-secrets.env <<'EOF'
export CLAUDE_CODE_OAUTH_TOKEN="上で発行した値"   # または export ANTHROPIC_API_KEY="..."
export GH_TOKEN="$(gh auth token)"
export NIGHT_RUN_REPO_URL="https://github.com/<org>/<repo>.git"   # 自分のリポジトリのURLに置き換える
EOF
chmod 600 ~/.night-run-secrets.env
```

`GH_TOKEN`は`gh auth login`済みのトークンをそのまま流用している(`repo`スコープがあればOK。専用の絞ったPATを別途発行してもよい)。

以後、night-runを使うときは毎回このファイルを`source`する:

```sh
source ~/.night-run-secrets.env && night-run/run.sh start
```

### 5. 一度、night-run一式を `main` にマージする

`night_runner.py` はタスクの合間に `git reset --hard origin/main` する（`git_cleanup()`）。**このリポジトリ自身がその対象なので、`night-run/` 一式が `main` に入っていないと、次のタスクへ進む際に消えてしまう。** 初回は普通のPRフローでこのディレクトリ一式を `main` にマージしてから使うこと。

## ドライラン（`night-run/`本体に手を入れたら再実施）

本番の締切・タスクで初めて使う前、および`night-run/`配下のスクリプト自体を変更したときは、以下の手順で必ず確認すること。設計書9.6節。

1. ヒアリングSkillを実行する際、「何時まで」の質問に対して**現在時刻から5〜10分後**を答える
2. タスクは1件、既存コードの小さな修正など軽量なものにする
3. `night-run/run.sh start` → `night-run/run.sh logs` で経過を見る
4. 確認すること:
   - `init-firewall.sh` の自己検証（`example.com`拒否/`api.github.com`許可）が通ること
   - ソフトカットオフ（新規タスク非着手）とハードリミット（強制終了）が期待通りのタイミングで効くこと
   - 締切超過時に診断用ブランチが作られ、`night-run-state.json`の該当タスクが`failed`になり、draft PRの本文にTODOプレースホルダーではなく実際の進捗が入っていること
   - 正常完走した場合、`gh pr view`での実在確認（9.8節）を経て`done`になっていること
5. 問題があれば該当箇所を直し、もう一度ドライランする。**通るまで本番の締切・タスクでは実行しない**

## コマンド早見表

```sh
source ~/.night-run-secrets.env && night-run/run.sh start   # 起動
night-run/run.sh logs                                       # ログを追う(閉じてもコンテナは動き続ける)
cat night-run/state/night-run-state.json                    # 途中経過(ホストから直接読める)
tail -f night-run/state/alerts.log                          # 異常があればここに出る
```

止めたいときは `night-run/run.sh stop`。**進行中のタスクは中断され、`done`にならない**（次に`run.sh start`し直すとstateの`pending`/`in_progress`から再開を試みるが、`in_progress`のまま止まったタスクは`main()`が拾わないので、手動で`status`を`pending`に戻すか診断ブランチの内容を確認してから判断すること — 常駐化・自動復旧は今回のスコープ外）。

## スコープ外（今回は実装していない）

- esa用MCPサーバー（設計書7章、任意扱い）
- `night_runner.py`自体の常駐化・クラッシュ時の自動再起動（設計書9.1節）。`run.sh start`はターミナルを閉じても動き続けるが、コンテナやホストが落ちた場合の自動復旧はない
- Slack Webhook等への実際の通知送信（`notify_human()`に拡張ポイントだけ用意。今は `alerts.log` への追記のみ）

## トラブルシュート

- **依存パッケージの取得が失敗する**: 新しいパッケージを追加するタスクで、そのパッケージの配信元CDNのIPが`init-firewall.sh`の許可リストにない可能性がある。パッケージレジストリのIPは起動時に一度だけ解決しており、実行中にIPが変わると通信がブロックされうる（この方式の既知の制約）。`night-run/run.sh stop && night-run/run.sh rm && night-run/run.sh start`でコンテナを作り直す（`init-firewall.sh`が再実行されIPを再解決する）
- **`gh pr create`/`gh issue view`が権限エラーで失敗する**: `GH_TOKEN`のスコープ（`repo`。issueの読み書きも含まれる）と対象リポジトリへの権限を確認する
- **コンテナがすぐ落ちる**: `night-run/run.sh logs`で`[init-firewall]`のFATALログを確認する。ネットワーク許可リストの設定ミスであることが多い
