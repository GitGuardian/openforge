#!/usr/bin/env bash
set -euo pipefail

# Verify Forge + Supabase are running before executing test command
if ! curl -sf http://localhost:3000/health >/dev/null 2>&1; then
  echo "ERROR: Forge not running. Start it first:" >&2
  echo "  cd forge && supabase start && bun run dev" >&2
  exit 1
fi

cd forge
NODE_ENV=test exec "$@"
