#!/usr/bin/env bash
# Sequential isolation (NOT bisection): run tests one-by-one in order and stop at
# the first test after which the pollution target exists.
# Multiple polluters: this finds the first in execution order — fix it, clean the
# target, and re-run to find the next.
#
# Usage: ./isolate-polluter.sh <file_or_dir_to_check> <test_pattern>
# Env:   TEST_RUNNER - command used to run one test file (default: "npm test")
# Note:  the target must NOT exist before the run; this script fails closed.

set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <file_to_check> <test_pattern>"
  echo "Example: $0 'tmp-output.log' 'src/**/*.test.ts'"
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"
TEST_RUNNER="${TEST_RUNNER:-npm test}"

# Reserved device names (Windows) can never be real files — checking them is meaningless.
case "${POLLUTION_CHECK^^}" in
  NUL|CON|PRN|AUX|COM[1-9]|LPT[1-9])
    echo "ERROR: '$POLLUTION_CHECK' is a reserved device name - cannot be a pollution target"
    exit 2
    ;;
esac

# Fail-closed: without a working test runner every result would be a false "clean".
RUNNER_BIN="${TEST_RUNNER%% *}"
command -v "$RUNNER_BIN" >/dev/null 2>&1 || { echo "ERROR: runner '$RUNNER_BIN' not found - refusing to report clean (false negative)"; exit 2; }

echo "Isolating test that creates: $POLLUTION_CHECK"
echo "Test pattern: $TEST_PATTERN"
echo "Runner: $TEST_RUNNER"
echo ""

# Get list of test files
TEST_FILES=$(find . -path "$TEST_PATTERN" | sort)

if [ -z "$TEST_FILES" ]; then
  echo "ERROR: no test files matched pattern - refusing to report clean (false negative)"
  exit 2
fi

TOTAL=$(printf '%s\n' "$TEST_FILES" | wc -l | tr -d ' ')

echo "Found $TOTAL test files"
echo ""

# Pre-existing pollution makes isolation impossible and would be reported as "clean" — fail closed.
if [ -e "$POLLUTION_CHECK" ]; then
  echo "ERROR: $POLLUTION_CHECK already exists before any test ran - cannot isolate; remove it first"
  exit 2
fi

COUNT=0
RUN_ERRORS=0
while IFS= read -r TEST_FILE; do
  COUNT=$((COUNT + 1))

  echo "[$COUNT/$TOTAL] Testing: $TEST_FILE"

  # A failing test may still pollute, so we run regardless; but an errored run proves
  # nothing. Count errors and report at the end so infra failure can't fake a green.
  # (Intentional unquoted $TEST_RUNNER: allows values like "npm test".)
  if ! $TEST_RUNNER "$TEST_FILE" > /dev/null 2>&1; then
    RUN_ERRORS=$((RUN_ERRORS + 1))
  fi

  # Check if pollution appeared
  if [ -e "$POLLUTION_CHECK" ]; then
    echo ""
    echo "FOUND POLLUTER!"
    echo "   Test: $TEST_FILE"
    echo "   Created: $POLLUTION_CHECK"
    echo ""
    echo "Pollution details:"
    ls -la "$POLLUTION_CHECK"
    echo ""
    echo "To investigate:"
    echo "  $TEST_RUNNER $TEST_FILE    # Run just this test"
    echo "  cat $TEST_FILE             # Review test code"
    echo ""
    echo "If more pollution remains after fixing: clean the target and re-run to find the next polluter."
    exit 1
  fi
done <<< "$TEST_FILES"

echo ""
if [ "$RUN_ERRORS" -gt 0 ]; then
  echo "WARNING: $RUN_ERRORS of $TOTAL test run(s) errored - 'clean' result may be a false negative"
  exit 2
fi
echo "No polluter found - all tests clean!"
exit 0
