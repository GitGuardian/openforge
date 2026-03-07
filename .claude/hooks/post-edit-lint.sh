#!/bin/bash
# PostToolUse hook: auto-lint after Edit/Write
# Python files: ruff check + format
# TypeScript files: tsc typecheck

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

if [[ -z "$FILE_PATH" ]]; then
  exit 0
fi

cd "$(echo "$INPUT" | jq -r '.cwd')"

# Python files — ruff
if [[ "$FILE_PATH" == *.py ]]; then
  uv run ruff check --fix "$FILE_PATH" 2>&1
  uv run ruff format "$FILE_PATH" 2>&1
  exit 0
fi

# TypeScript files in forge/ — typecheck
if [[ "$FILE_PATH" == *.ts && "$FILE_PATH" == *forge/* ]]; then
  cd forge && bun run typecheck 2>&1
  exit 0
fi

exit 0
