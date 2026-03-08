# OpenForge — Agent Instructions

Read this entire file before doing anything.

---

## What this project is

OpenForge is an open-source platform for distributing, discovering, and curating AI agent plugins and skills. It has two components:

- **The Forge** — A web app for browsing, searching, voting, discussing, and curating plugins. Serves `marketplace.json` for native Claude Code/Cowork integration and `.well-known/skills/index.json` for skills.sh compatibility.
- **CLI** — A Python tool (`uvx openforge`) for installing plugins and skills across 75 AI agents. Drop-in superset of skills.sh.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. Plugins are a superset of skills — they contain skills plus commands, hooks, MCP config, and agent definitions.

See `docs/plans/2026-03-06-openforge-platform.md` for the full PRD.
See `docs/plans/2026-03-06-openforge-architecture-design.md` for the architecture design.
See `docs/plans/2026-03-06-phase1-cli-mvp-design.md` for the Phase 1 CLI MVP design.
See `docs/plans/2026-03-06-phase2-forge-mvp-design.md` for the Phase 2 Forge MVP design.
See `docs/plans/2026-03-08-phase3-community-features-design.md` for the Phase 3 Community Features design.
See `docs/plans/2026-03-08-phase3-community-features-implementation.md` for the Phase 3 implementation plan.
See `docs/plans/2026-03-08-phase4-automated-indexing-design.md` for the Phase 4 Automated Indexing & CLI Parity design.
See `docs/plans/2026-03-08-phase4-implementation.md` for the Phase 4 implementation plan.

---

## Component Instructions

Each component has its own CLAUDE.md with stack, commands, rules, and key files:
- **The Forge:** See `forge/CLAUDE.md`
- **CLI:** See `cli/CLAUDE.md`

---

## Project Structure

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
        pages.ts                # HTML page routes (catalogue, detail)
        api.ts                  # JSON API (marketplace.json, telemetry, well-known)
        auth.ts                 # Auth routes (login, signup, magic-link, logout)
        health.ts               # GET /health
        webhooks.ts             # GitHub webhook receiver (HMAC-SHA256)
      db/
        schema.ts               # Drizzle table definitions (8 tables)
        index.ts                # Database client
      lib/
        markdown.ts             # Markdown rendering (marked + DOMPurify)
        supabase.ts             # Supabase client (auth, storage)
        indexer.ts              # Reusable indexing library (extracted from seed.ts)
      views/
        layout.ts               # HTML layout (Tailwind + HTMX, auth-aware nav)
      scripts/
        seed.ts                 # Seed database from git repos
    drizzle/                    # Generated SQL migrations
    supabase/                   # Local Supabase config (supabase init)
    public/                     # Static files served at /public/*
  cli/                          # Python CLI (uvx openforge)
    pyproject.toml
    src/
      openforge/
        cli.py                  # Typer app, entry point, --version flag
        add.py                  # add command (provider dispatch)
        remove.py               # remove command
        find_cmd.py             # find command (--remote, --all for Forge search)
        list_cmd.py             # list command
        check.py                # check command (staleness detection via git ls-remote)
        update.py               # update command (re-fetch outdated entries)
        config.py               # config command
        agents/
          registry.py           # All 75 agent configs (data-driven)
          base.py               # AgentConfig dataclass + AgentAdapter protocol
          adapters/
            claude.py           # Claude Code adapter
            cursor.py           # Cursor adapter
        providers/
          base.py               # Provider protocol + FetchResult
          github.py             # Legacy GitHub provider
          git.py                # Git provider (GitHub, GitLab, SSH, generic)
          local.py              # Local path provider
          wellknown.py          # Well-known URL provider (RFC 8615)
          forge.py              # Forge API provider (remote find + install)
          source_parser.py      # Parse sources (owner/repo, GitLab, SSH, local, #branch, well-known, forge:)
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
  .mcp.json                     # MCP servers (Railway, Supabase, Context7)
  CLAUDE.md                     # This file
  README.md
  LICENSE                       # Apache 2.0
```

---

## Rules

Component-specific rules are in `forge/CLAUDE.md` and `cli/CLAUDE.md`. The rules below apply project-wide.

### General rules

**Plans go in `docs/plans/`.**
Use the naming convention `YYYY-MM-DD-<feature-name>.md`.

**Keep this file up to date.**
When you make significant changes (new tables, new routes, new CLI commands, architectural decisions), update this file. It is the primary context for all future sessions.

---

## Key Files

Component-specific key files are listed in `forge/CLAUDE.md` and `cli/CLAUDE.md`.

---

## Environment Setup

### MCP servers

The project includes a `.mcp.json` that configures MCP servers for all contributors:
- **Railway** — deployment, logs, project management. Requires `RAILWAY_TOKEN`.
- **Supabase** — database management, docs. Authenticates via OAuth on first use.
- **Context7** — up-to-date library documentation.

Component-specific environment setup is in `forge/CLAUDE.md` and `cli/CLAUDE.md`.

---

## Architecture decisions

- **Git is source of truth for plugin content.** The Forge indexes metadata into Postgres but never stores plugin files in the database.
- **Supabase Auth for identity.** Email/password and magic link out of the box, with optional OAuth providers. Allowed email domains are configurable by admins.
- **RLS from day one.** Row Level Security on all tables. Permissions enforced at the database level, not just application layer.
- **Single monorepo.** The Forge and CLI live in the same repo for easier coordination.
- **HTMX over SPA.** Server-rendered HTML with HTMX for interactivity. No client-side framework.
- **Canonical plugin format.** Claude Code's `.claude-plugin/` structure. The CLI adapts it per agent.
- **75-agent support.** Data-driven agent registry, drop-in compatible with skills.sh file layout.
- **Public/private modes.** Single codebase supports both open community and company-internal deployments via config toggle.
- **Telemetry architecture.** CLI sends simple JSON POST. The Forge stores in Postgres and emits OTel server-side.
- **Config precedence.** env vars > `.openforge.toml` (project) > `~/.config/openforge/config.toml` (user) > defaults.
- **First deployment.** `openforge.gitguardian.com` in private mode. Public domain TBD.
