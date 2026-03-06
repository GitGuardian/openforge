# OpenForge — Agent Instructions

Read this entire file before doing anything.

---

## What this project is

OpenForge is an open-source platform for distributing, discovering, and curating AI agent plugins and skills. It has two components:

- **The Forge** — A web app for browsing, searching, voting, discussing, and curating plugins. Serves `marketplace.json` for native Claude Code/Cowork integration and `.well-known/skills/index.json` for skills.sh compatibility.
- **CLI** — A Python tool (`uvx openforge`) for installing plugins and skills across 51 AI agents. Drop-in superset of skills.sh.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. Plugins are a superset of skills — they contain skills plus commands, hooks, MCP config, and agent definitions.

See `docs/plans/2026-03-06-openforge-platform.md` for the full PRD.
See `docs/plans/2026-03-06-openforge-architecture-design.md` for the architecture design.
See `docs/plans/2026-03-06-phase1-cli-mvp-design.md` for the Phase 1 CLI MVP design.

---

## Stack

### The Forge

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

### CLI

| Layer | Technology | Notes |
|-------|-----------|-------|
| Language | Python 3.10+ | Strictly typed (pyright strict mode). |
| Framework | Typer | CLI framework with auto-generated help. |
| Distribution | PyPI | Installed via `uvx openforge`. |
| Telemetry | JSON POST to the Forge | Fire-and-forget, disabled via `DO_NOT_TRACK=1`. |

---

## Commands

### The Forge

```bash
cd forge
bun install              # Install dependencies
bun run dev              # Start dev server with hot reload
bun run start            # Start production server
bun run db:generate      # Generate migration from schema changes
bun run db:migrate       # Apply migrations to database
bun run db:studio        # Open Drizzle Studio (database GUI)
bun run typecheck        # Run TypeScript type checking
```

### CLI

```bash
cd cli
uv sync                  # Install dependencies
uv run pytest            # Run tests
uv run pyright           # Type check (strict mode)
uv run openforge --help  # Run CLI locally
```

---

## Project structure

```
openforge/
  forge/                        # The Forge (web app, Bun + Hono)
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
        pages.ts                # HTML page routes (browse, detail, submit, admin)
        api.ts                  # JSON API (marketplace.json, telemetry, well-known)
        health.ts               # GET /health
      db/
        schema.ts               # Drizzle table definitions (with RLS)
        index.ts                # Database client
      lib/
        git.ts                  # GitHub API operations (indexing, MR creation)
        validation.ts           # Plugin/skill validation
        notifications.ts        # Slack + email
        supabase.ts             # Supabase client (auth, storage)
      views/
        layout.ts               # HTML layout (Tailwind + HTMX)
    drizzle/                    # Generated SQL migrations
    public/                     # Static files served at /public/*
  cli/                          # Python CLI (uvx openforge)
    pyproject.toml
    src/
      openforge/
        cli.py                  # Typer app, entry point
        add.py                  # add command
        remove.py               # remove command
        find_cmd.py             # find command
        list_cmd.py             # list command
        config.py               # config command
        agents/
          registry.py           # All 51 agent configs (data-driven)
          base.py               # AgentConfig dataclass + AgentAdapter protocol
          adapters/
            claude.py           # Claude Code adapter
            cursor.py           # Cursor adapter
        providers/
          base.py               # Provider protocol
          github.py             # GitHub clone + content detection
          source_parser.py      # Parse owner/repo@skill syntax
        installer.py            # Core install logic (symlink/copy, agent dispatch)
        plugins.py              # plugin.json / marketplace.json parsing
        skills.py               # SKILL.md parsing
        lock.py                 # Lock file (.openforge-lock.json)
        config_file.py          # TOML config read/write/precedence
        telemetry.py            # Fire-and-forget JSON POST
        types.py
    tests/
  docs/
    plans/                      # PRDs and design docs (YYYY-MM-DD-<name>.md)
    architecture.md
    deployment.md
    contributing.md
  .mcp.json                     # MCP servers (Railway, Supabase, Context7)
  CLAUDE.md                     # This file
  README.md
  LICENSE                       # Apache 2.0
```

---

## Rules

Follow these strictly. They prevent common failure modes.

### Forge rules

**Always use Drizzle for database queries.**
Use the Drizzle client (`forge/src/db/index.ts`) and schema (`forge/src/db/schema.ts`) for all database operations. Never write raw SQL strings in route handlers.

**Always use HTMX for interactivity.**
Do not add React, Vue, or any client-side JavaScript framework. Do not write inline `<script>` tags for interactivity. Use HTMX attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`) to make the page dynamic. The server returns HTML fragments.

**Always use Tailwind utility classes for styling.**
Do not create CSS files or `<style>` tags. Use Tailwind classes directly on HTML elements. The CDN is loaded in the layout.

**After schema changes, always run generate + migrate.**
Whenever you modify `forge/src/db/schema.ts`, run:
```bash
cd forge && bun run db:generate && bun run db:migrate
```

**Register new routes in `forge/src/index.ts`.**
After creating a new route file, import it and register with `app.route("/", yourRoutes)`. Routes won't work until registered.

**User identity comes from Supabase Auth middleware.**
Access the current user via `c.get("user")` in any route. The auth middleware in `forge/src/middleware/auth.ts` handles session validation against Supabase Auth. RLS enforces permissions at the database level.

### CLI rules

**Use Typer for all CLI commands.**
Every command is a Typer command. Use type annotations for arguments and options.

**All Python code must be strictly typed.**
Every function signature must have full type annotations (parameters and return types). Use `dataclass`, `TypedDict`, `Protocol`, and `Enum` where appropriate. No `Any` unless truly unavoidable. Run `pyright` in strict mode — the CI and `pyproject.toml` must enforce this. Prefer `from __future__ import annotations` at the top of every file.

**Agent configs are data-driven.**
All 51 agents are defined as `AgentConfig` entries in `cli/src/openforge/agents/registry.py`. Do not create separate files per agent. Only agents with capabilities beyond `skills` (Claude Code, Cursor) get adapter classes in `agents/adapters/`.

**Telemetry must never block.**
All telemetry calls are fire-and-forget. Never let a telemetry failure prevent a command from completing.

### Testing and fixing

**Use TDD red/green for all bug fixes.**
When you find a bug or a test fails:
1. **Red**: Write a failing test that reproduces the bug.
2. **Green**: Fix the code to make the test pass.
3. Verify all existing tests still pass (`uv run pytest`).
4. Verify pyright still passes (`uv run pyright src/`).
5. Only then commit the fix.

Never fix a bug without a test that covers it. Never skip the verification step.

**Run the full test suite before committing.**
Always run `cd cli && uv run pytest && uv run pyright src/openforge/` before committing any change.

### General rules

**Plans go in `docs/plans/`.**
Use the naming convention `YYYY-MM-DD-<feature-name>.md`.

**Keep this file up to date.**
When you make significant changes (new tables, new routes, new CLI commands, architectural decisions), update this file. It is the primary context for all future sessions.

---

## Key files to understand

### The Forge
- **`forge/src/index.ts`** — Entry point. All middleware and routes registered here.
- **`forge/src/db/schema.ts`** — Database schema. Source of truth for what tables exist.
- **`forge/src/views/layout.ts`** — HTML layout wrapper. All pages use this.
- **`forge/src/middleware/auth.ts`** — Supabase Auth session handling.

### CLI
- **`cli/src/openforge/cli.py`** — Typer app. All commands registered here.
- **`cli/src/openforge/agents/base.py`** — AgentConfig dataclass and AgentAdapter protocol.
- **`cli/src/openforge/agents/registry.py`** — All 51 agent definitions.
- **`cli/src/openforge/installer.py`** — Core install logic.

---

## Environment setup

### MCP servers

The project includes a `.mcp.json` that configures MCP servers for all contributors:
- **Railway** — deployment, logs, project management. Requires `RAILWAY_TOKEN`.
- **Supabase** — database management, docs. Authenticates via OAuth on first use.
- **Context7** — up-to-date library documentation.

### The Forge

1. Copy `forge/.env.example` to `forge/.env` and fill in:
   - `DATABASE_URL` — Supabase Postgres connection string
   - `SUPABASE_URL` — Supabase project URL
   - `SUPABASE_ANON_KEY` — Supabase anonymous key
   - `SUPABASE_SERVICE_ROLE_KEY` — Supabase service role key (for admin operations)
2. `cd forge && bun install`
3. `bun run db:migrate`
4. `bun run dev`

### CLI

1. `cd cli && uv sync`
2. `uv run openforge --help`

---

## Architecture decisions

- **Git is source of truth for plugin content.** The Forge indexes metadata into Postgres but never stores plugin files in the database.
- **Supabase Auth for identity.** Email/password and magic link out of the box, with optional OAuth providers. Allowed email domains are configurable by admins.
- **RLS from day one.** Row Level Security on all tables. Permissions enforced at the database level, not just application layer.
- **Single monorepo.** The Forge and CLI live in the same repo for easier coordination.
- **HTMX over SPA.** Server-rendered HTML with HTMX for interactivity. No client-side framework.
- **Canonical plugin format.** Claude Code's `.claude-plugin/` structure. The CLI adapts it per agent.
- **51-agent support.** Data-driven agent registry, drop-in compatible with skills.sh file layout.
- **Public/private modes.** Single codebase supports both open community and company-internal deployments via config toggle.
- **Telemetry architecture.** CLI sends simple JSON POST. The Forge stores in Postgres and emits OTel server-side.
- **Config precedence.** env vars > `.openforge.toml` (project) > `~/.config/openforge/config.toml` (user) > defaults.
- **First deployment.** `openforge.gitguardian.com` in private mode. Public domain TBD.
