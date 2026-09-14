#!/usr/bin/env bash
# 发布：活副本（~/.agents/skills）→ 仓克隆 → 哈希读回校验。commit+push 由人决定。
# 默认拒绝：会用活副本覆盖本仓。仓库比活副本新时会丢改动。
set -e
REPO="$(cd "$(dirname "$0")/.." && pwd)"

if [ "${1:-}" != "--from-live" ]; then
  echo "ABORT: publish.sh 会用 ~/.agents/skills 覆盖本仓。"
  echo "仓库里有活副本没有的改动时，这样会丢。"
  echo "先把本仓装进活副本："
  echo "  python \"$REPO/tools/install.py\" --source \"$REPO\" --host-dir \"\$HOME/.agents/skills\""
  echo "确认要把活副本拍进本仓时："
  echo "  bash tools/publish.sh --from-live"
  exit 1
fi
shift

python - "$REPO" <<'PY'
import os, re, sys
repo = sys.argv[1]
host = os.path.join(os.path.expanduser("~"), ".agents", "skills")
t = open(os.path.join(repo, "tools", "install.py"), encoding="utf-8").read()
m = re.search(r"ALL_SKILLS = \[([^\]]+)\]", t)
if not m:
    print("ABORT: 读不到 tools/install.py 的 ALL_SKILLS")
    sys.exit(1)
skills = [x.strip().strip("\"'") for x in m.group(1).split(",") if x.strip().strip("\"'")]
miss = [s for s in skills if os.path.isdir(os.path.join(repo, s)) and not os.path.isdir(os.path.join(host, s))]
if miss:
    print("ABORT: 活副本缺: " + ", ".join(miss))
    print("先: python tools/install.py --source %s --host-dir %s" % (repo, host))
    sys.exit(1)
PY

python "$REPO/tools/install.py" --source "$HOME/.agents/skills" --host-dir "$REPO" --state-dir "$REPO/.install-state" "$@"
python "$REPO/tools/install.py" --source "$HOME/.agents/skills" --host-dir "$REPO" --state-dir "$REPO/.install-state" --verify-only
echo "已同步并读回校验。发布：git add -A && git commit && git push"
