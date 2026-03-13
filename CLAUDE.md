# OpenForge — Agent Instructions

Read this entire file before doing anything.

---

## What this project is

OpenForge is an open-source platform for distributing, discovering, and curating AI agent plugins and skills. It has two components:

- **The Forge** — A web app for browsing, searching, voting, discussing, and curating plugins. Serves `marketplace.json` for native Claude Code/Cowork integration and `.well-known/skills/index.json` for skills.sh compatibility.
- **CLI** — A Python tool (`uvx openforge`) for installing plugins and skills across 75 AI agents. Drop-in superset of skills.sh.

The canonical plugin format is Claude Code's `.claude-plugin/` structure. Plugins are a superset of skills — they contain skills plus commands, hooks, MCP config, and agent definitions.

Design docs and plans are in `docs/plans/` (named `YYYY-MM-DD-<topic>.md`).

---

## Component Instructions

Each component has its own CLAUDE.md with stack, commands, rules, and key files:
- **The Forge:** See `forge/CLAUDE.md`
- **CLI:** See `cli/CLAUDE.md`

---

## Project Structure

```
openforge/
  forge/          # The Forge (web app) — see forge/CLAUDE.md
  cli/            # Python CLI — see cli/CLAUDE.md
  docs/plans/     # Design docs and implementation plans
  .claude/        # Hooks, agents, commands
  .mcp.json       # MCP servers (Railway, Supabase, Context7)
```

Detailed file trees are in `forge/CLAUDE.md` and `cli/CLAUDE.md`.

---

## Rules

Component-specific rules are in `forge/CLAUDE.md` and `cli/CLAUDE.md`. The rules below apply project-wide.

### General rules

**Incremental delivery — steel thread first.**
Always implement as a "tracer bullet" (The Pragmatic Programmer): build the thinnest functional path through the entire system first, then widen it. Every phase and feature starts with a walking skeleton that touches all layers (DB → API → UI or DB → API → CLI), then iterates to add richness. Never build one layer to completion before connecting the next.

**Plans go in `docs/plans/`.**
Use the naming convention `YYYY-MM-DD-<feature-name>.md`.

**Keep this file up to date.**
When you make significant changes (new tables, new routes, new CLI commands, architectural decisions), update this file. It is the primary context for all future sessions.

---

## Architecture decisions

- Git is source of truth for plugin content (Forge indexes metadata, never stores files)
- Supabase Auth (email/password, magic link, OAuth) | RLS on all tables
- HTMX over SPA | Canonical plugin format: `.claude-plugin/`
- 75-agent support, data-driven registry, skills.sh compatible
- Public/private modes via config toggle
- Config precedence: env > `.openforge.toml` > `~/.config/openforge/config.toml` > defaults
- Two plugin ingestion paths: **webhook auto-indexing** (trusted, auto-approved) and **community submissions** (untrusted, requires curator review)
- CLI auth uses Supabase GoTrue REST API directly (no SDK dependency). Token stored at `~/.config/openforge/token.json` with 0o600 permissions
- Security hardening (Phase 6): auth rate limiting (IP+email keyed), atomic file writes, path traversal protection, SSRF prevention, XSS escaping, HMAC optimization, symlink protection. See component CLAUDE.md files for details.

---

## Testing Architecture

Three-tier hybrid testing pyramid for both Forge and CLI:

- **Tier 1 — Unit:** Fast, mocked, in-process. `bun test` (Forge) / `pytest` (CLI)
- **Tier 2 — Integration:** Real HTTP against local Forge+Supabase via `fetch()` (Forge) / `respx` transport mocking (CLI)
- **Tier 3 — E2E:** Playwright browser tests via Node.js (Forge) / subprocess smoke tests (CLI)

CI target: <60s total. Playwright runs via `npx` (NOT Bun — incompatible). Setup: `scripts/test-e2e-setup.sh`.
