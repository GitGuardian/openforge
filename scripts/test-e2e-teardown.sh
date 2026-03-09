#!/usr/bin/env bash
set -euo pipefail

if [ -f /tmp/forge-e2e.pid ]; then
  PID=$(cat /tmp/forge-e2e.pid)
  if kill -0 "$PID" 2>/dev/null; then
    echo "Stopping Forge server (PID $PID)..."
    kill "$PID"
  fi
  rm -f /tmp/forge-e2e.pid
fi

echo "E2E test environment torn down."
