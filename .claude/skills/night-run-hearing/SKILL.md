---
name: night-run-hearing
description: 夜間に人の確認なしでタスクを実装〜PR作成まで自律実行させたいときのヒアリング。「夜間実行して」「夜間タスクをお願い」「寝てる間に実装しておいて」「朝までにこれ終わらせておいて」「オーバーナイトで進めて」といった依頼で発動する。Claude night-run(完全無人)向けのnight-run-state.jsonと、Antigravity `/goal`(人が近くにいる想定、コピペで渡す)向けの実行プロンプトの、どちらか一方を生成するところまでで、実際の自律実行はここでは行わない。
---

# night-run ヒアリング

night-run システム（`night-run/README.md`、設計書 `docs/night-run-design.md`）の対話フェーズ。目的は「何時まで・何を・どちらの実行エンジンで」を確定させ、実行エンジンに応じた成果物（Claude night-runなら`night-run/state/night-run-state.json`、Antigravityなら`/goal`に貼り付けるプロンプト文）を作ることだけ。**実際の実装・PR作成はこのSkillの範囲外**。この境界を崩さない——ここで実装作業に踏み込まない。

Step 1〜5（締切・issue・依存関係・要約・最終確認）はどちらのエンジンでも共通。Step 6以降だけエンジンによって分岐する。

このSkill中の選択肢が2〜4個に絞れる質問（Step 0の実行エンジン選択、Step 3の依存解消方法、Step 5の最終確認など）は、自由文入力を求めずに `AskUserQuestion` ツールでクリック選択できる形で聞く。

## Step 0: 実行エンジンを確認する

`AskUserQuestion` で「Claude night-run」と「Antigravity `/goal`」のどちらで実行するか選んでもらう。それぞれの性質の違いを一言で添える。**最初の依頼文で既にどちらか指定されていれば（例:「Antigravityで夜間実行して」）、ここで聞き直さず、指定された方を復唱して確認するだけにする。**

- **Claude night-run**: Dockerサンドボックス内で完全無人実行。予算上限・PR実在検証・締切超過時の退避ブランチなど、`night_runner.py`側のハードニングあり。画面を閉じても、人が離れても動く。
- **Antigravity `/goal`**: 対話セッション内で実行。認証がコンテナ間で持続しない既知の制約があり、現時点では**完全無人・長時間放置での動作は未検証**。人がある程度近くにいる／後で様子を見に戻れる前提での利用を想定する。

選んだ結果で、この後のStep 6以降が分岐する。

## Step 1: 締切時刻を確認する

「何時まで作業してよいか」を聞く（「6時まで」のように時刻だけ言われる想定）。現在時刻から見て一番近い未来の該当時刻に変換する。手計算せず、Bashで確認する。

```sh
python3 - <<'EOF'
import datetime
from zoneinfo import ZoneInfo

jst = ZoneInfo("Asia/Tokyo")  # TODO: プロジェクトのタイムゾーンに合わせて変更する
now = datetime.datetime.now(jst)
hour = 6  # ユーザーが言った時刻に置き換える
candidate = now.replace(hour=hour, minute=0, second=0, microsecond=0)
if candidate <= now:
    candidate += datetime.timedelta(days=1)
print(candidate.isoformat())
EOF
```

変換結果を「〇月〇日 6:00までですね」と復唱して確認する。

続けて「締切を過ぎてから完走まで待つ猶予（バッファ）」を確認する。特に指定がなければ90分をデフォルトとして提案する。締切+バッファを `hard_limit` として、こちらも絶対時刻で確定させる。

- **Claude night-run**: `hard_limit` は`night_runner.py`が実行時刻と突き合わせて強制終了に使う値。このシステムは実行中に都度計算し直さない。ここで確定した値をそのまま書き出す。
- **Antigravity**: `/goal`自体が独自に締切を聞いてくることがある（Step 6bで生成するプロンプト内に目安として埋め込むだけで、機械的な強制はされない）。

## Step 2: タスクのissueを確認する

やってほしいタスクのGitHub issue番号またはURL（複数可）を聞く。タイトルしか分からない場合は `gh issue list --search "<キーワード>"` で探す。それぞれ `gh issue view <番号>` で実在確認し、内容(タイトル・本文)を読む。見つからないものはその場でユーザーに確認する（番号違い・未起票など。`github-task-intake` Skillで先に起票することを案内してもよい）。**ここで実在確認できなかったタスクは、実行フェーズには絶対に持ち越さない。**

## Step 3: タスク間の依存関係を確認する

「このタスクの変更が前提になる、他のタスクはありますか？」と確認する。依存ありと申告されたら、`AskUserQuestion` で以下のどちらかをその場で選んでもらい解消する（設計書7.2節）。**実行フェーズのタスクリストに未解決の依存を残さない。**

- **同じ夜にまとめて1ブランチで進める**: 依存する複数タスクを1つの実装単位（state上は1エントリ、PRも1つ）として扱う
- **別の夜に回す**: 依存先のタスクは今夜のリストに含めない（stateに書き出さない）

## Step 4: 内容を要約提示する

各タスクについて、issueの内容を要約してユーザーに提示する。

## Step 5: 実行確認

すべてを踏まえて `AskUserQuestion` で「この内容で実行してよいか」を最終確認する（選択肢: 実行する / 修正したい、など）。実行しない場合は該当ステップに戻ってやり直す。**「実行する」が選ばれるまでstateファイルは書き出さない。**

## Step 6: 成果物を作る

`branch` はどちらのエンジンでも共通のルールでこの時点で確定させる。`night-run/<ヒアリング当日の日付YYYY-MM-DD>/task-<連番>` とする（issueタイトルをそのままブランチ名にしない。ASCIIで一意にするため。日付を入れるのは、Dockerの作業ボリュームは夜をまたいで使い回す想定なので、`task-1`のような連番だけだと前回の夜のブランチ名と衝突しうるため）。

Step 0で選んだエンジンに応じて、以下のどちらかを行う。

### Step 6a: Claude night-run — state ファイルを書き出す

`night-run/state/night-run-state.json` を以下のスキーマで書き出す（`night-run/state/` ディレクトリが無ければ作成する）。

```json
{
  "deadline": "2026-08-30T06:00:00+09:00",
  "hard_limit": "2026-08-30T07:30:00+09:00",
  "hard_limit_buffer_minutes": 90,
  "tasks": [
    { "title": "タスクA", "issue_url": "https://github.com/<org>/<repo>/issues/12", "status": "pending", "branch": "night-run/2026-08-29/task-1" },
    { "title": "タスクB + タスクC(依存によりまとめて実施)", "issue_url": "https://github.com/<org>/<repo>/issues/13", "status": "pending", "branch": "night-run/2026-08-29/task-2" }
  ]
}
```

- `issue_url` はStep 2で実在確認した実際のissue URLを入れる(タスクプロンプト側がタイトルの曖昧一致ではなく、この番号で直接`gh issue view`できるようにするため)。依存タスクをまとめた場合は、実装の起点となる方のissue URLを入れる
- `status` は全タスク `"pending"` で書き出す
- `depends_on` フィールドは書かない（Step 3で解消済みのため）
- `hard_limit`・`deadline` は必ず絶対時刻(ISO8601)。ランタイム側では計算し直さない

書き出したら、このSkillの役目は終わり。**対話セッションはここで終了する**（実装作業には進まない）。

### Step 6b: Antigravity — `/goal` プロンプトを生成する

依存でまとめたタスクごとに1つ、Antigravityの`/goal`にそのまま貼り付けられるプロンプト文を、以下の形式でチャット上に出力する（コピペしやすいようコードブロックで囲む）。ファイルには書き出さない（`night-run/state/`はClaude night-run専用のディレクトリなので混在させない）。

```
以下の<N>つのissueをまとめて1つのブランチ `<branch>` で実装し、draft PRを作成してください。

## 対象issue

**Issue #<番号>**: <タイトル>
<issue URL>

(複数あれば繰り返し)

## 手順
1. `git checkout -b <branch>` でブランチを切る
2. 各issueの受け入れ条件を満たす実装をする
3. AGENTS.md/CLAUDE.mdに記載の実装規約・コーディング規約に従う
4. テストを追加する
5. CLAUDE.mdに記載のテスト・静的解析コマンドを実行し、失敗があれば直す(グリーンになるまで繰り返す)
6. **ここが一番省略されやすい工程です。飛ばさないこと**: 実装した差分を、実装した本人ではなくレビュアーの視点で読み直してください。バグ・エッジケースの考慮漏れ、AGENTS.md/CLAUDE.mdの規約違反、テストの過不足がないかを確認し、見つかったら直す。指摘事項と対応結果を後述のPR本文に書けるようにメモしておく
7. `git commit` して `git push origin <branch>`
8. `gh pr create --draft` でdraft PRを作成する。本文にStep 6で見つけた指摘事項と対応状況を含める(何もなければ「レビュー観点で確認、指摘なし」と明記する)

目安の締切: <Step 1で確認した締切>（厳密な強制はされないので、超えそうなら一旦区切りのいいところまでで止めてよい）

完走するまで止まらず進めてください。

skillsは '.claude/skills/README.md' を参照してください。
```

- `<N>`・issueの列挙・`<branch>`はStep 2〜3で確定した内容をそのまま使う
- 複数タスク（依存でまとめていないもの）を一度にヒアリングした場合は、タスクごとに別々のプロンプトを生成する（1つの`/goal`呼び出しに複数の無関係なタスクを混ぜない）

出力したら、このSkillの役目は終わり。**対話セッションはここで終了する**（実装作業には進まない）。

## Step 7: 次の手順を案内する

以下を案内して終える。実際に実行を開始するのは、ユーザー自身が明示的に行う一手として残す（このSkillからは起動しない）。

### Step 7a: Claude night-run

- 初回、または `night-run/` を直近で変更した場合は、**`night-run/` 一式が `main` にマージ済みか**を確認するよう伝える（`git_cleanup()` が毎回 `origin/main` に戻すため、マージされていないと次のタスクへ進む際に消える）
- 本番の締切で使うのが初めてなら、まず `night-run/README.md` のドライラン手順を一度通すよう案内する
- 準備ができたら `night-run/run.sh start` で起動すること、`night-run/run.sh logs` で経過を追えること、`night-run/state/night-run-state.json` と `night-run/state/alerts.log` はホストから直接読めることを伝える

### Step 7b: Antigravity

- 生成したプロンプトを、Antigravityの`/goal`（または通常のチャット）にそのまま貼り付けるよう案内する
- 事前確認として、以下ができているかを伝える（できていなければ先に済ませるよう促す）:
  - `.agents/hooks.json` / `.agents/hooks/deny_dangerous_agy.py` が配置済みであること（破壊的コマンドの検出用。効くかどうかは実機で継続検証中）
  - Antigravity側の権限設定（`/permissions` → Project scope）で、ファイル編集・コマンド実行が毎回確認を求めない状態になっていること
- **完全無人・長時間放置での動作は未検証**であることを明確に伝える。人が離れる場合は、定期的に様子を見に戻ることを勧める
