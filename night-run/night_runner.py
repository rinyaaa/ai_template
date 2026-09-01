#!/usr/bin/env python3
"""夜間自律タスク実行の外側オーケストレーター(docs/night-run-design.md 4章)。

サンドボックス化されたDockerコンテナ内で動くことを前提にしている。
ホスト側で直接実行してはならない(assert_sandbox_or_exitが拒否する)。
"""
import json
import os
import re
import signal
import subprocess
import sys
import time
import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _state_io import atomic_write_json  # noqa: E402

REPO_DIR = os.environ.get("NIGHT_RUN_REPO_DIR", "/workdir/repo")
# state/ はgit管理下に置かない(git_cleanupのgit clean -fdで消えるのを防ぐため、
# リポジトリの外・別のbind mountに置く前提)。
STATE_FILE = os.environ.get("NIGHT_RUN_STATE_FILE", "/workdir/state/night-run-state.json")
ALERTS_LOG = os.path.join(os.path.dirname(STATE_FILE), "alerts.log")

RATE_LIMIT_PATTERN = re.compile(r"rate.?limit|429|usage limit|overloaded", re.IGNORECASE)
MAX_RETRY_ATTEMPTS = 5          # 9.10節: backoffの上限回数
MAX_BACKOFF_SECONDS = 1800      # 9.10節: 1回あたりの待機を最大30分でキャップ
MAX_REVIEW_ROUNDS = 4           # 3.4節: reviewerサイクルの最大ラウンド数
MAX_BUDGET_USD_PER_TASK = float(os.environ.get("NIGHT_RUN_MAX_BUDGET_USD", "15"))

REVIEWER_AGENT_DEFINITION = {
    "reviewer": {
        "description": (
            "実装担当とは別視点でコードレビューを行う専任エージェント。"
            "バグ・設計・テスト漏れ・AGENTS.md/CLAUDE.mdの規約違反を指摘する。"
        ),
        "prompt": (
            "あなたはこのリポジトリのコードレビュー専任エージェントです。実装は行わず、"
            "レビューだけを行ってください。以下の観点で指摘してください:\n"
            "- バグ・エッジケースの考慮漏れ\n"
            "- テストの過不足(新機能・修正に対するテストの有無)\n"
            "- AGENTS.md/CLAUDE.mdの規約違反(状態管理・データクラスの書き方など、"
            "リポジトリ固有の規約があればそれに従っているか)\n"
            "- 設計上の重大な懸念(小さなスタイルの好みは指摘しない)\n"
            "問題がなければ「LGTM」とだけ明確に述べてください。"
        ),
    }
}

TASK_RESULT_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["success", "draft", "failed"]},
        "pr_url": {"type": ["string", "null"]},
        "branch": {"type": "string"},
        "review_round": {"type": "integer"},
        "completed_summary": {"type": "string"},
        "remaining_summary": {"type": "string"},
    },
    "required": [
        "status", "pr_url", "branch", "review_round",
        "completed_summary", "remaining_summary",
    ],
}


# --- サンドボックス確認ガード(0.2節) ---
# 環境変数だけだと `NIGHT_RUNNER_SANDBOX=1 python3 night_runner.py` とホストで
# 直接打たれたら素通りしてしまう(spoof可能)。Dockerfileがイメージにしか
# 焼き込まないマーカーファイルも合わせて確認することで、実際にそのイメージから
# 起動されたコンテナ内であることを担保する。
SANDBOX_MARKER_FILE = "/.sandbox-marker"


def assert_sandbox_or_exit():
    ok = (
        os.environ.get("NIGHT_RUNNER_SANDBOX") == "1"
        and os.path.exists(SANDBOX_MARKER_FILE)
    )
    if not ok:
        message = "致命的エラー: サンドボックス環境が確認できません(環境変数またはマーカーファイルが無い)。実行を中止します。"
        print(message, file=sys.stderr)
        notify_human(message)
        sys.exit(1)


# --- 人間への通知(9.9節) ---
def notify_human(message):
    line = f"{datetime.datetime.now().isoformat()} {message}"
    print(f"[ALERT] {message}", file=sys.stderr)
    try:
        os.makedirs(os.path.dirname(ALERTS_LOG), exist_ok=True)
        with open(ALERTS_LOG, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass
    # 拡張ポイント: Slack Incoming Webhook等を使うなら、
    # NIGHT_RUN_ALERT_WEBHOOK_URL を見てここでPOSTする(今回のスコープ外)。


# --- 状態ファイルの読み書き(アトミック書き込み、9.7節) ---
def load_state():
    with open(STATE_FILE) as f:
        return json.load(f)


def save_state(state):
    state["last_updated"] = datetime.datetime.now().isoformat()
    atomic_write_json(STATE_FILE, state)


def _slug(text):
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", text).strip("-.")
    return slug or "task"


def backoff_seconds(attempt):
    """9.10節: 2^(attempt-1)*60秒、上限MAX_BACKOFF_SECONDSでキャップする。"""
    return min((2 ** (attempt - 1)) * 60, MAX_BACKOFF_SECONDS)


def _envelope_is_rate_limited(envelope):
    """claude -pはAPIレベルのレートリミットをexit code 0 + JSON封筒内のis_error=true
    として返すことがある(stderrの文字列マッチだけでは拾えない)。"""
    if not isinstance(envelope, dict) or not envelope.get("is_error"):
        return False
    text = f"{envelope.get('subtype', '')} {envelope.get('result', '')}"
    return bool(RATE_LIMIT_PATTERN.search(text))


# --- git操作 ---
# git_cleanup()はAGENTS.md安全ルール1が禁じるgit reset --hard/git cleanをそのまま使う。
# .claude/hooks/deny_dangerous_bash.pyはClaude Code自身のBashツール呼び出ししか
# 検査できないため、night_runner.pyのこの生subprocess呼び出しはそのフックの対象外
# ——ここが安全に許されるのは、night_runner.py自体がDockerサンドボックス(named
# volumeへのclone、ホストリポジトリはbind mountしない)内でしか動かないことを
# assert_sandbox_or_exit()が起動時に強制しているため。この前提が崩れると
# git_cleanup()はホストの実リポジトリを容赦なく吹き飛ばす。
def git_cleanup():
    assert_sandbox_or_exit()  # 破壊的コマンドの前に必ず確認する
    subprocess.run(["git", "fetch", "origin"], check=True)
    # -f: 前のタスクの未コミット変更(mergeコンフリクトの残骸等)があってもcheckoutを
    # 拒否させない。どうせ直後にreset --hard/clean -fdで消えるので安全。
    subprocess.run(["git", "checkout", "-f", "main"], check=True)
    subprocess.run(["git", "reset", "--hard", "origin/main"], check=True)
    subprocess.run(["git", "clean", "-fd"], check=True)


def git_cleanup_with_retry(max_attempts=3, wait_seconds=60):
    """git_cleanup()はcheck=Trueの生subprocess呼び出しの列で、ネットワークの
    一時的な不調(git fetchの瞬断等)でもCalledProcessErrorを投げる。ここで
    吸収しないと、その場でnight_runner.py全体が無通知でクラッシュし、
    残りの未着手タスクについて誰にも気付かれないまま朝を迎えることになる。"""
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            git_cleanup()
            return
        except subprocess.CalledProcessError as e:
            last_error = e
            notify_human(f"git_cleanup()に失敗(試行{attempt}/{max_attempts}): {e}")
            if attempt < max_attempts:
                time.sleep(wait_seconds)
    raise last_error


def save_diagnostic_branch(task):
    # cleanupで消える前に、原因調査用に現状をブランチへ退避する
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    branch = f"diagnostic/{_slug(task['title'])}-{ts}"
    subprocess.run(["git", "checkout", "-b", branch], check=True)
    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", f"wip: 異常終了時点のスナップショット ({task['title']})", "--allow-empty"], check=True)
    subprocess.run(["git", "push", "origin", branch], check=True)
    return branch


def create_draft_pr_from_branch(task, branch, reason):
    # プレースホルダーは書かない。state中の最後のstep/review_roundから
    # 実際の進捗を埋め込む(冒頭の注記が警告している事故の対応)。
    step = task.get("step", "(記録なし)")
    review_round = task.get("review_round", "(記録なし)")
    completed = task.get("completed_summary") or f"最後に記録された作業段階: {step}"
    remaining = task.get("remaining_summary") or (
        f"{branch} の作業ツリー・コミット履歴を確認してください。"
    )
    body = (
        f"## 自動終了理由\n{reason}\n\n"
        f"## 完了した内容\n{completed}\n\n"
        f"## 未完了の点 / 次にやるべきこと\n{remaining}\n\n"
        f"## 診断情報\n"
        f"- 退避ブランチ: `{branch}`\n"
        f"- 最終step: `{step}`\n"
        f"- レビューラウンド: {review_round}\n"
    )
    subprocess.run(["git", "push", "origin", branch], check=True)
    subprocess.run([
        "gh", "pr", "create", "--draft",
        "--head", branch,
        "--title", f"WIP: {task['title']} ({reason})",
        "--body", body,
    ], check=True)


def verify_pr(pr_url, expected_branch):
    """9.8節: claude -pの自己申告を無条件に信じず、実在するPRか外側で検証する。"""
    if not pr_url or not expected_branch:
        return False
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_url, "--json", "url,headRefName,state"],
            capture_output=True, text=True, check=True,
        )
        info = json.loads(result.stdout)
    except (subprocess.CalledProcessError, json.JSONDecodeError):
        return False
    return info.get("headRefName") == expected_branch and info.get("state") == "OPEN"


# --- タスク状態の更新 ---
def update_state_done(task, state, claude_stdout):
    def fail(reason):
        branch = save_diagnostic_branch(task)
        mark_task_failed(task, state, reason, diagnostic_branch=branch)

    try:
        envelope = json.loads(claude_stdout)
    except json.JSONDecodeError as e:
        fail(f"claude -p の出力がJSONとして解釈できない: {e}")
        return

    if envelope.get("is_error"):
        fail(f"claude -p がエラー終了(subtype={envelope.get('subtype')}): {str(envelope.get('result'))[:500]}")
        return

    structured = envelope.get("structured_output")
    if not isinstance(structured, dict):
        fail("structured_output が得られなかった(自己申告JSONの欠落)")
        return

    status = structured.get("status")
    pr_url = structured.get("pr_url")

    if status not in ("success", "draft"):
        fail(f"タスクからの報告がfailed: {structured.get('remaining_summary')}")
        return

    if not verify_pr(pr_url, task.get("branch")):
        fail(f"PRの実在確認に失敗した(自己申告URL: {pr_url})")
        return

    task["status"] = "done"
    task["pr_status"] = status  # "success"(ready) か "draft"
    task["pr_url"] = pr_url
    task["review_round"] = structured.get("review_round")
    task["completed_summary"] = structured.get("completed_summary")
    task["remaining_summary"] = structured.get("remaining_summary")
    save_state(state)


def mark_task_failed(task, state, reason, diagnostic_branch=None):
    task["status"] = "failed"
    task["failure_reason"] = reason
    if diagnostic_branch:
        task["diagnostic_branch"] = diagnostic_branch
    save_state(state)
    notify_human(f"タスク「{task['title']}」が failed になりました: {reason}")


def log_unexpected_error(task, state, stderr_text):
    print(f"[ERROR] タスク「{task['title']}」で予期しないエラー: {stderr_text}", file=sys.stderr)


def handle_hard_limit_exceeded(task, state):
    branch = save_diagnostic_branch(task)
    mark_task_failed(task, state, reason="hard_limit_exceeded", diagnostic_branch=branch)
    create_draft_pr_from_branch(task, branch, reason="締切バッファを超過したため強制終了")


def _issue_urls(task):
    """issue_urlは単一issueなら文字列、依存関係でまとめたタスクなら配列で持つ。
    どちらでも扱えるようにリストへ正規化する。"""
    raw = task.get("issue_url") or task.get("issue_urls") or []
    if isinstance(raw, str):
        return [raw] if raw else []
    return list(raw)


# --- タスクプロンプトの組み立て(3章) ---
def build_prompt(task, state):
    resume_note = ""
    if task.get("step"):
        resume_note = (
            f"\n## 再開についての注意\n"
            f"このタスクは以前の試行で `{task['branch']}` ブランチまで進んでいます"
            f"(最後に記録された段階: {task['step']}, レビューラウンド: {task.get('review_round', 0)})。"
            f"`git fetch origin && git checkout {task['branch']}` でこのブランチを再開し、"
            f"ゼロから作り直さないでください。\n"
        )

    urls = _issue_urls(task)
    if len(urls) <= 1:
        issue_fetch_instruction = f"`gh issue view {urls[0] if urls else ''}` でこのタスクの内容(issue本文)を取得し、実装する。"
    else:
        view_lines = "\n".join(f"   - `gh issue view {u}`" for u in urls)
        issue_fetch_instruction = (
            f"以下の複数issue(依存関係により1タスクにまとめられている)をすべて取得し、"
            f"まとめて実装する。片方だけ実装して終わりにしないこと:\n{view_lines}"
        )
    closes_line = " ".join(f"Closes {u}" for u in urls) if urls else ""

    return f"""あなたはこのリポジトリの実装エージェントです。以下の1タスクを実装からPR作成まで完走させてください。

## タスク
- タイトル: {task['title']}
- 使用するブランチ: `{task['branch']}`(まだ存在しなければ `origin/main` から新規作成する)
{resume_note}
## 手順
1. {issue_fetch_instruction} 実装規約はAGENTS.md/CLAUDE.mdに従うこと。
2. 各段階が終わるたびに以下を実行し、進捗を記録する(必須。レートリミット等で中断しても再開できるようにするため):
   `python3 night-run/update_step.py "{task['title']}" "<段階名: 実装/デバッグ/レビュー/修正/コンフリクト解消/PR作成>" [レビューラウンド数]`
3. CLAUDE.mdに記載のテスト・静的解析コマンド(例: `npm test` / `pytest` / `flutter test` 等、プロジェクトに合わせて読み替える)を実行し、失敗があれば直す。
4. Task/Agentツールで `reviewer` サブエージェントにレビューさせ、指摘に対応する。
   - グリーン かつ reviewer承認 → 次へ
   - 同じ指摘が2回連続、または最大{MAX_REVIEW_ROUNDS}ラウンドに到達 → そこで打ち切り、readyではなくdraftとして扱う
5. PR作成前に `git fetch origin && git merge origin/main` でコンフリクトを解消する。
   **重要**: `git reset --hard` / `git clean` / `git push --force`(force-with-lease含む)は、このリポジトリの
   安全網で常にブロックされる。使う必要が生じたらやり方が間違っているサインなので、代わりに新しいコミットで対応すること。
6. `gh pr create` でPRを作成する。
   - グリーン かつ reviewer承認 → 通常PR(ready)。本文に `{closes_line}` を含め、マージ時に対象issueが自動クローズされるようにする
   - 打ち切りの場合 → `--draft` を付け、本文に「完了した内容」「未完了の点」「次にやるべきこと」を書く(このケースはまだ未完了なので `Closes` は書かない)

## 最後の出力
最後は指定されたJSONスキーマに従い、以下を報告すること:
- status: 通常PRを作成できたら "success"、打ち切ってdraft PRにしたら "draft"、致命的な問題で実装を進められなかったら "failed"
- pr_url: 実際に作成したPRのURL(作成できなかった場合はnull)
- branch: 実際に使ったブランチ名
- review_round: reviewerサブエージェントを呼んだ回数
- completed_summary: 完了した内容の要約(日本語、3行程度)
- remaining_summary: 未完了の点・次にやるべきことの要約(日本語、3行程度。すべて完了していれば「なし」)
"""


# --- claude -pの実行(プロセスグループごとタイムアウト管理、4.2節) ---
def run_claude_with_timeout(prompt, timeout_seconds):
    argv = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--dangerously-skip-permissions",
        "--agents", json.dumps(REVIEWER_AGENT_DEFINITION, ensure_ascii=False),
        "--json-schema", json.dumps(TASK_RESULT_SCHEMA, ensure_ascii=False),
        "--max-budget-usd", str(MAX_BUDGET_USD_PER_TASK),
    ]
    proc = subprocess.Popen(
        argv,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        start_new_session=True,  # 新しいプロセスグループを作る
    )
    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
        return proc.returncode, stdout, stderr
    except subprocess.TimeoutExpired:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)  # 孫プロセスごと強制終了
        proc.wait()
        return None, "", "TIMEOUT"


def _retry_after_rate_limit_or_give_up(task, state, attempt, detail_text):
    """レートリミット検知時の共通処理。上限に達していなければ待機してTrueを返し
    (呼び出し側はリトライを続ける)、達していれば診断ブランチへ退避してfailedに
    更新しFalseを返す(呼び出し側はそこで打ち切る)。"""
    if attempt > MAX_RETRY_ATTEMPTS:
        branch = save_diagnostic_branch(task)
        mark_task_failed(
            task, state,
            f"レートリミットで{MAX_RETRY_ATTEMPTS}回リトライしても解消しなかった",
            diagnostic_branch=branch,
        )
        log_unexpected_error(task, state, detail_text)
        return False
    wait_seconds = backoff_seconds(attempt)
    print(f"レートリミット検知。{wait_seconds}秒待機してリトライします。({attempt}/{MAX_RETRY_ATTEMPTS})")
    time.sleep(wait_seconds)
    return True


# --- タスク単体の実行+レートリミットへのリトライ(4.3節/9.10節) ---
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

        # update_step.py はタスク実行中に別プロセスとしてstateファイルへ書き込む。
        # ここで再読み込みしないと、以降で参照するtask/stateが古いままになる。
        state = load_state()
        task = next((t for t in state["tasks"] if t["title"] == task["title"]), task)

        if stderr == "TIMEOUT":
            handle_hard_limit_exceeded(task, state)
            return

        if returncode == 0:
            # claude -pはAPIレベルのレートリミットをexit 0 + JSON封筒内のエラーとして
            # 返すことがある。stderrの文字列マッチだけでなく、こちらも見ておかないと
            # 一度で"failed"確定してしまいbackoffリトライへ入れない。
            try:
                envelope = json.loads(stdout)
            except json.JSONDecodeError:
                envelope = None

            if _envelope_is_rate_limited(envelope):
                attempt += 1
                if _retry_after_rate_limit_or_give_up(task, state, attempt, stdout):
                    continue
                return

            update_state_done(task, state, stdout)
            return

        if RATE_LIMIT_PATTERN.search(stderr):
            attempt += 1
            if _retry_after_rate_limit_or_give_up(task, state, attempt, stderr):
                continue
            return
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
    lines = [f"完了: {len(done)}件 / 失敗: {len(failed)}件 / 未着手: {len(pending)}件"]
    for t in done:
        lines.append(f"  [done] {t['title']} -> {t.get('pr_url')}")
    for t in failed:
        lines.append(f"  [failed] {t['title']} -> {t.get('failure_reason')} (診断ブランチ: {t.get('diagnostic_branch')})")
    for t in pending:
        lines.append(f"  [pending] {t['title']}")
    summary_text = "\n".join(lines)
    print(summary_text)
    try:
        summary_path = os.path.join(os.path.dirname(STATE_FILE), "summary.txt")
        with open(summary_path, "w", encoding="utf-8") as f:
            f.write(summary_text + "\n")
    except OSError:
        pass


# --- メインループ ---
def main():
    assert_sandbox_or_exit()  # 0.2節: 実行環境の安全性を最初に確認する
    os.chdir(REPO_DIR)

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
        try:
            git_cleanup_with_retry()
        except subprocess.CalledProcessError:
            notify_human(
                "git_cleanup()が繰り返し失敗したため、night_runner.pyを停止します。"
                "手動で状況を確認してください(残りのタスクは pending のまま残ります)。"
            )
            break

        run_task_with_retry(task, state)

    generate_summary(load_state())


if __name__ == "__main__":
    main()
