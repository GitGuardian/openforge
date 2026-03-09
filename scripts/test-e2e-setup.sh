#!/usr/bin/env bash
set -euo pipefail

# Verify Supabase is running
if ! supabase status --workdir forge 2>/dev/null | grep -q "API URL"; then
  echo "ERROR: Local Supabase not running. Run: cd forge && supabase start"
  exit 1
fi

# Get Supabase credentials from status output
SUPABASE_URL=$(supabase status --workdir forge 2>/dev/null | grep "API URL" | awk '{print $NF}')
ANON_KEY=$(supabase status --workdir forge 2>/dev/null | grep "anon key" | awk '{print $NF}')
SERVICE_ROLE_KEY=$(supabase status --workdir forge 2>/dev/null | grep "service_role key" | awk '{print $NF}')
DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"

export SUPABASE_URL ANON_KEY SERVICE_ROLE_KEY DB_URL

# Start Forge server in background if not already running
if ! curl -sf http://localhost:3000/health > /dev/null 2>&1; then
  echo "Starting Forge server..."
  cd forge
  DATABASE_URL="$DB_URL" \
  SUPABASE_URL="$SUPABASE_URL" \
  SUPABASE_ANON_KEY="$ANON_KEY" \
  SUPABASE_SERVICE_ROLE_KEY="$SERVICE_ROLE_KEY" \
  OPENFORGE_MODE=public \
  bun run start &
  FORGE_PID=$!
  echo "$FORGE_PID" > /tmp/forge-e2e.pid
  cd ..

  # Wait for health check
  for i in $(seq 1 30); do
    if curl -sf http://localhost:3000/health > /dev/null 2>&1; then
      echo "Forge server ready on port 3000 (PID $FORGE_PID)"
      break
    fi
    if [ "$i" -eq 30 ]; then
      echo "ERROR: Forge server failed to start within 30s"
      kill "$FORGE_PID" 2>/dev/null || true
      exit 1
    fi
    sleep 1
  done
else
  echo "Forge server already running on port 3000"
fi

echo "E2E test environment ready."
echo "  FORGE_URL=http://localhost:3000"
echo "  SUPABASE_URL=$SUPABASE_URL"
