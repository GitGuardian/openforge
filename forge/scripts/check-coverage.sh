#!/bin/bash
# Run Forge tests with coverage and fail if line coverage drops below threshold.
# Usage: bash forge/scripts/check-coverage.sh [threshold]
# Default threshold: 90
# Output: minimal on success, full on failure.

THRESHOLD="${1:-90}"
cd "$(dirname "$0")/.." || exit 1

OUTPUT=$(bun test --coverage tests/routes/ tests/middleware/ tests/lib/ 2>&1)
EXIT_CODE=$?

# If tests failed, show full output
if [ $EXIT_CODE -ne 0 ]; then
  echo "$OUTPUT"
  exit $EXIT_CODE
fi

# Extract summary and coverage
SUMMARY=$(echo "$OUTPUT" | grep -E '^\s*\d+ pass')
COVERAGE=$(echo "$OUTPUT" | grep "All files" | awk -F'|' '{gsub(/[[:space:]]/, "", $3); print $3}')

if [ -z "$COVERAGE" ]; then
  echo "$SUMMARY"
  echo "WARNING: Could not parse coverage"
  exit 0
fi

COV_INT=${COVERAGE%.*}

if [ "$COV_INT" -lt "$THRESHOLD" ]; then
  # Show full coverage table on failure
  echo "$OUTPUT" | grep -E '^\s*(File|All files|src/|tests/|---)'
  echo ""
  echo "FAIL: Coverage ${COVERAGE}% < ${THRESHOLD}%"
  exit 1
else
  echo "${SUMMARY} | coverage: ${COVERAGE}%"
fi
