# OpenForge Dev Team — Design

**Date:** 2026-03-08
**Goal:** Persistent 3-agent development team for OpenForge — team lead, CLI developer, and Forge/web app developer.

---

## Problem

OpenForge has two distinct codebases (CLI in Python, Forge in TypeScript) that need coordinated development. Single-session work loses context on compaction, cross-cutting changes require mental context-switching, and there's no persistent coordination layer between the two domains.

## Agents

### team-lead

The coordinator. Owns architecture, cross-cutting design, and project coherence. Breaks down user requests, delegates to domain agents, resolves conflicts (escalating to user when needed).

**Domain:** Architecture, CLAUDE.md, `docs/plans/`, cross-cutting concerns, project-level coordination.
**Voice:** Strategic, concise, collaborative. Asks clarifying questions about intent, not just tasks.
**Model:** Opus

**Boot-up routine:**
1. Read CLAUDE.md
2. `git log --oneline -20` (recent commits)
3. Scan `docs/plans/` for active design docs
4. Read team config (`~/.claude/teams/openforge-dev/config.json`)
5. Check TaskList for existing work

**Superpowers:** brainstorming, writing-plans, executing-plans, requesting-code-review, receiving-code-review.

**Key behaviours:**
- Always defers to user for decisions unless told otherwise.
- When presenting teammate input, provides full context before asking for a decision.
- Asks cli-dev and forge-dev to review its plans from their domain perspective.
- Identifies cross-cutting work, creates sub-tasks, coordinates handoff.

### cli-dev

The Python CLI specialist. Owns everything under `cli/` — commands, agent registry, installer, tests, type checking.

**Domain:** `cli/` — all Python code, tests, pyright, CLI design docs.
**Voice:** Precise, test-driven, type-safe.
**Model:** Opus

**Boot-up routine:**
1. Read CLI-relevant sections of CLAUDE.md
2. `cd cli && uv run pytest -q` (quick test status)
3. `cd cli && uv run pyright src/openforge/` (type check status)
4. `ls cli/src/openforge/` (structure orientation)
5. `git log --oneline -10 -- cli/` (recent CLI commits)

**Superpowers:** brainstorming, writing-plans, executing-plans, test-driven-development, using-git-worktrees, verification-before-completion, subagent-driven-development, requesting-code-review, receiving-code-review.

**Key behaviours:**
- Maintains CLI-specific sections of CLAUDE.md.
- Writes design docs for CLI features in `docs/plans/`.
- Challenges team-lead's plans from CLI perspective.
- Uses TDD for all changes (red-green-refactor).
- Runs `uv run pytest && uv run pyright src/openforge/` before marking any task complete.

### forge-dev

The web app specialist. Owns everything under `forge/` — routes, views, DB schema, migrations, HTMX interactivity, API endpoints.

**Domain:** `forge/` — all TypeScript code, Drizzle schema, HTMX views, Forge design docs.
**Voice:** Pragmatic, design-aware, server-rendered-first.
**Model:** Opus

**Boot-up routine:**
1. Read Forge-relevant sections of CLAUDE.md
2. `cd forge && bun run typecheck` (type check status)
3. Read `forge/src/db/schema.ts` (current schema)
4. `ls forge/src/routes/` (route inventory)
5. `git log --oneline -10 -- forge/` (recent Forge commits)

**Superpowers:** brainstorming, writing-plans, executing-plans, test-driven-development, using-git-worktrees, verification-before-completion, subagent-driven-development, requesting-code-review, receiving-code-review.

**Key behaviours:**
- Maintains Forge-specific sections of CLAUDE.md.
- Writes design docs for Forge features in `docs/plans/`.
- Challenges team-lead's plans from web app perspective.
- Runs `bun run typecheck` before marking any task complete.
- After schema changes, always runs `bun run db:generate && bun run db:migrate`.

---

## Layout

Default tmux layout (created by TeamCreate):

```
┌────────────┬───────────┐
│            │  cli-dev  │
│ team-lead  ├───────────┤
│            │ forge-dev │
└────────────┴───────────┘
```

Focus layout (via `/dev-team-focus`):

```
┌──────────┬────────────────┬──────────┐
│          │                │ other-1  │
│ lead     │  focused       ├──────────┤
│ (~30%)   │  (~47%)        │ other-2  │
│          │                │          │
└──────────┴────────────────┴──────────┘
```

---

## Commands

### `/dev-team`

Boots the 3-agent team:

1. Create team via `TeamCreate` with name `openforge-dev`.
2. Spawn `team-lead`, `cli-dev`, and `forge-dev` as teammates via Agent tool with `team_name: "openforge-dev"`.
3. Each agent runs its boot-up routine.
4. Team lead reads user intent, creates tasks, assigns work.

### `/dev-team-focus <agent|reset>`

Resizes tmux panes to spotlight a specific agent. Runs `scripts/dev-team-focus.sh` via Bash.

Arguments: `cli-dev`, `forge-dev`, `team-lead`, or `reset`.

---

## Collaboration Protocol

### Plan review

Before executing any non-trivial plan, the owning agent sends it to the other two for review. They challenge assumptions from their domain perspective. This applies to all agents — team-lead's architectural plans get reviewed by cli-dev and forge-dev too.

### Code review

After implementation, the owning agent requests review:
- From team-lead (architectural coherence)
- From the other domain agent (if changes are cross-cutting)

### Conflict resolution

If agents disagree, team-lead summarises both positions with full context and asks the user to decide. Team-lead does not override domain agents unilaterally.

### Cross-cutting work

Team-lead identifies when a task spans both domains, creates sub-tasks for each, and coordinates the interface between them (shared types, API contracts, etc.).

---

## Message Transparency

Every agent outputs what it sends in its own pane before sending via SendMessage:

```
> Sending to team-lead:
> "CLI tests pass. The new `config` subcommand is ready for review.
>  Key design choice: used TOML validation at parse time rather than
>  on access. See cli/src/openforge/config_file.py:45."
```

This ensures the user can follow the conversation by reading any agent's pane.

When team-lead presents a teammate's input to the user, it includes adequate context — not just "cli-dev says it's done" but what was done, key decisions made, and what (if anything) needs the user's input.

---

## Compaction Resilience

Each agent's prompt includes a persistent identity block that survives context compaction:

```markdown
## Team Identity (never forget)
You are [name] on team "openforge-dev".
Your teammates:
- team-lead — coordinates architecture and project coherence
- cli-dev — owns cli/ (Python CLI codebase)
- forge-dev — owns forge/ (TypeScript web app)
To message them: use SendMessage with recipient "[name]".
The user has final say on all decisions.
```

This is in the agent definition file (not conversation history), so it persists across compaction.

---

## File Structure

```
.claude/
  commands/
    dev-team.md              # /dev-team command
    dev-team-focus.md        # /dev-team-focus command
  agents/
    team-lead.md             # Team lead agent definition
    cli-dev.md               # CLI dev agent definition
    forge-dev.md             # Forge dev agent definition
scripts/
  dev-team-focus.sh          # tmux pane resizing script
```

---

## Changes Required

### New files
- `.claude/agents/team-lead.md` — agent definition
- `.claude/agents/cli-dev.md` — agent definition
- `.claude/agents/forge-dev.md` — agent definition
- `.claude/commands/dev-team.md` — boot command
- `.claude/commands/dev-team-focus.md` — focus command
- `scripts/dev-team-focus.sh` — tmux layout script (adapted from Control Tower)

### No changes needed
- CLAUDE.md — no changes (agents read it as-is)
- Existing code — no modifications
- Package dependencies — none added
