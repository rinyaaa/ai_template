# 夜間自律タスク実行システム 設計書 (v6)

> **実装時の変更点**: このテンプレートはエンジニアのみで運用する前提のため、タスクの起点をこの文書が前提とする「Notion MCP」から**GitHub Issue**に変更して実装している(`.claude/skills/github-task-intake/`で起票、`.claude/skills/night-run-hearing/`・`night-run/night_runner.py`は`gh issue view`で内容を取得)。これにより10章のNotion非対話認証まわりの課題は発生しない。本文中の「Notion」を読む際はこの変更を踏まえること。議論フェーズ(役割ベースの合意形成)は夜間の自律判定としては採用せず、`.claude/skills/github-task-intake/`内で人間同席の起票時チェックリストとして採用している。

---

## 0. 実装着手前の必須前提条件(ブロッカー)

以下は「残課題」ではなく、**これが確定・実装されるまで他の部分を実装・実行してはならない前提条件**である。第三者レビューにより「後回しにできない核心部分」と指摘された事項をここにまとめる。

### 0.1 サンドボックス実行環境の具体化(旧9.5より格上げ)

- 本設計は`--dangerously-skip-permissions`(3.1節)と、破壊的なgit操作である`git_cleanup()`(4.1節)を前提にしている
- これらの安全性は**「本当に使い捨て・隔離された環境で動いているか」に100%依存する**。この前提が崩れた場合、ホスト環境や他の開発マシンに対して確認なしのコマンド実行・強制的な作業ツリー破棄が走るリスクがある
- したがって、実装着手の最初のステップとして以下を確定させること:
  - コンテナ/VMの具体的な実装(Dockerfile等)
  - ネットワーク許可先の明示的なリスト(Notion API、GitHub、Anthropic API、esa APIなど。それ以外は遮断)
  - コンテナのライフサイクル(タスクごとに使い捨てるか、夜間を通して使い回すか。git操作の一貫性を考えると同一コンテナ・同一作業ディレクトリの使い回しを推奨)
  - **当該環境が「サンドボックスである」ことを外側スクリプトが機械的に確認できる手段**(後述0.2で使用する環境マーカー)

### 0.2 サンドボックス確認ガードの実装

`git_cleanup()`や`--dangerously-skip-permissions`を伴う`claude -p`呼び出しの前に、実行環境が意図したサンドボックスであることを機械的に確認するガードを設ける。例えば以下のような方式のいずれかを採用する:

- 環境変数(例:`NIGHT_RUNNER_SANDBOX=1`)がコンテナ起動時にのみ設定されるようにし、`night_runner.py`起動時にこれが存在しない場合は即座に異常終了する
- あるいは、コンテナ内にのみ存在するマーカーファイル(例:`/.sandbox-marker`)の有無を確認する

```python
import os, sys

def assert_sandbox_or_exit():
    if os.environ.get("NIGHT_RUNNER_SANDBOX") != "1":
        print("致命的エラー: サンドボックス環境が確認できません。実行を中止します。", file=sys.stderr)
        sys.exit(1)
```

`night_runner.py`の`main()`冒頭、および`git_cleanup()`の先頭で必ずこのチェックを行う。

---

## 1. 目的・概要

Claude Codeを用いて、夜間に人が介在しなくてもタスクを自律的に実装し、PR作成まで完了させる仕組みを構築する。

- タスクはNotion MCP経由で取得する
- 実行開始時に会話形式で対象タスク・終了時刻を確認する
- 各タスクは「実装→デバッグ→レビュー→修正→コンフリクト解消→PR作成」のサイクルを回す
- 指定時刻を過ぎたら新規タスクには着手せず、進行中のタスクのみ完走して停止する
- トークン(利用量上限)切れが発生した場合は状態を保存し、復活後に自動で続きから再開する

### 1.1 アーキテクチャ方針(重要)

本システムは **「対話セッション(ヒアリング用)」と「自律実行(外側スクリプト駆動)」を明確に分離する**。

- **ヒアリングフェーズ**:人間とClaudeの対話セッション。ここで締切・タスクリストを確定し、状態ファイルに書き出して終了する
- **実行フェーズ**:Claude自身がループを回すのではなく、**外側のBash/Pythonスクリプトがタスクを1つずつ取り出し、タスクごとに新規・クリーンなコンテキストで`claude -p`を起動する**

この分離により、長時間の単一セッション運用で起きがちな「コンテキストあふれ」「指示忘れ」「無限思考」を根本的に回避する。締切判定・リトライ制御もすべて外側スクリプトの責務とし、Claudeは「1タスクを実装してPRを作るところまで」に集中させる。

### 1.2 全体シーケンス

```
[人] 夜間実行コマンドを入力
  ↓
[Claude:対話セッション] ヒアリング
  - 何時まで作業するか → 締切/ハードリミットを確定
  - タスクタイトル(複数可) → Notionで実在確認
  - 内容確認・要約提示
  - 実行してよいか確認(yes/No)
  ↓ yes
  night-run-state.json に 締切・タスクリスト(pending)を書き出して対話セッション終了
  ↓
[外側スクリプト] 実行フェーズ開始
  while 未処理タスクがある:
      現在時刻を確認
      if 現在時刻 >= 締切: break (新規タスクには着手しない)
      次のタスクを1件取り出す
      claude -p "<タスク単体の実装〜PR作成プロンプト>" --dangerously-skip-permissions
          → タスク内で: 実装→デバッグ→レビュー→修正→コンフリクト解消→PR作成
      exit code / stderr を確認
          正常終了 → state更新(done)、ループ継続
          レートリミットエラー → exponential backoffで待機・リトライ
          ハードリミット到達 → 強制終了処理(draft PR化)してループ終了
  終了サマリを生成
```

---

## 2. ヒアリングフェーズ仕様

対話セッション側で完結させる部分。実装としては1つの会話フロー(スラッシュコマンド等)として定義する。

### 2.1 確認する内容(順番)

1. **何時まで作業するか**
   - ユーザーは「6時」のように時刻のみを言う想定
   - 現在時刻から見て**一番近い未来の該当時刻**に変換する
     - 例:現在23:00で「6時」→ 翌日06:00
     - 例:現在04:00で「6時」→ 当日06:00
     - 例:現在07:00で「6時」→ 翌日06:00(すでに過ぎているため翌日扱い)
   - 変換結果を「〇月〇日 6:00までですね」と復唱して確認する
2. **やってほしいタスクのタイトル(複数可)**
   - Notion MCPで実在確認する。見つからないタイトルはその場で確認する(6章参照)
3. **タスク間の依存関係の申告**(v2で追加)
   - 「タスクAの変更が前提になるタスクはありますか?」と確認する
   - 依存ありと申告されたタスクは、7章のブランチ戦略に従って扱いを決める
4. **内容確認**
   - 各タスクのNotionページ内容を要約提示する
5. **実行確認(yes/No)**
   - すべてを踏まえて最終確認する。Noなら該当箇所をやり直す

### 2.2 ヒアリング完了時点で確定・書き出す情報

- 締切時刻(絶対日時、ISO8601、状態ファイルの`deadline`)
- ハードリミット時刻(締切+バッファ。**v6で確定:必ず絶対日時・確定値として計算し`hard_limit`に書き出す。ランタイム側では都度計算しない**。4.2節・5章参照)
- タスクリスト(タイトル、Notionページ参照、依存関係の有無、ステータス=`pending`)

ヒアリングセッションはこの書き出しをもって**終了する**。以降の処理は外側スクリプトに引き継ぐ。

---

## 3. タスク実行仕様(1タスク=1つの`claude -p`呼び出し)

### 3.1 起動コマンドの方針

```bash
claude -p "<タスクプロンプト>" \
  --output-format json \
  --dangerously-skip-permissions
```

- `--dangerously-skip-permissions`により確認プロンプトによる停止を防ぐ
- **このフラグを使う場合、必ずサンドボックス化された使い捨て環境(専用コンテナ/VM)上で実行すること。** ホストマシン上や他の重要データにアクセス可能な環境での使用は禁止する
- 1タスク=1回の起動なので、コンテキストは常にクリーンな状態から始まる

### 3.2 タスクプロンプト内のサイクル

1. **実装**:Notionのタスク内容をもとにコードを実装する
2. **デバッグ**:テスト・lintを実行し、失敗があれば修正する
3. **レビュー**:reviewerサブエージェントにレビューさせる
4. **修正**:指摘に対応する。3〜4を、テストgreenかつreviewer承認 または 最大ラウンド数到達まで繰り返す
5. **コンフリクト解消**:PR作成前に`origin/main`を取り込みコンフリクトを解消する
6. **PR作成**:
   - テストgreen かつ reviewer承認 → 通常PR(ready)
   - 最大ラウンド数到達 → draft PRとして作成し、本文に「完了した内容」「未完了の点」「次にやるべきこと」を明記

### 3.3 reviewerサブエージェント

- `--agents`オプションで定義。実装担当とは別視点を持つレビュー専任エージェント
- 観点:バグ、設計、テスト漏れ、規約違反など(運用しながら調整)

### 3.4 タスク内ループの停止条件

- テストgreen かつ reviewer承認 → 正常終了
- 最大ラウンド数(初期値:3〜5回、要調整)到達 → draft PRとして残し打ち切り
- 同じ指摘が2回連続 → 打ち切ってdraft PR化、指摘内容を本文に記載

### 3.5 締切判定はタスク内では行わない(v2での変更点)

タスクプロンプト側には時刻を確認させるルールを**含めない**。「新規タスクに着手してよいか」の判定は外側スクリプトが次のタスクを取り出す前に行う。一度起動したタスクは、途中で締切を過ぎても最後まで完走させる(=何もしなくても「今のタスクは完走」が実現される)。

---

## 4. 外側スクリプトの仕様

### 4.0 実装言語:Python(`night_runner.py`)に統一

Bashの`date -d`はGNU date(Linux)構文であり、macOS標準のBSD dateでは動作しない。サンドボックス実行環境はLinuxコンテナ前提でも、ローカルでの開発・検証をmacOSで行うケースを考えると、日付計算・JSON操作・リトライロジックを含む外側オーケストレーター全体をPython(標準ライブラリの`datetime`、`json`、`subprocess`)で組み、環境差異を吸収する。

**v5での方針変更**:v4まで4.1〜4.3節に分割してコード片を提示していたが、`run_claude_with_timeout`(タイムアウト処理)が実際にはどこからも呼ばれておらず、`save_state`のアトミック版も一部にしか反映されておらず、`handle_hard_limit_exceeded`が未定義のまま呼ばれている、という**統合漏れ**が第三者レビューで指摘された。これを踏まえ、以下では`night_runner.py`の内容を**1本の一貫したコード**として提示する。

**v6での追加修正**:v5の統合作業自体の中で、診断用ブランチとPR作成対象ブランチが食い違うバグ、および`hard_limit`キーの前提が5章と矛盾する問題が新たに見つかった。これらもv6で修正済み。以降このセクション全体が実装のリファレンスであり、過去バージョンの断片コードは参照しないこと。

### 4.1 `night_runner.py` 全体像(統合版)

```python
import json
import os
import re
import signal
import subprocess
import sys
import tempfile
import time
import datetime

STATE_FILE = "night-run-state.json"
RATE_LIMIT_PATTERN = re.compile(r"rate limit|429|usage limit", re.IGNORECASE)


# --- サンドボックス確認ガード(0.2節) ---
def assert_sandbox_or_exit():
    if os.environ.get("NIGHT_RUNNER_SANDBOX") != "1":
        print("致命的エラー: サンドボックス環境が確認できません。実行を中止します。", file=sys.stderr)
        sys.exit(1)


# --- 状態ファイルの読み書き(アトミック書き込み、9.7節) ---
def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    state["last_updated"] = datetime.datetime.now().isoformat()
    dir_name = os.path.dirname(os.path.abspath(STATE_FILE))
    with tempfile.NamedTemporaryFile("w", dir=dir_name, delete=False, suffix=".tmp") as tmp:
        json.dump(state, tmp, indent=2, ensure_ascii=False)
        tmp_path = tmp.name
    os.replace(tmp_path, STATE_FILE)  # アトミックな置き換え


# --- git操作 ---
def git_cleanup():
    assert_sandbox_or_exit()  # 破壊的コマンドの前に必ず確認する
    subprocess.run(["git", "checkout", "main"], check=True)
    subprocess.run(["git", "reset", "--hard"], check=True)
    subprocess.run(["git", "clean", "-fd"], check=True)


def save_diagnostic_branch(task):
    # cleanupで消える前に、原因調査用に現状をブランチへ退避する
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"diagnostic/{task['title']}-{ts}"
    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", f"wip: 異常終了時点のスナップショット ({task['title']})", "--allow-empty"], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)
    return branch


def create_draft_pr_from_branch(task, branch, reason):
    # v6での修正: 退避先ブランチを引数で明示的に受け取る(task["branch"]頼みにしない)。
    # v5では task.get("branch") を優先していたため、save_diagnostic_branch が
    # 実際にコミットしたブランチとPR作成対象が食い違うバグがあった。
    # PR本文はプレースホルダーであり、Skill実装時に実際の完了内容・未完了点を
    # 埋め込むこと。プレースホルダーのまま本番のdraft PRに載せてはならない。
    body = (
        f"## 自動終了理由\n{reason}\n\n"
        f"## 完了した内容\n"
        f"# TODO(実装時に埋める): タスクプロンプトの出力・state[\"tasks\"][].step を参照して記載する\n\n"
        f"## 未完了の点 / 次にやるべきこと\n"
        f"# TODO(実装時に埋める): 手動での確認・引き継ぎ内容を記載する\n"
    )
    subprocess.run(["git", "push", "origin", branch], check=True)
    subprocess.run([
        "gh", "pr", "create", "--draft",
        "--head", branch,  # v6で追加: 現在のチェックアウト状態に依存させず、対象ブランチを明示する
        "--title", f"WIP: {task['title']} ({reason})",
        "--body", body,
    ], check=True)


# --- タスク状態の更新 ---
def update_state_done(task, state, claude_stdout):
    # 9.3節: claude -p --output-format json の標準出力は、Claude Code CLI自体の
    # レスポンスエンベロープ(実行結果・コストなどを含む構造)であり、タスク固有の
    # {"status": ..., "pr_url": ...} はその中の結果テキスト部分にClaude自身が
    # 出力したJSONブロックとして埋め込まれる想定。
    # 以下は「エンベロープ全体をそのままパースすればpr_urlが取れる」という仮実装であり、
    # 実際の抽出方法(エンベロープのどのフィールドからタスク用JSONを取り出すか)は
    # 9.3節でまだ未確定。Skill実装時にタスクプロンプト側の出力形式と合わせて確定させること。
    parsed = json.loads(claude_stdout)  # TODO(9.3節): 実際のエンベロープ構造に合わせて修正する
    task["status"] = "done"
    task["pr_url"] = parsed.get("pr_url")
    save_state(state)


def mark_task_failed(task, state, reason, diagnostic_branch=None):
    task["status"] = "failed"
    task["failure_reason"] = reason
    if diagnostic_branch:
        task["diagnostic_branch"] = diagnostic_branch
    save_state(state)


def log_unexpected_error(task, state, stderr_text):
    print(f"[ERROR] タスク「{task['title']}」で予期しないエラー: {stderr_text}", file=sys.stderr)


# --- v5で新規定義: v4で呼ばれていたが未定義だった関数(v6でブランチ不整合バグを修正) ---
def handle_hard_limit_exceeded(task, state):
    # v6での修正: save_diagnostic_branch が返したブランチ名をそのまま
    # create_draft_pr_from_branch に渡す(v5では task["branch"] を優先してしまい、
    # 実際にコミットした診断ブランチとPR作成対象が食い違うバグがあった)
    branch = save_diagnostic_branch(task)
    mark_task_failed(task, state, reason="hard_limit_exceeded", diagnostic_branch=branch)
    create_draft_pr_from_branch(task, branch, reason="締切バッファを超過したため強制終了")


# --- claude -pの実行(プロセスグループごとタイムアウト管理、4.2節) ---
def run_claude_with_timeout(prompt, timeout_seconds):
    proc = subprocess.Popen(
        ["claude", "-p", prompt, "--output-format", "json", "--dangerously-skip-permissions"],
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True  # 新しいプロセスグループを作る
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # 孫プロセスごと強制終了
        proc.wait()
        return None, "", "TIMEOUT"


def build_prompt(task, state):
    # タスク内容・reviewerサブエージェント定義・9.2/9.3の出力ルールを埋め込んだプロンプトを組み立てる
    raise NotImplementedError("タスクプロンプトの具体的な組み立てはSkill実装時に定義する")


# --- タスク単体の実行+レートリミットへのリトライ(4.3節) ---
def run_task_with_retry(task, state):
    attempt = 0
    while True:
        hard_limit = datetime.datetime.fromisoformat(state["hard_limit"])
        now = datetime.datetime.now(datetime.timezone.utc)
        if now >= hard_limit:
            handle_hard_limit_exceeded(task, state)
            return

        remaining_seconds = (hard_limit - now).total_seconds()
        returncode, stdout, stderr = run_claude_with_timeout(
            build_prompt(task, state), timeout_seconds=remaining_seconds
        )

        if stderr == "TIMEOUT":
            # タスク実行中にハードリミットへ到達した場合も同じ経路で処理する
            handle_hard_limit_exceeded(task, state)
            return

        if returncode == 0:
            update_state_done(task, state, stdout)
            return

        if RATE_LIMIT_PATTERN.search(stderr):
            attempt += 1
            wait_seconds = (2 ** (attempt - 1)) * 60  # 60, 120, 240, 480, ...
            print(f"レートリミット検知。{wait_seconds}秒待機してリトライします。")
            time.sleep(wait_seconds)
            continue
        else:
            # レートリミット以外のエラー: 診断用ブランチへ退避してからfailedに更新し、
            # 次のタスクへ進む(無限リトライを防止)
            branch = save_diagnostic_branch(task)
            mark_task_failed(task, state, stderr, diagnostic_branch=branch)
            log_unexpected_error(task, state, stderr)
            return


def generate_summary(state):
    done = [t for t in state["tasks"] if t["status"] == "done"]
    failed = [t for t in state["tasks"] if t["status"] == "failed"]
    pending = [t for t in state["tasks"] if t["status"] == "pending"]
    print(f"完了: {len(done)}件 / 失敗: {len(failed)}件 / 未着手: {len(pending)}件")
    # 実際にはSlack通知やesa/Notionへのレポート投稿などをここに実装する


# --- メインループ ---
def main():
    assert_sandbox_or_exit()  # 0.2節: 実行環境の安全性を最初に確認する

    initial_state = load_state()
    if "hard_limit" not in initial_state:
        print("設定エラー: state に hard_limit がありません。ヒアリング完了時点で確定値を書き出してください。", file=sys.stderr)
        sys.exit(1)
    for t in initial_state["tasks"]:
        if t.get("depends_on"):
            print(f"設定エラー: タスク「{t['title']}」に未解決の依存が残っています。ヒアリング時点で解消してください。", file=sys.stderr)
            sys.exit(1)

    while True:
        state = load_state()
        now = datetime.datetime.now(datetime.timezone.utc)
        deadline = datetime.datetime.fromisoformat(state["deadline"])

        if now >= deadline:
            print("締切到達。新規タスクには着手しません。")
            break

        pending = [t for t in state["tasks"] if t["status"] == "pending"]
        if not pending:
            print("全タスク完了。")
            break

        task = pending[0]

        # 次のタスクに入る前に必ずクリーンな状態へ戻す
        git_cleanup()

        run_task_with_retry(task, state)

    generate_summary(load_state())


if __name__ == "__main__":
    main()
```

### 4.2 ハードリミット・タイムアウトの扱い(結論)

- ソフトカットオフ(締切):新規タスク着手の可否判定にのみ使用(`main()`のループ先頭)
- ハードリミット(締切+バッファ):`run_claude_with_timeout`の`timeout_seconds`として、残り時間をそのまま渡す。到達すると`TimeoutExpired`が発生し、`os.killpg`でプロセスグループごと`SIGKILL`される(孫プロセスの残存を防止)
- **v5で確定、v6でバグ修正**:ハードリミット到達の経路は「タスク開始前のチェック」「タスク実行中のタイムアウト」のどちらも`handle_hard_limit_exceeded`に集約する。中身は`mark_task_failed`と同様に診断用ブランチへ退避した上で、`create_draft_pr_from_branch`によりdraft PRを作成する。**v5では退避先ブランチとPR作成対象ブランチが食い違うバグがあったため、v6で`save_diagnostic_branch`の戻り値を明示的に受け渡す形に修正した**(4.1節のコード参照)
- バッファ長は「1タスクが完走するのに要する最大想定時間」を目安に設定する(初期値:90分など、要調整)

### 4.3 トークン切れ(レートリミット)の検知とリトライ

`run_task_with_retry`(4.1節)内で、tmuxでのプロセス生存監視ではなく**exit codeとstderrの文字列マッチ**により検知する。Exponential Backoffはレートリミットの解除粒度(数分〜数十分単位のことが多い)を踏まえ、`2^(attempt-1) × 60`秒(60→120→240→480…)とする。

- レートリミット由来のエラーのみリトライ対象とし、それ以外のエラー(実装上の異常終了など)は必ず`status`を`failed`に更新した上で人間に引き継ぐ。これにより同一タスクへの無限リトライを防ぐ
- 失敗したタスクの作業ツリーは、次のタスク取り出し時の`git_cleanup()`で消去される前に診断用ブランチへpushしておく。翌朝の調査はこのブランチとstderrログの両方を参照できる
- リトライ再開時、途中まで進んでいた実装は`night-run-state.json`の`step`情報を元に、`build_prompt`が「ここまで完了している内容」を含めたプロンプトを組み立てて再開させる(セッションIDでの復元ではなく、状態ファイルベースでの再開)
- backoffの上限(何回までリトライするか、上限秒数をキャップするか)は運用しながら調整する。ハードリミット到達で自動的に打ち切られるため、無限リトライにはならない
- **運用方針の確認事項**:1タスクが`failed`になった場合、残りのタスクの実行を続けるか、その夜のジョブ全体を停止するかは要検討(初期方針としては「続行し、終了サマリで失敗タスクを明示」とする)

---

## 5. 状態ファイル(`night-run-state.json`)

**v4での修正**:旧v3の例では、依存ありのタスク(`depends_on`が非null)が`pending`のまま単独でタスクリストに残っており、7.2節の解消ルール(まとめる/別の夜に回す)と矛盾していた。正しくは、**ヒアリング完了時点で依存関係は解消済みであるべきで、実行フェーズのタスクリストに未解決の依存(`depends_on`が非null)が残ることはない**。「1ブランチにまとめる」場合はまとめた結果を1つのタスクエントリとして書き出し、「別の夜に回す」場合はそのタスクを今夜のリストに含めない。

```json
{
  "deadline": "2026-08-30T06:00:00+09:00",
  "hard_limit": "2026-08-30T07:30:00+09:00",
  "hard_limit_buffer_minutes": 90,
  "tasks": [
    { "title": "タスクA", "status": "done", "pr_url": "https://github.com/.../pull/12", "branch": "feature/task-a" },
    { "title": "タスクB", "status": "in_progress", "step": "review", "branch": "feature/task-b", "review_round": 2 },
    { "title": "タスクC + タスクD(依存によりまとめて実施)", "status": "pending", "branch": "feature/task-c-d" }
  ],
  "last_updated": "2026-08-30T02:14:00+09:00"
}
```

- **v6で確定(第三者レビュー反映)**:4.1節の統合コードは`state["hard_limit"]`が必ず存在する前提で書かれている一方、本節はv3から「都度計算してもよいし確定値でもよい」と未決定のままだった。これを解消し、**`hard_limit`は必ずヒアリング完了時点で確定値(ISO8601文字列)として書き出す**ことを正式なルールとする。`hard_limit_buffer_minutes`はヒアリング時にどれだけのバッファを取ったかの記録用に残すが、ランタイム側が都度計算し直すことはしない。ヒアリングフェーズのSkill実装時、`hard_limit`の書き出し漏れがあると`night_runner.py`起動直後に`KeyError`で即死するため、この項目は必須フィールドとして明記する
- `depends_on`フィールドは状態ファイルには持たせない(ヒアリング時点で解消済みのため)。依存関係の記録が必要な場合は、ヒアリングログ側に残す
- **ランタイム側のバリデーション(v4で追加)**:念のため、`night_runner.py`起動時に状態ファイルを読み込んだ際、万一`depends_on`を持つタスクが存在した場合は設定エラーとして即座に異常終了する(4.1節参照)。同様に`hard_limit`キーが存在しない場合も設定エラーとして即座に異常終了するチェックを追加する(4.1節`main()`に反映)

---

## 6. Notionタイトルが見つからない場合

ヒアリング時点でその場でユーザーに確認する(表記揺れ、未作成など)。実行フェーズに入ってから見つからない場合は想定しない(ヒアリング完了時点で実在確認済みのため)。

---

## 7. gitブランチ戦略・タスク間依存の扱い(v2で追加)

### 7.1 基本ルール

- 各タスクは**必ず`origin/main`から個別ブランチを切る**。他のタスクのブランチから派生させない
- これにより、あるタスクが未完了・失敗しても他のタスクに影響しない

### 7.2 依存関係があるタスクの扱い

ヒアリング時点(2.1節)で依存関係を申告してもらい、以下のいずれかを選択する。**いずれの場合も、ヒアリング完了時点で依存関係は解消され、実行フェーズのタスクリスト(5章)には未解決の依存を持つタスクは残らない。**

- **同じ夜にまとめて1ブランチで進める**:依存する複数タスクを1つの実装単位として扱い、1つのタスクプロンプト・1つの状態ファイルエントリにまとめて実行する(PRも1つになる)
- **別の夜に回す**:依存元のタスクが完了(マージ)されるまで、依存先のタスクは**今夜のタスクリストに含めない**(状態ファイルに書き出さない)

依存関係が申告されなかったにもかかわらず実行時にコンフリクトが多発する場合は、そのタスクを異常系としてログに残し、人間にエスカレーションする(自動での依存解決は行わない)。

---

## 8. その他エッジケース・要検討事項

- **reviewerとの堂々巡り**:同じ指摘が2回連続 → 打ち切りdraft PR化(3.4節)
- **PRベースブランチの事後更新によるコンフリクト**:PR作成後に発生したコンフリクトは本設計のスコープ外とし、別フロー(人間レビュー後の`@claude`メンションによる自動修正)で対応する
- **最大ラウンド数・バッファ時間・exponential backoffの初期値**:設計上は暫定値を置いているが、実運用しながら調整することを前提とする
- **`--dangerously-skip-permissions`使用時のサンドボックス化**:0章参照(実装着手前の必須前提条件として格上げ済み)

---

## 9. 残課題(実装着手前に詰める必要がある事項)

以下は設計思想としては問題ないが、実装レベルの詳細が未確定のためClaude Codeへの依頼時に明示しておくべき事項。**0章のブロッカーとは異なり、実装を進めながら並行して詰めることが可能な項目。**

### 9.1 `night_runner.py`自体の常駐化・監視

- ヒアリングセッション終了後、誰(何)が`night_runner.py`を起動するかが未定義。人間がターミナルを閉じても動き続けるよう、`nohup`/`systemd`/デーモン化などでバックグラウンド起動する処理を明記する必要がある
- サーバー再起動・プロセスクラッシュへの耐性(監視プロセスによる自動再起動)も現状未対応。`systemd`の`Restart=on-failure`、あるいは外部の軽量監視(cronでプロセス生存確認→死んでいたら`night-run-state.json`を見て再起動)などを検討する

### 9.2 タスク実行中の途中経過(`step`)の書き込み主体

- `update_state_done`は「タスク完了時」にのみ呼ばれる想定になっている
- タスク実行中(実装中/レビュー中など)にレートリミットで`claude -p`プロセスが落ちた場合、途中経過を`night-run-state.json`に書き込むのはClaude自身(タスクプロンプト内でBashツール経由のファイル書き込み)である必要がある
- タスクプロンプト側に「各ステップ完了時点で状態ファイルの該当タスクの`step`を更新すること」という指示を明記する必要がある。この書き込みも9.7のアトミック化ルールに従うこと

### 9.3 `claude -p`出力からの成功可否・PR URL抽出ルール

- `--output-format json`はClaudeの応答を構造化して返すが、「タスク成功/失敗」「PR URL」をどう抽出するかの取り決めがない
- タスクプロンプト側に「最後に決まったスキーマのJSONブロックを出力すること」という指示を入れ、`night_runner.py`側でそのJSONをパースするルールを定義する必要がある(例:`{"status": "success", "pr_url": "...", "review_round": 2}`)

### 9.4 タスク実行のタイムアウト(v5で統合・確定)

- v4で提示した`run_claude_with_timeout`が実際には呼ばれていない、`handle_hard_limit_exceeded`が未定義、という統合漏れがあったが、v5の4.1節で1本のコードに統合し解消した
- ハードリミット到達の経路(タスク開始前のチェック/タスク実行中のタイムアウト)は`handle_hard_limit_exceeded`に一本化し、診断用ブランチへの退避+draft PR作成という結論で確定させた(4.2節参照)

### 9.5 (0章へ統合)サンドボックス実行環境の具体化

この項目は実装着手前の必須前提条件のため0章へ移動した。詳細は0.1節を参照。

### 9.6 ドライラン計画

- 「締切を数分後に短縮して試す」という検証手順を設計に反映していなかった
- 本番投入前に、以下のようなドライランを最低1回実施する:
  - 締切を現在時刻+5〜10分に設定
  - タスクを1〜2件の軽量なもの(既存コードの小さな修正など)にする
  - ソフトカットオフ・ハードリミット・レートリミット時のリトライ(意図的に再現できるなら)・gitクリーンアップ・エラー時のfailed更新と診断用ブランチ退避が期待通り動くかを確認する

### 9.7 状態ファイル(`night-run-state.json`)の書き込みをアトミック化する(v4で追加、v5で4.1節に統合済み)

- v4時点では修正版`save_state`が9.7節にのみ記載され、4.1節のメインコードには反映されていない、という統合漏れがあった。v5では4.1節の`save_state`をアトミック版に統一済み
- 9.2で触れているClaude自身によるタスクプロンプト内での`step`書き込みも、同じアトミック書き込みパターンを使うよう指示に含める(この部分はタスクプロンプト側の実装であり、`night_runner.py`本体とは別に対応が必要)

### 9.8 `claude -p`の自己申告JSON(成功可否・PR URL)を外側スクリプトが無条件に信じている(v5で追加)

- 現状の`update_state_done`は、`claude -p`が返すJSON(`status`/`pr_url`)をそのまま信用して`done`に更新している
- Claude自身の自己申告が誤っている場合(例:実際にはPRが作成されていないのに成功と報告する)を検知できない
- 対策案:`update_state_done`内で`gh pr view <pr_url>`等を実行し、PRが実在すること・対象ブランチが一致することを外側スクリプト側で独立に検証してから`done`に更新する。検証に失敗した場合は`failed`として扱う

### 9.9 `failed`発生時の人間への即時通知(v5で追加)

- 現状、`mark_task_failed`は状態ファイルを更新するのみで、人間への通知は行われない。朝までエラーに気づけない可能性がある
- 対策案:`mark_task_failed`または`log_unexpected_error`の中でSlack Webhook等への通知を追加する。夜間実行である以上、致命的でないエラーは朝まで待ってよいが、「サンドボックスガードでの異常終了」など0章に関わる異常は即時通知が望ましい

### 9.10 Exponential Backoffの上限が未数値化(v5で追加)

- 4.3節のbackoffは`2^(attempt-1) × 60`秒で無限に増加する。ハードリミット到達で自動的に打ち切られるため実害は限定的だが、明示的な上限(例:最大5回、または1回あたりの待機を最大30分でキャップ)を数値化しておくと運用時の見通しが良くなる

---

## 10. MCP・外部接続

| 対象 | 方法 | 備考 |
|---|---|---|
| Notion | 公式Notion MCPサーバーを`claude mcp add`で登録 | Notion側でIntegration作成、対象データベースへの権限付与、トークン発行が必要 |
| GitHub(PR作成) | MCP不要。標準の`Bash`ツールから`gh pr create`等をそのまま利用 | 事前に`gh auth login`を済ませておく |

---

## 11. 実装スコープ(Claude Codeへの依頼事項)

**実装順序の注意**:0章(サンドボックス実行環境の具体化とサンドボックス確認ガード)は他のすべての前提となるため、最初に着手・確定させること。それ以外は以下に加えて9章の残課題(常駐化・監視、途中経過の書き込み、出力パースルール、ドライラン計画、状態ファイルのアトミック書き込み)も実装時に併せて詰めること。

1. サンドボックス実行環境の構築とサンドボックス確認ガードの実装(0章、最優先)
2. ヒアリングフェーズを実行するSkill(スラッシュコマンド等)。完了時に`night-run-state.json`を書き出して終了する。依存関係の解消(7.2節)をこの時点で完了させる
3. タスク単体の実装〜PR作成サイクルを行うタスクプロンプト/Skill(reviewerサブエージェント定義含む、9.2・9.3の出力ルールに準拠)
4. 外側の実行制御スクリプト`night_runner.py`(Python、4章):タスクループ、締切判定、サンドボックス確認ガード付きgitクリーンアップ、`--dangerously-skip-permissions`での起動、exit code/stderr監視、exponential backoffリトライ、プロセスグループごとのタイムアウト処理、失敗タスクのfailed更新と診断用ブランチ退避、ハードリミット強制終了・draft PR化
5. `night-run-state.json`の読み書き・バリデーションロジック(アトミック書き込み、`depends_on`残存チェック含む)
6. gitブランチ戦略の実装(各タスク個別ブランチ、依存タスクの合流ロジック)
7. (必要であれば)esa用の薄いMCPサーバー
8. `night_runner.py`の常駐化・監視の仕組み(9.1参照)
