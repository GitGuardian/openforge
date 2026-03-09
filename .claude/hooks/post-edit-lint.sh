#!/bin/bash
# PostToolUse hook: auto-lint after Edit/Write
# Output is minimal on success, verbose on failure.

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

cd "$(echo "$INPUT" | jq -r '.cwd')"

# Python files — ruff
if [[ "$FILE_PATH" == *.py ]]; then
  LINT_OUT=$(uv run ruff check --fix "$FILE_PATH" 2>&1)
  LINT_RC=$?
  FMT_OUT=$(uv run ruff format "$FILE_PATH" 2>&1)

  # Only show output if there were lint errors
  if [ $LINT_RC -ne 0 ]; then
    echo "$LINT_OUT"
  fi
  # Only show format output if a file was changed
  if echo "$FMT_OUT" | grep -q "reformatted"; then
    echo "$FMT_OUT"
  fi
  exit $LINT_RC
fi

# TypeScript files in forge/ — typecheck
if [[ "$FILE_PATH" == *.ts && "$FILE_PATH" == *forge/* ]]; then
  OUTPUT=$(cd forge && bun run typecheck 2>&1)
  RC=$?
  if [ $RC -ne 0 ]; then
    echo "$OUTPUT"
  fi
  exit $RC
fi

exit 0
