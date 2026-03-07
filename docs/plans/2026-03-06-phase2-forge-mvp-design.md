# Phase 2: The Forge MVP — Design Document

**Date:** 2026-03-06
**Status:** Draft
**Depends on:** Phase 1 (CLI MVP) — complete
**Goal:** Ship a working web app where users can browse a curated plugin/skill catalogue, view details, and integrate with the CLI via `marketplace.json` and `.well-known/skills/index.json` endpoints.

---

## Scope

Phase 2 delivers the **catalogue and API layer** — the minimum needed for The Forge to be useful:

| In scope | Out of scope (Phase 3+) |
|----------|------------------------|
| Database schema (all core tables) | Votes / upvote-downvote |
| Supabase Auth (email/password, magic link) | Threaded comments |
| Browse/search catalogue page | GitHub webhook indexing pipeline |
| Plugin detail page with rendered README | Rate limiting |
| `GET /api/marketplace.json` | Security headers (CSP, HSTS) |
| `GET /.well-known/skills/index.json` | Admin panel UI |
| `POST /api/telemetry` | Notifications (Slack/email) |
| Seed script for populating registry data | Non-technical submissions |
| Auth middleware + RLS policies | Curator dashboard |
| Private/public mode toggle | |
| Railway deployment | |
| Health check endpoint | |

Community features (votes, comments) and automated git indexing move to **Phase 3**.

---

## Phase Renumbering

With the old Phase 2 split, the project milestones become:

| Phase | Name | Status |
|-------|------|--------|
| 1 | CLI MVP | Complete |
| 2 | **The Forge MVP** (this doc) | Next |
| 3 | **Community & Indexing** (votes, comments, webhooks) | New |
| 4 | Non-technical Submissions (was Phase 3) | Future |
| 5 | Polish & Expand (was Phase 4) | Future |
| 6 | Open-source Release (was Phase 5) | Future |
| Backlog | CLI Parity & Enhancements | Ongoing |

---

## Tech Stack

Unchanged from the architecture doc. Matches gg-launchpad conventions.

| Layer | Technology | Notes |
|-------|-----------|-------|
| Runtime | Bun | `bun install`, `bun run dev`, `bun run start` |
| Server | Hono | Routes return HTML (pages) or JSON (API) |
| Interactivity | HTMX | Server returns HTML fragments, no client-side JS framework |
| Styling | Tailwind CSS (CDN) | Utility classes only, no build step |
| Database | Supabase (Postgres) | Managed Postgres, RLS on all tables |
| ORM | Drizzle | Type-safe, schema-as-code, generates SQL migrations |
| Auth | Supabase Auth | Email/password, magic link. OAuth deferred. |
| Markdown | marked | Server-side rendering at seed/index time |
| Deploy | Railway | Dockerfile-based, push to main = deploy |

---

## Architecture Overview

```
                                 +-------------------+
                                 |   Cloudflare CDN  |
                                 +--------+----------+
                                          |
                                 +--------v----------+
                                 |   Railway (Bun)   |
                                 |                   |
                                 |  Hono App         |
                                 |  +-----------+    |
  Browser ----HTMX/HTML-------->|  | Pages      |   |
                                 |  | (browse,   |   |
                                 |  |  detail,   |   |
                                 |  |  auth)     |   |
                                 |  +-----------+    |
                                 |  +-----------+    |
  CLI --------JSON------------->|  | API        |   |
  Claude Code --JSON----------->|  | (market,   |   |
                                 |  |  well-known|   |
                                 |  |  telemetry)|   |
                                 |  +-----------+    |
                                 |        |          |
                                 +--------+----------+
                                          |
                                 +--------v----------+
                                 |   Supabase        |
                                 |  +------+ +-----+ |
                                 |  |Postgres| |Auth | |
                                 |  +------+ +-----+ |
                                 +-------------------+
```

### Request Flow

1. Request hits Cloudflare (TLS termination, caching for static assets)
2. Proxied to Railway (Bun + Hono)
3. Auth middleware validates Supabase JWT from cookie (pages) or Bearer token (API)
4. Route handler queries Postgres via Drizzle
5. Returns HTML (pages) or JSON (API)

---

## Database Schema

All tables defined in `forge/src/db/schema.ts` using Drizzle. UUIDs for all primary keys. RLS enabled on all tables.

### Entity Relationship Diagram

```mermaid
erDiagram
    registries ||--o{ plugins : contains
    registries ||--o{ skills : contains
    plugins ||--o{ skills : has
    users ||--o{ votes : casts
    plugins ||--o{ votes : receives
    users ||--o{ comments : writes
    plugins ||--o{ comments : has
    comments ||--o{ comments : replies_to

    registries {
        uuid id PK
        text name UK
        text git_url
        text registry_type
        text webhook_secret
        timestamptz indexed_at
        timestamptz created_at
    }

    plugins {
        uuid id PK
        uuid registry_id FK
        text name
        text version
        text description
        text category
        text[] tags
        text readme_html
        jsonb plugin_json
        text git_path
        text git_sha
        text status
        int install_count
        int vote_score
        timestamptz created_at
        timestamptz updated_at
    }

    skills {
        uuid id PK
        uuid plugin_id FK
        uuid registry_id FK
        text name
        text description
        text skill_md_path
        jsonb metadata
        timestamptz created_at
    }

    users {
        uuid id PK
        text email UK
        text display_name
        text role
        uuid auth_id UK
        timestamptz created_at
    }

    votes {
        uuid user_id PK_FK
        uuid plugin_id PK_FK
        smallint value
        timestamptz created_at
    }

    comments {
        uuid id PK
        uuid plugin_id FK
        uuid user_id FK
        uuid parent_id FK
        text body
        timestamptz created_at
        timestamptz updated_at
    }

    install_events {
        uuid id PK
        text plugin_name
        text skill_name
        text version
        text source
        text[] agents
        text cli_version
        boolean is_ci
        timestamptz created_at
    }

    allowed_domains {
        uuid id PK
        text domain UK
        timestamptz created_at
    }
```

### Phase 2 vs Phase 3 Tables

**Phase 2 — create schema + seed/query:**
- `registries` — populated by seed script
- `plugins` — populated by seed script
- `skills` — populated by seed script
- `users` — created on first auth
- `install_events` — written by telemetry endpoint
- `allowed_domains` — populated by seed script or env var

**Phase 3 — activate with UI:**
- `votes` — schema created in Phase 2, UI in Phase 3
- `comments` — schema created in Phase 2, UI in Phase 3

All tables are created in Phase 2 so the schema is complete. Phase 3 adds the routes and UI to use votes/comments.

### RLS Policies

```sql
-- registries: public read, admin write
CREATE POLICY "registries_select" ON registries FOR SELECT USING (true);
CREATE POLICY "registries_insert" ON registries FOR INSERT
  WITH CHECK (auth.jwt() ->> 'role' = 'admin');

-- plugins: public read, admin write
CREATE POLICY "plugins_select" ON plugins FOR SELECT USING (true);
CREATE POLICY "plugins_admin" ON plugins FOR ALL
  USING (auth.jwt() ->> 'role' = 'admin');

-- skills: public read
CREATE POLICY "skills_select" ON skills FOR SELECT USING (true);

-- users: own row read, admin all
CREATE POLICY "users_own" ON users FOR SELECT
  USING (auth_id = auth.uid());
CREATE POLICY "users_admin" ON users FOR ALL
  USING (auth.jwt() ->> 'role' = 'admin');

-- votes: own votes CRUD
CREATE POLICY "votes_own" ON votes FOR ALL
  USING (user_id = (SELECT id FROM users WHERE auth_id = auth.uid()));

-- comments: public read, own write
CREATE POLICY "comments_select" ON comments FOR SELECT USING (true);
CREATE POLICY "comments_own" ON comments FOR INSERT
  WITH CHECK (user_id = (SELECT id FROM users WHERE auth_id = auth.uid()));

-- install_events: insert only (no auth required), admin read
CREATE POLICY "install_events_insert" ON install_events FOR INSERT
  WITH CHECK (true);
CREATE POLICY "install_events_admin" ON install_events FOR SELECT
  USING (auth.jwt() ->> 'role' = 'admin');

-- allowed_domains: public read (needed at signup), admin write
CREATE POLICY "allowed_domains_select" ON allowed_domains FOR SELECT USING (true);
CREATE POLICY "allowed_domains_admin" ON allowed_domains FOR ALL
  USING (auth.jwt() ->> 'role' = 'admin');
```

Note: The Forge app uses the Supabase service role key for write operations during seeding and indexing, bypassing RLS. RLS protects against direct Supabase client access and future public API usage.

---

## Authentication

### Strategy: Supabase Auth

Supabase Auth handles user registration, login, session management, and JWT issuance. The Forge validates JWTs in middleware.

### Auth Flows

**Email/Password:**
1. User submits email + password to `/auth/signup` or `/auth/login`
2. Server calls `supabase.auth.signUp()` or `supabase.auth.signInWithPassword()`
3. On success, set session cookie (`sb-access-token`, `sb-refresh-token`)
4. Redirect to `/`

**Magic Link:**
1. User submits email to `/auth/magic-link`
2. Server calls `supabase.auth.signInWithOtp({ email })`
3. User clicks link in email → redirected to `/auth/callback?token_hash=...`
4. Server exchanges token, sets session cookie, redirects to `/`

### Auth Middleware

```typescript
// forge/src/middleware/auth.ts
export const authMiddleware = createMiddleware<AppEnv>(async (c, next) => {
  const accessToken = getCookie(c, "sb-access-token");

  if (!accessToken) {
    c.set("user", null);
    return next();
  }

  const { data: { user }, error } = await supabase.auth.getUser(accessToken);

  if (error || !user) {
    // Token expired or invalid — clear cookies
    deleteCookie(c, "sb-access-token");
    deleteCookie(c, "sb-refresh-token");
    c.set("user", null);
    return next();
  }

  // Look up or create app user
  const appUser = await getOrCreateUser(user.id, user.email);
  c.set("user", appUser);
  return next();
});
```

### Require Auth Helper

```typescript
// For routes that require authentication
function requireAuth(c: Context<AppEnv>): AppUser {
  const user = c.get("user");
  if (!user) throw new HTTPException(401, { message: "Login required" });
  return user;
}

// For routes that require a specific role
function requireRole(c: Context<AppEnv>, role: "admin" | "curator"): AppUser {
  const user = requireAuth(c);
  if (user.role !== role && user.role !== "admin") {
    throw new HTTPException(403, { message: "Insufficient permissions" });
  }
  return user;
}
```

### Private Mode

When `OPENFORGE_MODE=private`:
- All page routes require authentication (redirect to `/auth/login`)
- API endpoints require Bearer token
- Registration restricted to allowed email domains
- Domain check at signup: `email.split("@")[1]` must be in `allowed_domains` table

When `OPENFORGE_MODE=public`:
- Browse and API endpoints are public (no auth required)
- Write actions (vote, comment — Phase 3) require auth
- Registration open to all

### User Roles

| Role | Capabilities |
|------|-------------|
| `user` | Browse, search, install (Phase 2). Vote, comment (Phase 3). |
| `curator` | All user capabilities + approve/reject submissions (Phase 4) |
| `admin` | All capabilities + manage registries, users, domains |

The first user created can be promoted to admin via the seed script or direct SQL.

### Types

```typescript
// forge/src/types.ts
export type AppUser = {
  id: string;       // UUID from users table
  email: string;
  displayName: string | null;
  role: "user" | "curator" | "admin";
  authId: string;   // Supabase Auth UID
};

export type AppEnv = {
  Variables: {
    user: AppUser | null;
  };
};
```

---

## Routes

### Page Routes (`forge/src/routes/pages.ts`)

| Route | Auth | Description |
|-------|------|-------------|
| `GET /` | Mode-dependent | Catalogue: browse + search |
| `GET /plugins/:name` | Mode-dependent | Plugin detail page |
| `GET /auth/login` | Public | Login form |
| `GET /auth/signup` | Public | Signup form |
| `GET /auth/callback` | Public | Magic link callback |
| `POST /auth/login` | Public | Handle login |
| `POST /auth/signup` | Public | Handle signup |
| `POST /auth/magic-link` | Public | Send magic link |
| `POST /auth/logout` | Auth | Clear session |

### API Routes (`forge/src/routes/api.ts`)

| Route | Auth | Description | Response |
|-------|------|-------------|----------|
| `GET /api/marketplace.json` | Mode-dependent | Claude Code marketplace | JSON |
| `GET /.well-known/skills/index.json` | Mode-dependent | skills.sh compatible index | JSON |
| `POST /api/telemetry` | None | CLI install events | 204 No Content |

### Health Route (`forge/src/routes/health.ts`)

| Route | Auth | Description |
|-------|------|-------------|
| `GET /health` | None | Health check |

---

## Pages

### Catalogue Page (`GET /`)

The landing page. Shows all plugins/skills from registered repos.

**Layout:**
```
+----------------------------------------------------------+
|  OpenForge                              [Login] [Signup]  |
+----------------------------------------------------------+
|                                                          |
|  [Search plugins and skills...              ] [Search]   |
|                                                          |
|  +----------------------------------------------------+  |
|  | plugin-name                           12 installs   |  |
|  | Short description of what this plugin does          |  |
|  | [tag1] [tag2] [tag3]           source/repo          |  |
|  +----------------------------------------------------+  |
|  | another-plugin                         8 installs   |  |
|  | Another description here                            |  |
|  | [tag1] [tag2]                  source/repo          |  |
|  +----------------------------------------------------+  |
|  |                    ...                              |  |
|  +----------------------------------------------------+  |
|                                                          |
|  [< Previous]                          [Next >]          |
+----------------------------------------------------------+
```

**Behavior:**
- Default: list all approved plugins, sorted by install count descending
- Search: `ILIKE` on `plugins.name`, `plugins.description`, and `plugins.tags` (array contains)
- Pagination: 20 items per page, offset-based
- HTMX: search input triggers `hx-get="/partials/plugin-list?q=..."` with debounce, swaps the list

**Server query:**
```typescript
const plugins = await db.select()
  .from(schema.plugins)
  .where(
    and(
      eq(schema.plugins.status, "approved"),
      query ? or(
        ilike(schema.plugins.name, `%${query}%`),
        ilike(schema.plugins.description, `%${query}%`),
      ) : undefined,
    )
  )
  .orderBy(desc(schema.plugins.installCount))
  .limit(20)
  .offset(page * 20);
```

### Plugin Detail Page (`GET /plugins/:name`)

**Layout:**
```
+----------------------------------------------------------+
|  OpenForge                              [Login] [Signup]  |
+----------------------------------------------------------+
|                                                          |
|  < Back to catalogue                                     |
|                                                          |
|  plugin-name                              v1.2.0         |
|  Short description                                       |
|  [tag1] [tag2] [tag3]                                    |
|                                                          |
|  +-- Install ----------------------------------------+   |
|  | CLI:          uvx openforge add owner/repo        |   |
|  | Claude Code:  marketplace add <url>               |   |
|  | skills.sh:    npx skills add owner/repo           |   |
|  +---------------------------------------------------+   |
|                                                          |
|  +-- About ------------------------------------------+   |
|  | Skills: skill-a, skill-b, skill-c                 |   |
|  | MCP servers: 1  |  Commands: 3  |  Hooks: 2      |   |
|  | Source: github.com/owner/repo @ abc1234           |   |
|  +---------------------------------------------------+   |
|                                                          |
|  +-- README -----------------------------------------+   |
|  | (rendered markdown)                               |   |
|  +---------------------------------------------------+   |
|                                                          |
+----------------------------------------------------------+
```

**Data source:** Single query joining `plugins` + `skills` where `skills.plugin_id = plugin.id`.

**README rendering:** The `readme_html` column stores pre-rendered HTML (rendered at seed time using `marked`). Output is sanitized to prevent XSS.

### Auth Pages

Minimal forms. Tailwind-styled, server-rendered.

**Login (`GET /auth/login`):**
- Email + password fields
- "Or sign in with magic link" link
- "Don't have an account? Sign up" link

**Signup (`GET /auth/signup`):**
- Email + password + confirm password fields
- In private mode: "Registration restricted to [domain] emails"
- "Already have an account? Log in" link

**Magic Link (`GET /auth/magic-link`):**
- Email field
- "Check your email for a login link" success message

---

## API Endpoints

### `GET /api/marketplace.json`

Claude Code and Cowork consume this natively via `claude plugin marketplace add <url>`.

**Response format:**
```json
{
  "version": "0.1.0",
  "packages": [
    {
      "id": "uuid",
      "name": "plugin-name",
      "description": "What it does",
      "displayName": "Plugin Name",
      "category": "security",
      "tags": ["security", "scanning"],
      "version": "1.0.0",
      "installCount": 42,
      "author": "owner",
      "downloadUrl": "https://github.com/owner/repo.git",
      "gitPath": "plugins/plugin-name",
      "gitSha": "abc1234",
      "status": "approved"
    }
  ]
}
```

**Query:** Select all approved plugins, join with registry for git URL.

**Caching:** Set `Cache-Control: public, max-age=300` (5 minutes). Cloudflare caches at the edge.

### `GET /.well-known/skills/index.json`

Compatible with the skills.sh well-known provider protocol.

**Response format:**
```json
{
  "version": "1.0.0",
  "skills": [
    {
      "name": "skill-name",
      "displayName": "Skill Name",
      "description": "What it does",
      "category": "conventions",
      "tags": ["style", "formatting"],
      "author": "owner",
      "version": "1.0.0",
      "source": {
        "type": "git",
        "url": "https://github.com/owner/repo.git",
        "path": "skills/skill-name/SKILL.md",
        "sha": "abc1234"
      },
      "metadata": {
        "installCount": 42
      }
    }
  ]
}
```

**Query:** Select all skills, join with plugin (if any) and registry.

**Caching:** Same as marketplace.json — `Cache-Control: public, max-age=300`.

### `POST /api/telemetry`

Fire-and-forget. No auth required. Accepts install events from the CLI.

**Request body:**
```json
{
  "event": "install",
  "plugin_name": "owner/repo",
  "skill_name": "skill-a",
  "version": "1.0.0",
  "source": "cli",
  "agents": ["claude-code", "cursor"],
  "cli_version": "0.1.0",
  "is_ci": false
}
```

**Behavior:**
1. Validate body shape (reject malformed — no crash, just 400)
2. Insert into `install_events`
3. Increment `plugins.install_count` (best-effort, `UPDATE ... SET install_count = install_count + 1`)
4. Return `204 No Content`

**Validation:**
- `plugin_name`: required, max 200 chars, no path traversal chars
- `source`: must be one of `"cli"`, `"hook-activate"`, `"marketplace-fetch"`
- `agents`: array of strings, max 20 items
- Body size limit: 4KB

---

## Seeding Data

Instead of webhook-driven git indexing (Phase 3), Phase 2 uses a **seed script** to populate the database from a git repo.

### Seed Script (`forge/src/scripts/seed.ts`)

Run manually: `bun run seed` or `bun run seed -- --repo https://github.com/owner/repo.git`

**Flow:**
1. Read registry config from env or CLI args (git URL, name, type)
2. Clone repo to temp directory (`git clone --depth 1`)
3. Scan for content:
   - `.claude-plugin/plugin.json` or `marketplace.json` at repo root
   - `SKILL.md` files (recursive)
4. For each plugin found:
   - Parse `plugin.json` metadata
   - Read and render README.md with `marked` (sanitize HTML output)
   - Upsert into `plugins` table
5. For each skill found:
   - Parse SKILL.md frontmatter
   - Determine if part of a plugin or standalone
   - Upsert into `skills` table
6. Upsert `registries` entry with `indexed_at = now()`
7. Clean up temp directory

**package.json script:**
```json
{
  "seed": "bun run src/scripts/seed.ts",
  "seed:dev": "bun run src/scripts/seed.ts -- --repo https://github.com/anthropics/claude-code-plugins.git"
}
```

This can be re-run to refresh data. The upsert logic (ON CONFLICT UPDATE) makes it idempotent.

---

## File Structure

```
forge/
  package.json
  tsconfig.json
  drizzle.config.ts
  Dockerfile
  .env.example
  src/
    index.ts                    # Hono app, middleware, route registration
    types.ts                    # AppEnv, AppUser types
    middleware/
      auth.ts                   # Supabase Auth JWT validation
    routes/
      pages.ts                  # HTML pages (catalogue, detail, auth)
      api.ts                    # JSON API (marketplace, well-known, telemetry)
      health.ts                 # GET /health
    db/
      schema.ts                 # Drizzle table definitions
      index.ts                  # Database client
    lib/
      supabase.ts               # Supabase client (auth, storage)
      markdown.ts               # marked wrapper with sanitization
    views/
      layout.ts                 # HTML layout (head, nav, footer)
      components/
        plugin-card.ts          # Plugin card for catalogue list
        plugin-detail.ts        # Plugin detail view
        auth-forms.ts           # Login/signup/magic-link forms
        nav.ts                  # Navigation bar
    scripts/
      seed.ts                   # Seed database from git repo
  drizzle/                      # Generated SQL migrations
  public/                       # Static files (favicon, etc.)
```

### New files vs existing skeleton

The forge skeleton already has the directory structure and empty files. Phase 2 fills them in and adds:

**New files:**
- `src/lib/markdown.ts`
- `src/views/components/plugin-card.ts`
- `src/views/components/plugin-detail.ts`
- `src/views/components/auth-forms.ts`
- `src/views/components/nav.ts`
- `src/scripts/seed.ts`

**New dependencies:**
- `marked` — Markdown rendering
- `dompurify` + `jsdom` — HTML sanitization for rendered markdown
- `hono/cookie` — Cookie handling (built into Hono, no extra dep)

---

## Deployment

### Railway

Same pattern as gg-launchpad. Dockerfile-based, auto-deploy on push to main.

**Dockerfile** (unchanged from skeleton):
```dockerfile
FROM oven/bun:1 AS base
WORKDIR /app
COPY package.json bun.lockb* ./
RUN bun install --frozen-lockfile || bun install
COPY . .
EXPOSE 3000
CMD ["bun", "run", "start"]
```

### Environment Variables

```bash
# Database
DATABASE_URL=postgresql://postgres:password@db.xxx.supabase.co:5432/postgres

# Supabase
SUPABASE_URL=https://xxx.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# App
PORT=3000
OPENFORGE_MODE=private          # "private" or "public"
ALLOWED_DOMAINS=gitguardian.com # comma-separated, empty = open registration

# Optional
LOG_LEVEL=info
```

### First Deployment Checklist

1. Create Supabase project
2. Create Railway project, connect to GitHub repo
3. Set environment variables in Railway
4. Deploy (auto on push)
5. Run migrations: `railway run bun run db:migrate`
6. Run seed: `railway run bun run seed -- --repo <url>`
7. Verify: `curl https://openforge.gitguardian.com/health`
8. Verify: `curl https://openforge.gitguardian.com/api/marketplace.json`

---

## Private Mode Behavior

The first deployment is `openforge.gitguardian.com` in private mode.

| Aspect | Private | Public |
|--------|---------|--------|
| Browse pages | Auth required (redirect to login) | Open |
| API endpoints | Bearer token required | Open |
| Registration | Restricted to allowed domains | Open to all |
| Telemetry endpoint | No auth (fire-and-forget) | No auth |
| Health endpoint | No auth | No auth |

The `OPENFORGE_MODE` env var controls this. The auth middleware checks it:
- Private: all routes except `/auth/*`, `/health`, and `/api/telemetry` require auth
- Public: only write routes require auth (Phase 3)

---

## Implementation Tasks

Ordered for incremental development. Each task is independently testable.

### Task 1: Dependencies and project setup
- `bun install` new deps (`marked`, `dompurify`, `jsdom`)
- Update `package.json` with seed script
- Verify `bun run dev` starts (even with empty routes)

### Task 2: Database schema
- Define all tables in `forge/src/db/schema.ts`
- Run `bun run db:generate && bun run db:migrate`
- Verify tables exist in Supabase dashboard

### Task 3: RLS policies
- Write SQL migration for all RLS policies
- Apply via `bun run db:migrate` or Supabase dashboard
- Test: anon user can SELECT plugins, cannot INSERT

### Task 4: Types and Supabase client
- Define `AppUser`, `AppEnv` in `forge/src/types.ts`
- Update `forge/src/lib/supabase.ts` with auth client helpers
- Create `forge/src/db/index.ts` with Drizzle client

### Task 5: Auth middleware
- Implement `forge/src/middleware/auth.ts`
- JWT validation from cookies
- `getOrCreateUser()` helper
- Private mode redirect logic

### Task 6: Auth pages and routes
- Login form, signup form, magic link form
- `POST /auth/login`, `POST /auth/signup`, `POST /auth/magic-link`
- `GET /auth/callback` (magic link)
- `POST /auth/logout`
- Allowed domain check on signup (private mode)

### Task 7: Layout and nav
- Update `forge/src/views/layout.ts` with full HTML layout
- Nav bar with logo, user state (logged in/out), login/signup links
- Responsive Tailwind styling

### Task 8: Health endpoint
- `GET /health` returns `{ status: "ok", timestamp: "..." }`

### Task 9: Seed script
- `forge/src/scripts/seed.ts`
- Clone repo, scan for plugins/skills, render README, upsert to DB
- `bun run seed -- --repo <url>`

### Task 10: Markdown rendering
- `forge/src/lib/markdown.ts`
- `marked` for rendering, `dompurify` for sanitization
- Used by seed script and detail page

### Task 11: Catalogue page
- `GET /` — list plugins with search
- Plugin card component
- Pagination (offset-based, 20 per page)
- HTMX search with debounce

### Task 12: Plugin detail page
- `GET /plugins/:name` — full detail view
- Join plugins + skills
- Rendered README
- Install instructions

### Task 13: marketplace.json endpoint
- `GET /api/marketplace.json`
- Query all approved plugins, format as Claude Code marketplace
- Cache-Control headers

### Task 14: well-known skills endpoint
- `GET /.well-known/skills/index.json`
- Query all skills, format as skills.sh index
- Cache-Control headers

### Task 15: Telemetry endpoint
- `POST /api/telemetry`
- Validate body, insert into `install_events`
- Increment `plugins.install_count`
- Return 204

### Task 16: App entry point and wiring
- Wire all middleware and routes in `forge/src/index.ts`
- Error handler
- Static file serving
- Logger middleware

### Task 17: Railway deployment
- Verify Dockerfile builds
- Deploy to Railway
- Run migrations and seed
- Smoke test all endpoints

---

## Testing Strategy

Phase 2 does not require the same test rigor as the CLI (no pyright, no 90% coverage target). Instead:

**Manual smoke tests** after each task:
- `bun run dev` and hit routes in browser
- `curl` API endpoints
- Verify Drizzle queries work against Supabase

**Type safety:**
- `bun run typecheck` (TypeScript strict mode)
- Drizzle provides type-safe queries

**Post-deployment:**
- Health check: `GET /health`
- Marketplace: `GET /api/marketplace.json` returns valid JSON
- Well-known: `GET /.well-known/skills/index.json` returns valid JSON
- Auth flow: signup → login → browse → logout

Automated tests can be added in Phase 3 alongside community features.

---

## Security Considerations (Phase 2)

| Concern | Mitigation |
|---------|-----------|
| XSS via README content | Sanitize rendered markdown with DOMPurify |
| SQL injection | Drizzle parameterized queries (no raw SQL) |
| Auth bypass | Supabase JWT validation + RLS as defense-in-depth |
| CSRF | Hono's built-in CSRF protection or SameSite cookies |
| Telemetry abuse | Body size limit (4KB), field length limits, no PII stored |
| Domain restriction bypass | Server-side check at signup, not just client-side |
| Secrets in code | All secrets via env vars, `.env` in `.gitignore` |

Security headers (CSP, HSTS, X-Frame-Options) and rate limiting are deferred to Phase 3.

---

## Open Questions

1. **Supabase project**: Do we use the existing GG Supabase org, or create a new project for OpenForge?
2. **Seed repos**: Which repos should we seed first? The openforge repo itself (this monorepo's plugins)?
3. **Domain**: `openforge.gitguardian.com` — is DNS/Cloudflare already configured, or do we need to set that up?
4. **First admin**: How should the first admin user be created? Seed script, or manual SQL after first signup?
