#!/bin/bash
# PostToolUse hook: run related test file after editing a source file
# Output is minimal on success (just pass/fail count), verbose on failure.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

cd "$(echo "$INPUT" | jq -r '.cwd')"

# Helper: run bun test and show only summary (or full output on failure)
run_bun_test() {
  local OUTPUT
  OUTPUT=$(cd forge && bun test "$@" 2>&1)
  local RC=$?
  if [ $RC -ne 0 ]; then
    echo "$OUTPUT"
  else
    # Show only the summary line (e.g. "14 pass, 0 fail")
    echo "$OUTPUT" | grep -E '^\s*\d+ pass'
  fi
  return $RC
}

# Helper: run pytest and show only summary (or full output on failure)
run_pytest() {
  local OUTPUT
  OUTPUT=$(uv run pytest "$@" 2>&1)
  local RC=$?
  if [ $RC -ne 0 ]; then
    echo "$OUTPUT"
  else
    # Show only the final summary line
    echo "$OUTPUT" | tail -1
  fi
  return $RC
}

# -------------------------------------------------------------------------
# TypeScript files (Forge)
# -------------------------------------------------------------------------

if [[ "$FILE_PATH" == *.ts && "$FILE_PATH" == *forge/* ]]; then
  BASENAME=$(basename "$FILE_PATH" .ts)

  if [[ "$FILE_PATH" == *.test.ts ]]; then
    run_bun_test "$FILE_PATH"
    exit $?
  fi

  if [[ "$BASENAME" == index || "$BASENAME" == types || "$BASENAME" == schema ]]; then
    exit 0
  fi

  TEST_FILE=""
  if [[ "$FILE_PATH" == *forge/src/routes/* ]]; then
    TEST_FILE="forge/tests/routes/${BASENAME}.test.ts"
  elif [[ "$FILE_PATH" == *forge/src/middleware/* ]]; then
    if [[ "$BASENAME" == "auth" ]]; then
      run_bun_test tests/middleware/auth.test.ts tests/middleware/auth-middleware.test.ts
      exit $?
    fi
    TEST_FILE="forge/tests/middleware/${BASENAME}.test.ts"
  elif [[ "$FILE_PATH" == *forge/src/lib/* ]]; then
    TEST_FILE="forge/tests/lib/${BASENAME}.test.ts"
  elif [[ "$FILE_PATH" == *forge/src/views/* ]]; then
    exit 0
  fi

  if [[ -n "$TEST_FILE" && -f "$TEST_FILE" ]]; then
    run_bun_test "$TEST_FILE"
    exit $?
  fi

  exit 0
fi

# -------------------------------------------------------------------------
# Python files (CLI)
# -------------------------------------------------------------------------

if [[ "$FILE_PATH" != *.py ]]; then
  exit 0
fi

BASENAME=$(basename "$FILE_PATH" .py)

if [[ "$BASENAME" == test_* ]]; then
  run_pytest "$FILE_PATH" -x -q
  exit $?
fi

if [[ "$FILE_PATH" == *cli/src/openforge/* ]]; then
  if [[ "$BASENAME" == __* || "$BASENAME" == conftest ]]; then
    exit 0
  fi

  if [[ "$FILE_PATH" == *agents/adapters/claude* ]]; then
    TEST_FILE="cli/tests/test_adapters.py"
  elif [[ "$FILE_PATH" == *agents/adapters/cursor* ]]; then
    TEST_FILE="cli/tests/test_cursor_adapter.py"
  elif [[ "$FILE_PATH" == *agents/registry* ]]; then
    TEST_FILE="cli/tests/test_agents.py"
  elif [[ "$FILE_PATH" == *agents/base* ]]; then
    TEST_FILE="cli/tests/test_agents.py"
  elif [[ "$FILE_PATH" == *providers/source_parser* ]]; then
    TEST_FILE="cli/tests/test_source_parser.py"
  elif [[ "$FILE_PATH" == *providers/github* ]]; then
    exit 0
  elif [[ -f "cli/tests/test_${BASENAME}.py" ]]; then
    TEST_FILE="cli/tests/test_${BASENAME}.py"
  else
    exit 0
  fi

  if [[ -f "$TEST_FILE" ]]; then
    run_pytest "$TEST_FILE" -x -q
  fi
fi

exit 0
