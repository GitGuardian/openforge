# OpenForge

An open-source platform for distributing, discovering, and curating AI agent plugins and skills.

## What is this?

OpenForge lets teams manage a trusted internal catalogue of AI agent plugins, with community features (voting, discussion, install tracking) layered on top of git-backed storage.

- **Portal** — Browse, search, vote, discuss, and curate plugins and skills.
- **CLI** — Install plugins across multiple agents from a single command.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. The CLI adapts plugins for installation across Claude Code, Claude Desktop/Cowork, Cursor, Codex CLI, OpenCode, Gemini CLI, and others.

## Status

Early development. See [tasks/prd-openforge-platform.md](tasks/prd-openforge-platform.md) for the full product requirements document.

## Stack

| Component | Technology |
|-----------|-----------|
| Portal | Bun + Hono + HTMX + Tailwind |
| Database | Postgres (Supabase compatible) |
| ORM | Drizzle |
| CLI | Python + Typer |
| CLI distribution | PyPI (`openforge`), installed via `uvx openforge` |
| Plugin storage | Git repos |

## Licence

TBD
