#!/usr/bin/env bash
# 发布：活副本（~/.agents/skills）→ 仓克隆 → 哈希读回校验。commit+push 由人决定。
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"
python "$REPO/tools/install.py" --source "$HOME/.agents/skills" --host-dir "$REPO" --state-dir "$REPO/.install-state" "$@"
python "$REPO/tools/install.py" --source "$HOME/.agents/skills" --host-dir "$REPO" --state-dir "$REPO/.install-state" --verify-only
echo "已同步并读回校验。发布：git add -A && git commit && git push"
