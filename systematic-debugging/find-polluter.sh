#!/usr/bin/env bash
# Bisection script to find which test creates unwanted files/state
# Usage: ./find-polluter.sh <file_or_dir_to_check> <test_pattern>
# Example: ./find-polluter.sh '.git' 'src/**/*.test.ts'

set -e

if [ $# -ne 2 ]; then
  echo "Usage: $0 <file_to_check> <test_pattern>"
  echo "Example: $0 '.git' 'src/**/*.test.ts'"
  exit 1
fi

POLLUTION_CHECK="$1"
TEST_PATTERN="$2"

# Fail-closed: without a working test runner every result would be a false "clean".
command -v npm >/dev/null 2>&1 || { echo "ERROR: npm not found - refusing to report clean (false negative)"; exit 2; }

echo "Searching for test that creates: $POLLUTION_CHECK"
echo "Test pattern: $TEST_PATTERN"
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

COUNT=0
RUN_ERRORS=0
while IFS= read -r TEST_FILE; do
  COUNT=$((COUNT + 1))

  # Skip if pollution already exists
  if [ -e "$POLLUTION_CHECK" ]; then
    echo "WARNING: Pollution already exists before test $COUNT/$TOTAL"
    echo "   Skipping: $TEST_FILE"
    continue
  fi

  echo "[$COUNT/$TOTAL] Testing: $TEST_FILE"

  # A failing test may still pollute, so we run regardless; but an errored run proves
  # nothing. Count errors and report at the end so infra failure can't fake a green.
  if ! npm test "$TEST_FILE" > /dev/null 2>&1; then
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
    echo "  npm test $TEST_FILE    # Run just this test"
    echo "  cat $TEST_FILE         # Review test code"
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
