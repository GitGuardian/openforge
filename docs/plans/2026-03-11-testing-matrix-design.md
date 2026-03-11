# Testing Matrix — Gap Close & Prevention

**Date:** 2026-03-11
**Status:** Draft

---

## Goal

Ensure every OpenForge feature has at least a happy-path integration test and a happy-path E2E test. Close existing gaps at integration, E2E, and cross-component tiers, and establish a convention that prevents new gaps from forming as the project grows.

Unit test coverage is already ≥90% across both components and is excluded from scope.

---

## Testing Conventions (to be added to forge/CLAUDE.md and cli/CLAUDE.md)

### Testing Pyramid (4 tiers)

| Tier | Name | Forge | CLI |
|------|------|-------|-----|
| 1 | Unit | `bun test` (mocked) | `pytest` (mocked) |
| 2 | Integration | `fetch()` against live Forge+Supabase | `respx` transport mock |
| 3 | E2E (component) | Playwright browser tests | subprocess smoke tests |
| 4 | Cross-component E2E | Playwright + CLI subprocess together | — |

### Rule

Every new feature must have:

1. A happy-path **integration test** (Tier 2)
   - Forge: `fetch()` against live Forge server + local Supabase
   - CLI: `respx` transport mock or real Supabase subprocess test
2. A happy-path **E2E test** (Tier 3)
   - Forge: Playwright browser test
   - CLI: subprocess smoke test
3. Any feature that crosses the CLI↔Forge boundary must also have a **cross-component E2E test** (Tier 4) — a Playwright test that drives both CLI subprocess and the browser in the same test flow

### TDD order is mandatory

- Write integration and E2E tests **first** (red), then implement the feature until they pass (green)
- When fixing a bug: write a test that reproduces the bug first, then fix the code
- Never write implementation code before a failing test exists

### Exceptions (must be noted explicitly, never silently skipped)

- Pure infrastructure/middleware (CSRF, rate limiting, logging) — unit only acceptable
- Features browser-untestable by nature (webhooks, background jobs) — integration only acceptable

---

## Gap Analysis

### Forge — E2E gaps (Playwright)

| Feature | Missing test |
|---------|-------------|
| Post a comment via browser | `e2e/comments.spec.ts` |
| Edit a comment via browser | `e2e/comments.spec.ts` |
| Delete a comment via browser | `e2e/comments.spec.ts` |
| Reply to a comment via browser | `e2e/comments.spec.ts` |
| Curator dashboard browse + status filter | `e2e/curator.spec.ts` |
| Curator approve submission via browser | `e2e/curator.spec.ts` |
| Curator reject submission via browser | `e2e/curator.spec.ts` |
| Plugin detail README renders | `e2e/catalogue.spec.ts` (extend) |
| Plugin detail skills list visible | `e2e/catalogue.spec.ts` (extend) |
| Search standalone happy-path | `e2e/catalogue.spec.ts` (extend) |

### Forge — Integration gaps

| Feature | Missing test |
|---------|-------------|
| `GET /api/marketplace.json` response shape | `tests/integration/api.test.ts` |
| `GET /.well-known/skills/index.json` response shape | `tests/integration/api.test.ts` |
| `POST /api/telemetry` happy path (count increments) | `tests/integration/api.test.ts` |
| Pagination (page 2 ≠ page 1) | `tests/integration/catalogue.test.ts` |

### CLI — Integration gaps

| Feature | Missing test | Approach |
|---------|-------------|----------|
| `find --remote` hits Forge marketplace | `tests/integration/test_find.py` | `respx` transport mock |
| `check` outdated vs. up-to-date distinction | `tests/integration/test_check.py` | `respx` transport mock |
| `publish` happy path (auth'd user, gets 201) | `tests/integration/test_publish.py` | `respx` mock of `/api/submissions` |

### CLI — E2E (subprocess smoke) gaps

| Feature | Missing test | Approach |
|---------|-------------|----------|
| `auth login` happy path (token stored) | `tests/e2e/test_auth_smoke.py` | subprocess against local Supabase |
| `auth logout` clears token file | `tests/e2e/test_auth_smoke.py` | subprocess, checks token file deleted |
| `auth status` reports logged-in state | `tests/e2e/test_auth_smoke.py` | subprocess, checks stdout |

### Cross-component E2E gaps (Tier 4)

These tests verify the full user journey across CLI and Forge together. They live in `forge/e2e/cross-component.spec.ts` and use Playwright as the runner, spawning the CLI via `child_process.spawnSync('uv', ['run', 'openforge', ...args])` — args array, no shell interpolation.

| Scenario | Key steps |
|----------|-----------|
| Publish → review → install | `cli publish` → curator approves in browser → `cli add forge:<name>` → verify files installed |
| Submit → appears in catalogue | `cli publish` → approve → Playwright: verify plugin appears in browse |

**Harness requirements:**
- CLI invoked via `spawnSync('uv', ['run', 'openforge', ...args], { env, cwd: '<repo-root>/cli' })` — `cwd` set to `cli/` so `uv` resolves `pyproject.toml`; no shell string interpolation
- CLI configured via env vars (`OPENFORGE_FORGE_URL`, `OPENFORGE_SUPABASE_URL`) pointing to local servers
- Requires: local Supabase + local Forge server running, CLI available via `uv run openforge`
- Test user promoted to curator role for the approve step (via Supabase admin API in `beforeAll`)

---

## Implementation Plan

Work is split across three milestones and runs in parallel across forge-dev and cli-dev.
team-lead audits any bugs surfaced during test writing — fixes must be verified before marking work complete.

### Milestone 1 — Forge E2E gaps (forge-dev)

Priority: highest — these are the most visible coverage holes.

1. `e2e/comments.spec.ts` — post, edit, delete, reply via Playwright
2. `e2e/curator.spec.ts` — dashboard browse, status filter, approve, reject
3. Extend `e2e/catalogue.spec.ts` — README renders, skills list, search happy-path

### Milestone 2 — Forge integration gaps (forge-dev)

4. `tests/integration/api.test.ts` — marketplace.json shape, skills index shape, telemetry POST
5. `tests/integration/catalogue.test.ts` — pagination

### Milestone 3 — CLI integration/smoke gaps (cli-dev)

Runs in parallel with Milestones 1 and 2. Integration tests that hit the Forge API use `respx` transport mocks and are independent of the live Forge server, so they can run safely while forge-dev is changing routes. The `auth` smoke tests require local Supabase only.

6. `tests/e2e/test_auth_smoke.py` — login, logout, status subprocess smoke tests (requires local Supabase on port 54321)
7. `tests/integration/test_publish.py` — publish happy path via `respx` mock of `/api/submissions`
8. `tests/integration/test_find.py` — `find --remote` with respx mock of Forge marketplace endpoint
9. `tests/integration/test_check.py` — check outdated vs. current distinction via respx mock

### Milestone 4 — Cross-component E2E (forge-dev + cli-dev, after Milestones 1–3)

Blocked on Milestones 1 (curator E2E) and 3 (auth smoke) being complete first.

10. `forge/e2e/cross-component.spec.ts` — harness: `spawnSync` CLI helper + Playwright page
11. Scenario: `publish` → curator approves in browser → `add forge:<name>` → verify installed files
12. Scenario: submit → approve → verify plugin appears in catalogue browse

forge-dev writes the Playwright harness + browser steps; cli-dev verifies CLI invocation args and env var config.

### Conventions update (both agents, in parallel with Milestone 1)

- Add TDD + integration/E2E rule to `forge/CLAUDE.md`
- Add TDD + integration/E2E rule to `cli/CLAUDE.md`

### Fixture / seed data requirements

Forge E2E tests for comments and curator flows require:
- An authenticated test user (email + password in the local seed)
- At least one approved plugin in the DB
- At least one pending submission for curator tests

These should be provided by the existing seed scripts (`supabase/seed.sql` or equivalent). forge-dev must verify seed data covers these cases and extend it if not — before writing E2E tests that depend on it.

---

## Bug Protocol

If tests reveal bugs during this work:
1. The discovering agent writes a failing test that reproduces the bug
2. The agent fixes the code
3. team-lead reviews the fix and verifies the test passes before marking complete

---

## Success Criteria

- All features in the gap analysis have a passing happy-path integration test and E2E test
- `forge/CLAUDE.md` and `cli/CLAUDE.md` both contain the testing conventions rule (this is the enforcement mechanism — agents read CLAUDE.md before every task)
- All tests pass: `bun test`, `bun run test:integration`, `npx playwright test` (Forge); `pytest` (CLI)
- Cross-component E2E suite passes: `npx playwright test e2e/cross-component.spec.ts`
- No new features are implemented before their integration + E2E tests are written and failing (TDD red before green)
- Any CLI↔Forge feature includes a cross-component E2E scenario
