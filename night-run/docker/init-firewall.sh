#!/bin/bash
# コンテナのネットワーク送信を default-deny にし、必要な通信先だけ許可する。
# docs/night-run-design.md 0.1節の要求(ネットワーク許可先の明示的なリスト)を満たす。
# Anthropic公式devcontainer(.devcontainer/init-firewall.sh)と同じ
# ipset+iptablesのdefault-denyパターンを踏襲し、宛先をこのプロジェクト用に調整している。
#
# root権限・NET_ADMIN/NET_RAW capabilityが必要。ホストのiptablesには影響しない
# (コンテナ自身のネットワーク名前空間に閉じる)。
set -euo pipefail

echo "[init-firewall] resolving allowed destinations..."

ipset create allowed-domains hash:net 2>/dev/null || ipset flush allowed-domains

add_domain_ips() {
    local domain="$1"
    local ips
    ips=$(dig +short "$domain" A | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' || true)
    if [ -z "$ips" ]; then
        echo "[init-firewall] WARNING: could not resolve $domain" >&2
        return
    fi
    while IFS= read -r ip; do
        [ -n "$ip" ] && ipset add allowed-domains "$ip" 2>/dev/null || true
    done <<< "$ips"
}

# 固定ドメイン。claude -p本体とClaude Codeの動作に必要な最小セット。
# TODO: 自分のプロジェクトが使うパッケージレジストリ・ビルドツールチェーンの配信元を
# ここに追加する(例: Flutterなら pub.dev / storage.googleapis.com / dl.google.com、
# Node.jsなら registry.npmjs.org、Pythonなら pypi.org / files.pythonhosted.org 等)。
# 増やす/減らすときはnight-run/README.mdのトラブルシュートも合わせて更新する。
FIXED_DOMAINS=(
    api.anthropic.com      # claude -p 本体の通信
    statsig.com             # Claude Codeのフィーチャーフラグ/テレメトリ
    sentry.io               # Claude Codeのエラー報告
)

for d in "${FIXED_DOMAINS[@]}"; do
    add_domain_ips "$d"
done

# GitHubはIPレンジが多く可変なので、meta APIからまとめて取得する(この時点ではまだ
# default-denyを適用していないので、この取得自体は素通しで通る)
echo "[init-firewall] fetching GitHub IP ranges..."
github_ranges="$(curl -sf --max-time 10 https://api.github.com/meta | python3 -c '
import json, sys
data = json.load(sys.stdin)
ranges = set()
for key in ("web", "api", "git"):
    ranges.update(data.get(key, []))
for r in sorted(ranges):
    if ":" not in r:  # IPv4のみ(このコンテナはIPv4のみを想定)
        print(r)
' || true)"

while IFS= read -r cidr; do
    [ -n "$cidr" ] && ipset add allowed-domains "$cidr" 2>/dev/null || true
done <<< "$github_ranges"

echo "[init-firewall] applying default-deny policy..."

iptables -F OUTPUT 2>/dev/null || true
iptables -F INPUT 2>/dev/null || true

# loopback
iptables -A OUTPUT -o lo -j ACCEPT
iptables -A INPUT -i lo -j ACCEPT

# 確立済み・関連する接続
iptables -A OUTPUT -m state --state ESTABLISHED,RELATED -j ACCEPT
iptables -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# DNS解決
iptables -A OUTPUT -p udp --dport 53 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 53 -j ACCEPT

# 許可リストに載っている宛先だけ許可
iptables -A OUTPUT -m set --match-set allowed-domains dst -j ACCEPT

# それ以外はデフォルトポリシーで拒否する
iptables -P OUTPUT DROP
iptables -P INPUT DROP
iptables -P FORWARD DROP

echo "[init-firewall] verifying..."
if curl -sf --max-time 5 https://example.com >/dev/null 2>&1; then
    echo "[init-firewall] FATAL: 許可していないはずの example.com にアクセスできてしまう(ファイアウォールが機能していない)" >&2
    exit 1
fi
if ! curl -sf --max-time 5 https://api.github.com >/dev/null 2>&1; then
    echo "[init-firewall] FATAL: api.github.com にアクセスできない(許可リストの設定ミス)" >&2
    exit 1
fi

echo "[init-firewall] OK"
