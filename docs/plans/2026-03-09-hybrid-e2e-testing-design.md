# Hybrid E2E Testing Design

**Date:** 2026-03-09
**Status:** Approved

## Overview

Three-tier testing pyramid for both Forge and CLI. Shared local Forge+Supabase instance for mid-tier and Playwright tests. CI target: under 60s total.

**Approach:** Shared test server (Approach A). One local Forge+Supabase instance started once, used by all integration and e2e tests. Tests manage their own data via API setup/teardown.

## Forge Testing Pyramid

### Tier 1 — Unit (existing, `bun test`)

- 241 tests, mocked DB/auth via `app.request()`
- Stays as-is, no changes
- ~10-15s

### Tier 2 — Integration (new, `bun test` with `fetch()`)

- ~15-20 tests in `forge/tests/integration/`
- Hit real running Forge at `http://localhost:3000` backed by real Supabase
- Real DB, real auth cookies, real HTMX partial responses
- Test data created via API in `beforeAll()`, cleaned up in `afterAll()`

**Flows:**
- Auth: signup → login → session cookie → authenticated page access
- Catalogue: `GET /` returns real plugin list from DB
- Plugin detail: `GET /plugins/:id` with real data
- Voting: `POST /plugins/:id/vote` returns HTMX partial with updated count
- Comments: `POST /plugins/:id/comments` returns HTMX partial with new comment
- Submissions: `POST /submissions` creates real submission in DB → `GET /my/submissions` shows it
- Curator flow: `POST /submissions/:id/review` with approve/reject → status changes in DB
- Search: `GET /?q=term` returns filtered results
- HTMX partials: verify `HX-Request` header triggers partial (not full page) responses
- API endpoints: `GET /api/marketplace.json`, `GET /.well-known/skills/index.json` return real data
- ~5-10s

### Tier 3 — Browser E2E (new, Playwright via Node.js)

- 5-8 tests in `forge/e2e/`
- Run via `npx playwright test` (Node.js, NOT Bun)
- Same Forge+Supabase instance as tier 2

**Tests (require real browser DOM):**
1. Full browse → click plugin → detail page renders correctly
2. Login → session persists across navigation
3. Vote click → HTMX swaps count in-place (no page reload)
4. Comment form → submit → comment appears via HTMX swap
5. Submit plugin form → validation → success redirect
6. Curator approve → inline status update via HTMX
7. Search → results update via HTMX partial swap

**Config:**
- API-based setup: seed test data via `fetch()` in `beforeAll()`
- `playwright.config.ts` with `baseURL`, `reuseExistingServer: true`, headless chromium
- ~30-40s (4 workers)

## CLI Testing Pyramid

### Tier 1 — Unit (existing, pytest)

- 298 tests, mocked everything via `unittest.mock.patch`
- Stays as-is, no changes
- ~0.66s

### Tier 2 — HTTP Transport (new, respx)

- ~10-15 tests in `cli/tests/integration/`
- Replace patch-based mocking with `respx` route-level HTTP mocking
- Tests `ForgeClient` methods against realistic HTTP responses at the transport layer
- Catches URL path bugs, header bugs, request body format issues that `patch` misses

**Flows:**
- `ForgeClient.search()` — correct URL, query params, response parsing
- `ForgeClient.submit()` — correct POST body, auth header, error handling
- Auth `_sign_in_with_password` — correct GoTrue endpoint, token parsing, error codes
- `_get_forge_url()` config precedence
- ~1-2s

### Tier 3 — Subprocess Smoke Tests (new, pytest)

- 5-7 tests in `cli/tests/e2e/`
- Run `openforge` as a real subprocess via `subprocess.run()`

**Tests:**
1. `openforge --help` exits 0, shows usage
2. `openforge --version` shows version string
3. `openforge add <local-fixture-repo>` → installs → lock file written
4. `openforge list` after add → shows installed plugin
5. `openforge remove <name>` → uninstalls → lock updated
6. `openforge auth status` when not logged in → graceful error message
7. `openforge find <term>` against mock server → shows results
- ~3-5s

## Test Infrastructure

### Server setup script (`scripts/test-e2e-setup.sh`)

- Verifies local Supabase is running (`supabase status`)
- Starts Forge dev server (`bun run dev` or builds and serves)
- Waits for health check (`GET /health`)
- Exports `FORGE_URL=http://localhost:3000`

### Test data management

- Each integration/e2e test suite creates its own test user + seed data in `beforeAll()`
- Uses unique prefixes (e.g., `test-<timestamp>-`) to avoid collisions
- Cleans up in `afterAll()`

### CI pipeline (two parallel jobs)

```
Job 1: Unit tests (~15s)          Job 2: E2E tests (~45s)
├── bun test (forge unit)          ├── Start Supabase + Forge
├── pytest (cli unit)              ├── bun test forge/tests/integration/
└── typecheck + lint               ├── npx playwright test forge/e2e/
                                   ├── pytest cli/tests/integration/
                                   └── pytest cli/tests/e2e/
```

**Total CI: ~45s** (jobs run in parallel, job 2 is the bottleneck)

## File Structure

```
forge/
  tests/                    # existing unit tests (tier 1)
  tests/integration/        # new HTTP integration tests (tier 2)
  e2e/                      # new Playwright tests (tier 3)
  playwright.config.ts      # Playwright config (Node.js)

cli/
  tests/                    # existing unit tests (tier 1)
  tests/integration/        # new respx HTTP tests (tier 2)
  tests/e2e/                # new subprocess smoke tests (tier 3)
```

## Dependencies (new)

**Forge:**
- `@playwright/test` (devDependency, runs via Node.js `npx`)

**CLI:**
- `respx` (dev dependency for HTTP transport testing)

## Prior Research

See `/Users/jeremy.brown/.claude/projects/-Users-jeremy-brown-dev-openforge/memory/playwright_research.md` for Playwright benchmarks, Bun compatibility analysis, and speed optimization strategies.

## Key Decisions

- Playwright runs via Node.js (`npx playwright test`), NOT Bun — due to ongoing incompatibility
- Integration tests use `bun test` with `fetch()` — fast, no browser overhead
- Shared test server instance (Approach A) — simple, realistic, one boot for all tests
- CLI uses `respx` for HTTP transport mocking — catches wire-format bugs that `patch` misses
- Under 60s CI target enforced by keeping Playwright to 5-8 critical browser-only flows
