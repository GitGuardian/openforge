#!/bin/bash
# PostToolUse hook: run related test file after editing a source file
# Maps cli/src/openforge/<module>.py -> cli/tests/test_<module>.py
# Maps cli/tests/test_*.py -> runs that test file directly

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only process Python files
if [[ -z "$FILE_PATH" || "$FILE_PATH" != *.py ]]; then
  exit 0
fi

cd "$(echo "$INPUT" | jq -r '.cwd')"
BASENAME=$(basename "$FILE_PATH" .py)

# If editing a test file, run it directly
if [[ "$BASENAME" == test_* ]]; then
  uv run pytest "$FILE_PATH" -x -q 2>&1
  exit 0
fi

# If editing a source file under cli/src/openforge/, find matching test
if [[ "$FILE_PATH" == *cli/src/openforge/* ]]; then
  # Skip __init__, conftest, __main__
  if [[ "$BASENAME" == __* || "$BASENAME" == conftest ]]; then
    exit 0
  fi

  # Handle submodule paths: agents/registry.py -> test_agents.py
  # Handle adapters: agents/adapters/claude.py -> test_adapters.py
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
    # No dedicated test file yet, skip
    exit 0
  elif [[ -f "cli/tests/test_${BASENAME}.py" ]]; then
    TEST_FILE="cli/tests/test_${BASENAME}.py"
  else
    exit 0
  fi

  if [[ -f "$TEST_FILE" ]]; then
    uv run pytest "$TEST_FILE" -x -q 2>&1
  fi
fi

exit 0
