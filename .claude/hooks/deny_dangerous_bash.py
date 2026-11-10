#!/usr/bin/env python3
"""PreToolUse hook: 破壊的なBashコマンドと秘密情報の読み取りをブロックする。

settings.json の permissions.deny は前方一致なので、フラグ後置の変種や
ラッパー経由（bash -c, env, timeout 等）の実行を検出できない。このhookは
コマンドをトークン単位で解析し、表現の変種に関係なく危険な操作をブロックする。

これはブロックリスト方式であり、シェルの全表現を列挙することは原理的に
できない。**第一関門であって最後の砦ではない**（最後の砦はCI・レビュー層）。
検出パターンを変更したら test_deny_dangerous_bash.py を必ず更新・実行すること。

標準ライブラリのみ使用。python3 がPATHに必要。入力が解釈できない場合は
ブロックしない（フェイルオープン）。

Claude Code / Codex / Cursor の3つから呼ばれる（--provider で入出力の形式を切り替える）。
  Claude: .claude/settings.json の PreToolUse。exit 2 + stderr で拒否
  Codex : .codex/hooks.json の PreToolUse。permissionDecision: deny のJSONで拒否
  Cursor: .cursor/hooks.json の beforeShellExecution / beforeReadFile（--event read）。
          permission: deny のJSONで拒否
"""
import json
import re
import sys

# コマンド名の前に付いても実体を変えないラッパー類（剥がして中身を検査する）
WRAPPERS = {
    "sudo", "doas", "env", "command", "builtin", "exec",
    "nohup", "nice", "time", "stdbuf", "timeout", "xargs",
}
# `-c` で文字列をコマンドとして実行するシェル
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}

# 秘密情報ファイルのパスパターン（Readツールのdenyと対になるBash側の検査）
SECRET_PATH = re.compile(
    r"(^|/)\.env(\.[\w.-]+)?$"          # .env, .env.production 等
    r"|(^|/)id_(rsa|dsa|ecdsa|ed25519)$"  # 秘密鍵（.pubは公開鍵なので対象外）
    r"|\.pem$"
    r"|(^|/)\.ssh(/|$)"
    r"|(^|/)\.aws(/|$)"
)
# 雛形ファイルは読んでよい（cp .env.example .env のような正当な操作を通す）
SECRET_OK = re.compile(r"\.env\.(example|sample|template|dist)$")

# 内容の読み取りに使われるコマンド（全引数が読み取り元）
READ_CMDS = {
    "cat", "head", "tail", "less", "more", "nl", "tac",
    "grep", "egrep", "fgrep", "rg", "ag",
    "awk", "sed", "cut", "sort", "uniq", "strings", "diff",
    "xxd", "od", "hexdump", "base64",
}
# 複製・転送コマンド（最後の位置引数は書き込み先なので読み取り検査から除外）。
# 「cp .env.example .env」は雛形→本物のセットアップなので通り、
# 「cp .env /tmp/backup」は本物の.envを読むのでブロックされる。
COPY_CMDS = {"cp", "scp", "rsync", "install"}


def flag_letters(tokens):
    """`-rf` や `-r -f` のような短縮フラグの文字集合（小文字化）を返す。"""
    letters = set()
    for t in tokens:
        if re.fullmatch(r"-[a-zA-Z]+", t):
            letters.update(t[1:].lower())
    return letters


def normalize_tokens(tokens):
    """先頭の環境変数代入（FOO=1 git ...）を除去し、コマンド名を
    引用符・バックスラッシュ・パス指定（/usr/bin/git 等）から正規化する。"""
    while tokens and re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=\S*", tokens[0]):
        tokens = tokens[1:]
    if not tokens:
        return tokens
    cmd = tokens[0].strip("\"'").lstrip("\\").rsplit("/", 1)[-1]
    return [cmd] + tokens[1:]


def strip_wrappers(tokens):
    """sudo/env/timeout等のラッパーを剥がし、実体のコマンドに到達する。"""
    tokens = normalize_tokens(tokens)
    while tokens and tokens[0] in WRAPPERS:
        tokens = normalize_tokens(tokens[1:])
        # ラッパー自身のオプションや timeout の持続時間（5s, 1m, 2.5h 等の
        # 単位付き書式を含む）を読み飛ばす
        while tokens and (
            tokens[0].startswith("-")
            or re.fullmatch(r"\d+(\.\d+)?[smhd]?", tokens[0])
        ):
            tokens = tokens[1:]
        tokens = normalize_tokens(tokens)
    return tokens


def git_subcommand(rest):
    """gitのグローバルオプション（-C <dir>, -c <kv> 等）を読み飛ばして
    サブコマンドを返す。引数中の単語（コミットメッセージ等）に反応しない。"""
    i = 0
    while i < len(rest):
        t = rest[i]
        if t in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            i += 2
            continue
        if t.startswith("-"):
            i += 1
            continue
        return t, rest[i + 1:]
    return None, []


def has_opt(rest, regex):
    """曖昧でない長オプション略記・拡張（getoptが受理する `--hard` に対する
    `--ha`, `--force` に対する `--force-with-lease` 等）にマッチするトークンが
    あるか。regexはフルマッチで評価する。"""
    return any(re.fullmatch(regex, t.split("=", 1)[0]) for t in rest)


# リダイレクト演算子（2>/dev/null, >>out, <in, 2>&1, &> 等）の先頭パターン
REDIRECT = re.compile(r"\d*>>?|\d*>&\d*|&>>?|<<?")


def positional_args(tokens):
    """フラグでもリダイレクトでもない位置引数だけを返す。
    `cp a b 2>/dev/null` の 2>/dev/null や、`> file` のfileを除外する。"""
    args, skip_next = [], False
    for t in tokens:
        if skip_next:
            skip_next = False
            continue
        if t.startswith("-"):
            continue
        m = REDIRECT.match(t)
        if m:
            # 演算子だけのトークン（`> file` の `>`）は次トークンがリダイレクト先
            if m.group(0) == t and t[-1] in "<>":
                skip_next = True
            continue
        args.append(t)
    return args


HOOKS_PATH_OK = (".githooks", "./.githooks")


def hooks_path_ok(sub, after):
    """core.hooksPath に触れる git コマンドのうち、許すもの（読む・.githooks にする）か。"""
    if sub != "config":
        return False  # -c / --config-env で他のサブコマンドに一時的に効かせる形
    if any(t in ("--unset", "--unset-all", "--remove-section", "--rename-section", "--replace-all", "--edit", "-e")
           for t in after):
        return False
    words = [t for t in after if not t.startswith("-")]
    if words and words[0] in ("unset", "remove-section", "rename-section", "edit"):
        return False
    if words and words[0] in ("get", "set"):
        words = words[1:]
    if not words or words[0].lower() != "core.hookspath":
        return False  # core.hooksPath=... のような値つきの書き方、別のキーとの組み合わせ
    values = words[1:]
    return not values or (len(values) == 1 and values[0] in HOOKS_PATH_OK)


# 環境変数で git の設定を差し替える形（GIT_CONFIG_KEY_0=core.hooksPath / GIT_CONFIG_PARAMETERS）
ENV_HOOKS_PATH = re.compile(r"GIT_CONFIG_(?:KEY_\d+|PARAMETERS)=\S*core\.hookspath", re.I)


def check_segment(segment):
    """パイプ・連結で区切られた1コマンド分を検査。ブロック理由 or None を返す。"""
    tokens = strip_wrappers(segment.split())
    if not tokens:
        return None

    cmd = tokens[0]
    rest = [t.strip("\"'") for t in tokens[1:]]

    if ENV_HOOKS_PATH.search(segment):
        return "環境変数で core.hooksPath を差し替えると、コミット前の検査が効かなくなるためブロックしています。"

    # シェル経由（bash -c "..."）や eval は、引用符の中身を取り出して再帰検査する。
    # -c は -lc / -xc のように他フラグと束ねられるので、束ねフラグも拾う
    shell_c = any(re.fullmatch(r"-[a-zA-Z]*c[a-zA-Z]*", t) for t in rest)
    if (cmd in SHELLS and shell_c) or cmd == "eval":
        for m in re.finditer(r"\"([^\"]*)\"|'([^']*)'", segment):
            reason = check_command(m.group(1) or m.group(2) or "")
            if reason:
                return reason
        if cmd == "eval":
            reason = check_command(" ".join(rest))
            if reason:
                return reason

    if cmd == "rm":
        letters = flag_letters(rest)
        long_flags = set(t for t in rest if t.startswith("--"))
        recursive = "r" in letters or "--recursive" in long_flags
        force = "f" in letters or "--force" in long_flags
        if recursive and force:
            return "rm の再帰強制削除は取り返しがつかないためブロックしています。個別のファイル削除か、ゴミ箱に相当する移動（mv）を使ってください。"

    if cmd == "find" and "-delete" in rest:
        return "find -delete は一括削除で取り返しがつかないためブロックしています。対象を確認しながら個別に削除してください。"
    if cmd == "find":
        for opt in ("-exec", "-execdir", "-ok", "-okdir"):
            if opt in rest:
                reason = check_segment(" ".join(rest[rest.index(opt) + 1:]))
                if reason:
                    return reason

    if cmd == "git":
        sub, after = git_subcommand(rest)
        # コミット前の検査（.githooks/pre-commit・秘密情報の検査）を飛ばす操作。
        # AGENTS.md 安全ルール6。-c で hooksPath を差し替える・設定を外すのも同じ扱い。
        # core.hooksPath に触れる git コマンドは、「今の値を読む」「.githooks にする」以外すべて止める
        # （-c / --config-env での一時的な差し替え、config set/unset、--unset 等の変種を個別に追わない）。
        if any("core.hookspath" in t.lower() for t in rest) and not hooks_path_ok(sub, after):
            return "core.hooksPath を差し替える・外す・.githooks 以外にすると、コミット前の検査（秘密情報・不可視文字・安全網の整合性）が効かなくなるためブロックしています。検査が失敗したなら、原因を直してからコミットしてください。"
        if sub in ("commit", "push", "merge", "am", "cherry-pick", "rebase") and has_opt(rest, r"--no-ver(i(f(y)?)?)?"):
            return "--no-verify はコミット前の検査（秘密情報・不可視文字・安全網の整合性）を飛ばすためブロックしています。検査が失敗したなら、原因を直してからやり直してください。"
        if sub == "commit" and any(re.fullmatch(r"-[A-Za-z]*n[A-Za-z]*", t) for t in after):
            return "git commit -n は --no-verify と同じ意味のためブロックしています。検査が失敗したなら、原因を直してからコミットしてください。"
        # 長オプションはgetoptが曖昧でない略記を受理するため、正式表記だけでなく
        # 略記（--force→--for, --hard→--ha, --delete→--del）も拾う。
        if sub == "push":
            # -f / 束ねた -fv・-vf 等 / --for / --forc / --force / --force-with-lease
            if any(re.fullmatch(r"-[A-Za-z]*f[A-Za-z]*", t) for t in rest) or has_opt(
                rest, r"--for(c(e.*)?)?"
            ):
                return "force push はリモートの履歴を書き換えるためブロックしています。取り消しは git revert で行ってください（safe-rollback スキル参照）。"
            # refspecの `+` プレフィックス（git push origin +main）も強制pushになる
            if any(t.startswith("+") for t in after if not t.startswith("-")):
                return "refspecの + プレフィックスは force push と同じ意味のためブロックしています。取り消しは git revert で行ってください。"
        if sub == "reset" and has_opt(rest, r"--har?d?"):  # --ha / --har / --hard
            return "git reset --hard は作業内容を完全に消すためブロックしています。復旧は safe-rollback スキルの手順（退避→revert）で行ってください。"
        if sub == "clean":
            return "git clean は未追跡ファイルを削除するためブロックしています。不要ファイルは個別に削除してください。"
        if sub == "branch":
            has_big_d = any(re.fullmatch(r"-[A-Za-z]*D[A-Za-z]*", t) for t in rest)
            has_delete = has_opt(rest, r"--d(e(l(e(t(e)?)?)?)?)?") or any(
                re.fullmatch(r"-[A-Za-z]*d[A-Za-z]*", t) for t in rest
            )
            has_force = has_opt(rest, r"--for(c(e.*)?)?") or any(
                re.fullmatch(r"-[A-Za-z]*f[A-Za-z]*", t) for t in rest
            )
            if has_big_d or (has_delete and has_force):
                return "ブランチの強制削除（-D）は未マージの作業を失うためブロックしています。マージ済みなら -d を使ってください。"
        if sub == "stash":
            for t in after:
                if t.startswith("-"):
                    continue
                if t in ("clear", "drop"):
                    return "git stash の clear/drop は退避した作業を消すためブロックしています。stashは残したままにしてください（safe-rollback スキル参照）。"
                break
        if sub == "worktree":
            for t in after:
                if t.startswith("-"):
                    continue
                if t in ("remove", "prune"):
                    return "git worktree の remove/prune はワークツリーのファイルを実際に削除するためブロックしています。不要になったワークツリーは削除対象を列挙して人間に削除を依頼してください（parallel-worktree スキル参照）。"
                break

    # 秘密情報ファイルの読み取り・複製（Readツールのdenyと対になる検査）。
    # 免除（.env.example 等の雛形）は引数ごとに個別判定する——
    # 「cat .env.example .env」のように雛形と本物を並べても本物を捕捉するため。
    if cmd in READ_CMDS or cmd in COPY_CMDS:
        sources = positional_args(rest)
        # 複製系は最後の位置引数が書き込み先なので、読み取り元から除く。
        # ただし -t/--target-directory（略記 --targ, --t 等も含む）で書き込み先を
        # フラグ指定した場合は位置引数が全てソースになるため、末尾除外をしない。
        def is_target_flag(t):
            base = t.split("=", 1)[0]
            return base == "-t" or (
                base.startswith("--t") and "--target-directory".startswith(base)
            )

        target_flag = any(is_target_flag(t) for t in rest)
        if cmd in COPY_CMDS and sources and not target_flag:
            sources = sources[:-1]
        for t in sources:
            if SECRET_OK.search(t):
                continue
            if SECRET_PATH.search(t):
                return "秘密情報ファイル（.env・秘密鍵・~/.ssh等）の読み取り・コピーはブロックしています。設定値が必要なときは、値そのものではなくキー名をユーザーに確認してください。"

    return None


def check_command(command):
    """コマンド文字列全体を検査する（シェル経由の再帰の入口にもなる）。"""
    # パイプ・;・&&・||・サブシェル・コマンド置換（$()と``）・改行の区切りごとに検査
    for segment in re.split(r"[|;&()`\n\r]+", command):
        reason = check_segment(segment)
        if reason:
            return reason
    return None


def respond(provider, reason):
    """ツールごとの「拒否」の伝え方に合わせて (stdout, stderr, exit code) を返す。"""
    if provider == "cursor":
        if reason:
            return json.dumps({"permission": "deny", "user_message": reason, "agent_message": reason},
                              ensure_ascii=False), "", 0
        return "{}", "", 0
    if provider == "codex":
        if reason:
            return json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                                      "permissionDecision": "deny",
                                                      "permissionDecisionReason": reason}},
                              ensure_ascii=False), "", 0
        return "", "", 0
    # Claude Code: exit 2 で拒否し、stderr が Claude に伝わる
    return "", (reason or ""), (2 if reason else 0)


def extract(provider, data, event):
    """入力から検査対象を取り出す。(種類, 値) か None。"""
    if provider == "cursor":
        if event == "read":
            return "read", data.get("file_path") or ""
        return "shell", data.get("command") or ""
    if data.get("tool_name") not in ("Bash", "shell", "exec_command", None):
        return None
    tool_input = data.get("tool_input") or {}
    command = tool_input.get("command", "")
    if isinstance(command, list):  # Codex は argv の配列で渡すことがある
        command = " ".join(str(c) for c in command)
    return "shell", command or ""


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--provider", choices=("claude", "codex", "cursor"), default="claude")
    ap.add_argument("--event", choices=("shell", "read"), default="shell")
    args = ap.parse_args(argv)
    try:
        data = json.load(sys.stdin)
        if not isinstance(data, dict):
            raise ValueError
    except Exception:
        data = None  # 入力が読めない場合はブロックしない（フェイルオープン）

    reason = None
    target = extract(args.provider, data, args.event) if data is not None else None
    if target and target[0] == "shell":
        reason = check_command(target[1])
    elif target and target[0] == "read":
        path = target[1]
        if SECRET_PATH.search(path) and not SECRET_OK.search(path):
            reason = f"秘密情報のファイル（{path}）は読まない（AGENTS.md 安全ルール2）"
    out, err, code = respond(args.provider, reason)
    if out:
        print(out)
    if err:
        print(err, file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
