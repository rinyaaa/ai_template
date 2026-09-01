#!/bin/bash
# コンテナのエントリポイント。
# root: ファイアウォール適用 → git認証設定 → リポジトリclone/fetch → 非rootへ降格してnight_runner.pyを起動。
set -euo pipefail

: "${GH_TOKEN:?GH_TOKEN が設定されていない(GitHub操作に必須)}"
if [ -z "${ANTHROPIC_API_KEY:-}" ] && [ -z "${CLAUDE_CODE_OAUTH_TOKEN:-}" ]; then
    echo "FATAL: ANTHROPIC_API_KEY か CLAUDE_CODE_OAUTH_TOKEN のどちらかが必要(claude -pの認証に必須)" >&2
    exit 1
fi

echo "[entrypoint] applying network egress allowlist..."
/usr/local/bin/init-firewall.sh

# TODO: このテンプレートでは既定値を用意していない。派生プロジェクトでは
# night-run/run.sh 側で NIGHT_RUN_REPO_URL を自リポジトリのURLに固定してもよい。
: "${NIGHT_RUN_REPO_URL:?NIGHT_RUN_REPO_URL が設定されていない(cloneするリポジトリのURL。night-run/run.sh側で既定値を設定するか、実行時に指定する)}"
REPO_URL="$NIGHT_RUN_REPO_URL"
REPO_DIR="${NIGHT_RUN_REPO_DIR:-/workdir/repo}"
STATE_FILE_PATH="${NIGHT_RUN_STATE_FILE:-/workdir/state/night-run-state.json}"
STATE_DIR="$(dirname "$STATE_FILE_PATH")"

echo "[entrypoint] configuring GitHub credential helper..."
# GH_TOKENはgh CLIが自動的に認識するので、gitの認証もgh経由のcredential helperに委ねる。
# システム全体(/etc/gitconfig)に設定することで、あとで降格するrunnerユーザーからも使える。
git config --system credential.helper '!gh auth git-credential'
git config --system --add safe.directory "$REPO_DIR"

if [ ! -d "$REPO_DIR/.git" ]; then
    echo "[entrypoint] cloning $REPO_URL into $REPO_DIR ..."
    git clone "$REPO_URL" "$REPO_DIR"
else
    # fetchだけだとworking treeは前回終了時点のまま(前夜の古いnight_runner.py等)。
    # これから起動するpython3プロセスはファイルを起動時に一度だけ読み込むので、
    # ここでorigin/mainに合わせておかないと、night_runner.py自体の更新が
    # (git_cleanup()が後で効くとしても)このプロセスには反映されない。
    echo "[entrypoint] $REPO_DIR already exists, syncing to latest origin/main..."
    git -C "$REPO_DIR" fetch origin
    git -C "$REPO_DIR" checkout -f main
    git -C "$REPO_DIR" reset --hard origin/main
    git -C "$REPO_DIR" clean -fd
fi

mkdir -p "$STATE_DIR"

if [ ! -f "$STATE_FILE_PATH" ]; then
    echo "[entrypoint] FATAL: state file が見つからない ($STATE_FILE_PATH)。" >&2
    echo "  ヒアリングSkill(.claude/skills/night-run-hearing/)で night-run-state.json を書き出してから起動すること。" >&2
    exit 1
fi

chown -R runner:runner /workdir

# Claude Codeには--dangerously-skip-permissionsとは別に「ワークスペース信頼」の
# ゲートがあり、初回はインタラクティブな承認が要る(非対話実行だと素通りできず
# claude -pがエラーで落ちる)。/home/runnerはnamed volumeではなくコンテナ起動の
# たびに作り直されるため、毎回明示的に信頼済み扱いにしておく。
echo "[entrypoint] pre-accepting Claude Code workspace trust for $REPO_DIR..."
mkdir -p /home/runner
cat > /home/runner/.claude.json <<JSON
{"projects": {"$REPO_DIR": {"hasTrustDialogAccepted": true}}}
JSON
chown runner:runner /home/runner/.claude.json

echo "[entrypoint] starting night_runner.py as non-root user 'runner'..."
runner_env=(
    "HOME=/home/runner"
    "PATH=$PATH"
    "NIGHT_RUNNER_SANDBOX=1"
    "NIGHT_RUN_REPO_DIR=$REPO_DIR"
    "NIGHT_RUN_STATE_FILE=$STATE_FILE_PATH"
    "NIGHT_RUN_MAX_BUDGET_USD=${NIGHT_RUN_MAX_BUDGET_USD:-15}"
    "GH_TOKEN=$GH_TOKEN"
)
# ANTHROPIC_API_KEY(APIキー課金)かCLAUDE_CODE_OAUTH_TOKEN(claude setup-tokenで発行する
# サブスクリプション連携の長期トークン)のどちらかで動く。両方渡さない
# (空文字を渡すと「設定されているが空」という別の状態になり、未設定より紛らわしいため)。
[ -n "${ANTHROPIC_API_KEY:-}" ] && runner_env+=("ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY")
[ -n "${CLAUDE_CODE_OAUTH_TOKEN:-}" ] && runner_env+=("CLAUDE_CODE_OAUTH_TOKEN=$CLAUDE_CODE_OAUTH_TOKEN")

exec runuser -u runner -- env "${runner_env[@]}" python3 "$REPO_DIR/night-run/night_runner.py"
