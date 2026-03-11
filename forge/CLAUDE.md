# The Forge — Agent Instructions

This file contains rules, commands, and conventions specific to the Forge web app. For project-wide context, see the root `../CLAUDE.md`.

---

## Stack

| Layer | Technology | Notes |
|-------|-----------|-------|
| Runtime | Bun | Use `bun` for everything (install, run, test). |
| Server | Hono | Lightweight, Express-like. Routes return HTML or JSON. |
| Interactivity | HTMX | No client-side JS framework. Server returns HTML fragments. |
| Styling | Tailwind CSS (CDN) | Utility classes only. No build step for CSS. |
| Database | Supabase (Postgres + RLS) | Managed Postgres with Row Level Security on all tables. |
| ORM | Drizzle | Type-safe, schema-as-code. Generates SQL migrations. |
| Auth | Supabase Auth | Email/password, magic link, OAuth providers. |
| Deploy | Railway | Dockerfile-based, behind Cloudflare. Push to main = deployed. |

---

## Commands

```bash
bun install              # Install dependencies
supabase start           # Start local Supabase (Postgres, Auth, Studio)
bun run dev              # Start dev server with hot reload
bun run start            # Start production server
bun test                 # Run unit tests (mocked, ~10-15s)
bun test --coverage      # Run unit tests with coverage report
bun run test:integration # Run integration tests against real Forge+Supabase (~5-10s)
bun run test:e2e         # Run Playwright E2E tests via Node.js (~7-10s)
bun run test:all         # Run all tiers (unit + integration + e2e)
bash scripts/check-coverage.sh 90  # Run tests and fail if coverage < 90%
bun run db:generate      # Generate migration from schema changes
bun run db:migrate       # Apply migrations to database
bun run db:studio        # Open Drizzle Studio (database GUI)
bun run typecheck        # Run TypeScript type checking
bun run seed -- --repo <url> --name <registry>  # Seed database from a git repo
supabase stop            # Stop local Supabase
```

---

## Project Structure

```
forge/
  package.json
  tsconfig.json
  drizzle.config.ts
  Dockerfile
  .env.example
  src/
    index.ts                  # App entry point — registers middleware and routes
    types.ts                  # Shared Hono types (AppEnv)
    middleware/
      auth.ts                 # Supabase Auth middleware
    routes/
      pages.ts                # HTML page routes (catalogue, detail, submit, my-submissions, curator)
      api.ts                  # JSON API (marketplace.json, telemetry, well-known)
      auth.ts                 # Auth routes (login, signup, magic-link, logout)
      health.ts               # GET /health
      votes.ts                # Vote routes (upvote, downvote, remove)
      comments.ts             # Comment routes (create, edit, delete, load)
      webhooks.ts             # GitHub webhook endpoint (HMAC-verified, triggers indexing)
      submissions.ts          # Submissions API (create, list, review)
    db/
      schema.ts               # Drizzle table definitions (9 tables, incl. submissions)
      index.ts                # Database client
    lib/
      markdown.ts             # Markdown rendering (marked + DOMPurify)
      supabase.ts             # Supabase client (auth, storage)
      rate-limit.ts           # In-memory rate limiting
      indexer.ts              # Indexer library (clone, scan, upsert plugins/skills, indexSubmission)
      notifications.ts        # Email notifications (fire-and-forget)
    views/
      layout.ts               # HTML layout (Tailwind + HTMX, auth-aware nav)
      submit.ts               # Submit plugin form (/submit)
      my-submissions.ts       # User's own submissions (/my/submissions)
      curator-dashboard.ts    # Curator submissions dashboard (/curator/submissions)
      components/
        vote-widget.ts        # HN-style vote widget
        comment-section.ts    # Threaded comment section with EasyMDE
        submission-review.ts  # Curator review banner (approve/reject)
    scripts/
      seed.ts                 # Seed database from git repos
      check-coverage.sh       # Coverage threshold check (used by pre-commit hook)
  tests/                      # Unit tests (bun test, mocked DB/auth, 90%+ coverage target)
    setup.ts                  # Shared test helpers (mockUser, createTestApp)
    routes/                   # Route tests (one file per route module)
    middleware/               # Middleware tests
    lib/                      # Lib module tests
    integration/              # Integration tests (real Forge+Supabase via fetch())
      helpers.ts              # Test user creation, auth fetch helpers
  e2e/                        # Playwright E2E tests (Node.js, NOT Bun)
    helpers.ts                # Shared E2E helpers (createE2EUser, loginViaUI)
  playwright.config.ts        # Playwright config (chromium, headless)
    routes/                   # Route tests (one file per route module)
    middleware/               # Middleware tests
    lib/                      # Lib module tests
  drizzle/                    # Generated SQL migrations
  supabase/                   # Local Supabase config (supabase init)
  public/                     # Static files served at /public/*
```

---

## Rules

Follow these strictly. They prevent common failure modes.

**Always use Drizzle for database queries.**
Use the Drizzle client (`src/db/index.ts`) and schema (`src/db/schema.ts`) for all database operations. Never write raw SQL strings in route handlers.

**Always use HTMX for interactivity.**
Do not add React, Vue, or any client-side JavaScript framework. Do not write inline `<script>` tags for interactivity. Use HTMX attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`) to make the page dynamic. The server returns HTML fragments.

**Always use Tailwind utility classes for styling.**
Do not create CSS files or `<style>` tags. Use Tailwind classes directly on HTML elements. The CDN is loaded in the layout.

**After schema changes, always run generate + migrate.**
Whenever you modify `src/db/schema.ts`, run:
```bash
bun run db:generate && bun run db:migrate
```

**Register new routes in `src/index.ts`.**
After creating a new route file, import it and register with `app.route("/", yourRoutes)`. Routes won't work until registered.

**User identity comes from Supabase Auth middleware.**
Access the current user via `c.get("user")` in any route. The auth middleware in `src/middleware/auth.ts` handles session validation against Supabase Auth. RLS enforces permissions at the database level.

**Coverage minimum is 90%.** Enforced by pre-commit hook (`scripts/check-coverage.sh`). Run `bash scripts/check-coverage.sh 90` to check locally. Never commit changes that drop coverage below 90%.

**Run local CI before pushing anything bigger than a tiny fix.**
```bash
bun run test                 # Unit tests (~0.7s)
bun run test:integration     # Integration tests — requires Forge+Supabase running (~1.5s)
npx playwright test          # E2E browser tests — requires Forge+Supabase running (~7s)
bun run typecheck            # TypeScript type checking
```
Integration and Playwright tests need local Supabase (`supabase start`) and Forge (`bun run dev`). The pre-commit hook runs integration tests automatically if Forge is reachable; Playwright is CI-only.

---

## Testing Conventions

### Testing pyramid (4 tiers)

| Tier | Name | Tool |
|------|------|------|
| 1 | Unit | `bun test` (mocked) |
| 2 | Integration | `fetch()` against live Forge+Supabase |
| 3 | E2E (component) | Playwright browser tests |
| 4 | Cross-component E2E | Playwright + CLI subprocess (`spawnSync`) |

### Rule: every feature must have

1. A happy-path **integration test** — `fetch()` against live Forge server + local Supabase
2. A happy-path **E2E test** — Playwright browser test
3. Any feature crossing the CLI↔Forge boundary must also have a **cross-component E2E test** in `e2e/cross-component.spec.ts`

### TDD order is mandatory

- Write integration and E2E tests **first** (red), then implement until they pass (green)
- When fixing a bug: write a failing test that reproduces the bug first, then fix the code
- Never write implementation code before a failing test exists

### Exceptions (note explicitly — never silently skip)

- Pure infrastructure/middleware (CSRF, rate limiting, logging) — unit only acceptable
- Features browser-untestable by nature (webhooks, background jobs) — integration only acceptable

---

## Key Files

- **`src/index.ts`** — Entry point. All middleware and routes registered here.
- **`src/db/schema.ts`** — Database schema (9 tables). Source of truth for what tables exist.
- **`src/routes/auth.ts`** — Auth routes (login, signup, magic-link, callback, logout).
- **`src/routes/pages.ts`** — Catalogue page with search/pagination, plugin detail page, submit form, my-submissions, curator dashboard.
- **`src/routes/api.ts`** — JSON APIs (marketplace.json, skills index, telemetry).
- **`src/routes/submissions.ts`** — Submissions API (POST create, GET list, POST review).
- **`src/middleware/auth.ts`** — Supabase Auth session handling, private/public mode.
- **`src/views/layout.ts`** — HTML layout wrapper with auth-aware nav.
- **`src/scripts/seed.ts`** — Seed database by cloning and scanning git repos.
- **`src/lib/markdown.ts`** — Server-side markdown rendering with sanitization.

---

## Environment Setup

### Local dev

1. Install Supabase CLI: `brew install supabase/tap/supabase`
2. `bun install`
3. `supabase start` (requires Docker — starts local Postgres, Auth, Studio)
4. Copy `.env.example` to `.env` — fill in values from `supabase status`
5. `bun run db:migrate`
6. `bun run seed -- --repo https://github.com/anthropics/claude-code --name anthropic`
7. `bun run dev` — app at http://localhost:3000, Studio at http://127.0.0.1:54323

### Cloud Supabase

1. Create a Supabase project and copy credentials to `.env`:
   - `DATABASE_URL` — Postgres connection string
   - `SUPABASE_URL` — Project URL
   - `SUPABASE_ANON_KEY` — Anonymous key
   - `SUPABASE_SERVICE_ROLE_KEY` — Service role key
2. `bun install`
3. `bun run db:migrate`
4. `bun run dev`
