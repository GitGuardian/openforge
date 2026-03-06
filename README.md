# OpenForge

An open-source platform for distributing, discovering, and curating AI agent plugins and skills.

## What is this?

OpenForge lets teams manage a trusted internal catalogue of AI agent plugins, with community features (voting, discussion, install tracking) layered on top of git-backed storage.

- **The Forge** — Browse, search, vote, discuss, and curate plugins and skills.
- **CLI** (`uvx openforge`) — Install plugins and skills across 51 AI agents from a single command. Drop-in superset of skills.sh.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. The CLI adapts plugins for installation across all major AI agents.

## Status

Early development. See [docs/plans/](docs/plans/) for design documents:
- [PRD](docs/plans/2026-03-06-openforge-platform.md) — full product requirements
- [Architecture Design](docs/plans/2026-03-06-openforge-architecture-design.md) — system architecture
- [Phase 1 CLI MVP Design](docs/plans/2026-03-06-phase1-cli-mvp-design.md) — first implementation target

## Stack

| Component | Technology |
|-----------|-----------|
| The Forge | Bun + Hono + HTMX + Tailwind |
| Database | Supabase (Postgres + RLS) |
| ORM | Drizzle |
| Auth | Supabase Auth |
| CLI | Python + Typer |
| CLI distribution | PyPI (`openforge`), installed via `uvx openforge` |
| Plugin storage | Git repos |
| Hosting | Railway + Supabase |

## Licence

Apache 2.0 — see [LICENSE](LICENSE).
