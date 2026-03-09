# OpenForge

An open-source platform for distributing, discovering, and curating AI agent plugins and skills.

## What is this?

OpenForge lets teams manage a trusted internal catalogue of AI agent plugins, with community features (voting, discussion, install tracking) layered on top of git-backed storage.

- **The Forge** — Browse, search, vote, discuss, and curate plugins and skills.
- **CLI** (`uvx openforge`) — Install plugins and skills across 75 AI agents from a single command. Drop-in superset of skills.sh.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. The CLI adapts plugins for installation across all major AI agents.

## Status

| Phase | Status | Highlights |
|-------|--------|------------|
| 1 — CLI MVP | **Complete** | 6 commands, 261 tests, 93%+ coverage, 75 agents |
| 2 — The Forge MVP | **Complete** | Catalogue, search, auth, RLS (29 policies), seed script |
| 3 — Community Features | **Complete** | Voting, comments, sorting, CSRF, rate limiting |
| 4 — Indexing & CLI Parity | **Complete** | Webhooks, indexer, 6 providers, check/update, remote find |
| 5 — Submissions & Curation | Next | |
| 6 — Hardening | Next | Test suite done (167 tests, 92%+ coverage) |

See [docs/plans/](docs/plans/) for design documents.

## Quick Start

### CLI

```bash
uvx openforge --help           # Install and run CLI
uvx openforge add owner/repo   # Install a plugin across your AI agents
```

### The Forge (local dev)

```bash
brew install supabase/tap/supabase  # One-time: install Supabase CLI
cd forge && bun install
supabase start                      # Start local Postgres + Auth (needs Docker)
cp .env.example .env                # Fill in values from `supabase status`
bun run db:migrate
bun run seed -- --repo https://github.com/anthropics/claude-code --name anthropic
bun run dev                         # http://localhost:3000
```

## Stack

| Component | Technology |
|-----------|-----------|
| The Forge | Bun + Hono + HTMX + Tailwind |
| Database | Supabase (Postgres + RLS) |
| ORM | Drizzle |
| Auth | Supabase Auth |
| CLI | Python 3.10+ / Typer |
| CLI distribution | PyPI (`openforge`), installed via `uvx openforge` |
| Plugin storage | Git repos (source of truth) |
| Local dev | Supabase CLI (`supabase start`) |
| Hosting | Railway + Supabase |

## Licence

Apache 2.0 — see [LICENSE](LICENSE).
