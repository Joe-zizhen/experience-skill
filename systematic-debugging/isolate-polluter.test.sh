#!/usr/bin/env bash
# Tests for isolate-polluter.sh. Each case builds a temp workspace with fake tests.
set -u

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SCRIPT="$SCRIPT_DIR/isolate-polluter.sh"
PASS=0
FAIL=0

check() { # <name> <expected_exit> <actual_exit>
  if [ "$2" -eq "$3" ]; then
    PASS=$((PASS + 1)); echo "ok   - $1"
  else
    FAIL=$((FAIL + 1)); echo "FAIL - $1 (want exit $2, got $3)"
  fi
}

make_workspace() {
  local dir
  dir=$(mktemp -d)
  ( cd "$dir" && touch a.test.sh b.test.sh )
  printf '%s\n' "$dir"
}

# fake runner: succeeds; creates 'pollution.out' when the test file name contains 'b.test'
make_polluting_runner() {
  cat > "$1/run.sh" <<'EOF'
#!/usr/bin/env bash
case "$1" in *b.test*) : > pollution.out ;; esac
exit 0
EOF
  chmod +x "$1/run.sh"
}

make_clean_runner() {
  printf '#!/usr/bin/env bash\nexit 0\n' > "$1/clean.sh"
  chmod +x "$1/clean.sh"
}

# 1. polluter present -> exit 1
W=$(make_workspace); make_polluting_runner "$W"
( cd "$W" && TEST_RUNNER="./run.sh" "$SCRIPT" pollution.out '*.test.sh' >/dev/null 2>&1 )
check "finds polluter" 1 $?

# 2. no pollution -> exit 0
W=$(make_workspace); make_clean_runner "$W"
( cd "$W" && TEST_RUNNER="./clean.sh" "$SCRIPT" pollution.out '*.test.sh' >/dev/null 2>&1 )
check "clean suite" 0 $?

# 3. pre-existing pollution -> exit 2 (fail closed)
W=$(make_workspace); make_clean_runner "$W"; : > "$W/pollution.out"
( cd "$W" && TEST_RUNNER="./clean.sh" "$SCRIPT" pollution.out '*.test.sh' >/dev/null 2>&1 )
check "pre-existing pollution fails closed" 2 $?

# 4. runner missing -> exit 2
W=$(make_workspace)
( cd "$W" && TEST_RUNNER="./no-such-runner" "$SCRIPT" pollution.out '*.test.sh' >/dev/null 2>&1 )
check "missing runner fails closed" 2 $?

# 5. no test files -> exit 2
W=$(mktemp -d); make_clean_runner "$W"
( cd "$W" && TEST_RUNNER="./clean.sh" "$SCRIPT" pollution.out '*.test.sh' >/dev/null 2>&1 )
check "no matching tests fails closed" 2 $?

echo ""
echo "pass=$PASS fail=$FAIL"
[ "$FAIL" -eq 0 ]
