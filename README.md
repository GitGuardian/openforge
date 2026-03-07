# OpenForge

An open-source platform for distributing, discovering, and curating AI agent plugins and skills.

## What is this?

OpenForge lets teams manage a trusted internal catalogue of AI agent plugins, with community features (voting, discussion, install tracking) layered on top of git-backed storage.

- **The Forge** — Browse, search, vote, discuss, and curate plugins and skills.
- **CLI** (`uvx openforge`) — Install plugins and skills across 75 AI agents from a single command. Drop-in superset of skills.sh.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. The CLI adapts plugins for installation across all major AI agents.

## Status

- **Phase 1 (CLI MVP)** — Complete. 188 tests, 93%+ coverage, 0 pyright errors.
- **Phase 2 (The Forge MVP)** — In progress. Web app with catalogue, search, auth, seed script.

See [docs/plans/](docs/plans/) for design documents:
- [PRD](docs/plans/2026-03-06-openforge-platform.md) — full product requirements
- [Architecture Design](docs/plans/2026-03-06-openforge-architecture-design.md) — system architecture
- [Phase 1 CLI MVP Design](docs/plans/2026-03-06-phase1-cli-mvp-design.md) — CLI implementation
- [Phase 2 Forge MVP Design](docs/plans/2026-03-06-phase2-forge-mvp-design.md) — web app implementation

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
