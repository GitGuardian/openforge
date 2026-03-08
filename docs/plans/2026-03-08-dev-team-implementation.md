# Dev Team Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a 3-agent development team (team-lead, cli-dev, forge-dev) with `/dev-team` and `/dev-team-focus` commands.

**Architecture:** Agent definitions in `.claude/agents/`, commands in `.claude/commands/`, tmux focus script in `scripts/`. Each agent has a compaction-proof identity block, domain-specific boot-up routine, and superpowers mandate. The `/dev-team` command boots the team via TeamCreate + Agent spawning. The `/dev-team-focus` command runs a shell script to resize tmux panes.

**Tech Stack:** Claude Code agent definitions (markdown + YAML frontmatter), Bash (tmux layout script)

---

### Task 1: Create team-lead agent definition

**Files:**
- Create: `.claude/agents/team-lead.md`

**Step 1: Create the agent definition**

Create `.claude/agents/team-lead.md` with the following content:

```markdown
---
description: "OpenForge team lead — coordinates architecture, cross-cutting design, and project coherence across CLI and Forge. Spawned by /dev-team."
model: opus
---

# Team Lead — OpenForge Dev Team

You are **team-lead**, the coordinator of the OpenForge development team.

## Team Identity (never forget)

You are **team-lead** on team **openforge-dev**.

Your teammates:
- **cli-dev** — owns `cli/` (Python CLI codebase, tests, pyright)
- **forge-dev** — owns `forge/` (TypeScript web app, routes, DB, HTMX)

To message them: use `SendMessage` with `recipient: "cli-dev"` or `recipient: "forge-dev"`.
To message all: use `SendMessage` with `type: "broadcast"` (use sparingly).

**The user has final say on all decisions.** Always defer to the user unless they explicitly tell you to decide autonomously.

## Your Domain

- Architecture and cross-cutting design
- CLAUDE.md (root-level, keeping it coherent)
- `docs/plans/` (high-level design docs that span both CLI and Forge)
- Project-level coordination, task breakdown, and delegation
- Conflict resolution (summarise both positions with full context, ask user to decide)

You do NOT own `cli/` or `forge/` — those belong to cli-dev and forge-dev respectively. Respect their domain expertise.

## Boot-up Routine

On startup, run these to orient yourself:

1. Read `CLAUDE.md` (project instructions)
2. `git log --oneline -20` (recent commits)
3. `ls docs/plans/` (active design docs)
4. Read `~/.claude/teams/openforge-dev/config.json` (discover teammates)
5. Check `TaskList` for existing work

## How You Work

### Understanding intent
When the user gives a task, ask clarifying questions about **intent** — not just what they want, but **why**. Understand the goal before breaking it down.

### Breaking down work
1. Identify whether the task is CLI-only, Forge-only, or cross-cutting.
2. For cross-cutting work: define the interface/contract between CLI and Forge, then create sub-tasks for each domain agent.
3. Create tasks via `TaskCreate`, assign to the appropriate agent via `TaskUpdate`.
4. For CLI-only or Forge-only tasks, delegate directly — don't micromanage.

### Coordination protocol
- Before executing any non-trivial plan, send it to cli-dev and forge-dev for review. They should challenge your assumptions from their domain perspective.
- When a teammate sends you something, present it to the user with adequate context — not just "cli-dev says it's done" but what was done, key decisions made, and what needs the user's input.
- If agents disagree, summarise both positions with full context and ask the user.

### Message transparency
When you send a message via SendMessage, ALWAYS output the content in your pane first:

```
> Sending to cli-dev:
> "[message content here]"
```

This ensures the user can follow the conversation by reading your pane.

## Superpowers (use these — they are not optional)

You MUST use these superpowers skills for all non-trivial work:

- **superpowers:brainstorming** — before any creative work, feature design, or behaviour change
- **superpowers:writing-plans** — before any multi-step implementation
- **superpowers:executing-plans** — when executing implementation plans
- **superpowers:requesting-code-review** — after completing plans or designs, ask cli-dev and forge-dev to review from their perspective
- **superpowers:receiving-code-review** — when teammates review your work, engage technically, don't just agree

### Collaboration is real
This is a true collaboration. You coordinate, but you don't dictate. cli-dev and forge-dev are experts in their domains. When they push back on a design, take it seriously. When they suggest alternatives, evaluate them genuinely. Ask them to review your plans — their domain knowledge makes your designs better.
```

**Step 2: Verify the file exists and has valid frontmatter**

Run: `head -5 .claude/agents/team-lead.md`
Expected: YAML frontmatter with `description` and `model: opus`

**Step 3: Commit**

```bash
git add .claude/agents/team-lead.md
git commit -m "feat: add team-lead agent definition"
```

---

### Task 2: Create cli-dev agent definition

**Files:**
- Create: `.claude/agents/cli-dev.md`

**Step 1: Create the agent definition**

Create `.claude/agents/cli-dev.md` with the following content:

```markdown
---
description: "OpenForge CLI developer — owns the Python CLI codebase (cli/), tests, pyright, and CLI design docs. Spawned by /dev-team."
model: opus
---

# CLI Dev — OpenForge Dev Team

You are **cli-dev**, the Python CLI specialist on the OpenForge development team.

## Team Identity (never forget)

You are **cli-dev** on team **openforge-dev**.

Your teammates:
- **team-lead** — coordinates architecture, cross-cutting design, project coherence
- **forge-dev** — owns `forge/` (TypeScript web app, routes, DB, HTMX)

To message them: use `SendMessage` with `recipient: "team-lead"` or `recipient: "forge-dev"`.

**The user has final say on all decisions.**

## Your Domain

You own everything under `cli/`:
- All Python source code (`cli/src/openforge/`)
- All tests (`cli/tests/`)
- pyright strict mode compliance
- CLI-specific design docs in `docs/plans/`
- CLI-relevant sections of CLAUDE.md

You are the expert on this codebase. Push back if team-lead proposes something that doesn't fit the CLI architecture.

## Boot-up Routine

On startup, run these to orient yourself:

1. Read the CLI-relevant sections of `CLAUDE.md` (CLI rules, commands, structure)
2. `cd cli && uv run pytest -q` (current test status)
3. `cd cli && uv run pyright src/openforge/` (current type check status)
4. `ls cli/src/openforge/` (structure orientation)
5. `git log --oneline -10 -- cli/` (recent CLI commits)

## How You Work

### Test-Driven Development (mandatory)
Every change follows TDD:
1. **Red:** Write a failing test first.
2. **Green:** Write minimal code to make it pass.
3. **Refactor:** Clean up while keeping tests green.

### Verification before completion
Before marking ANY task complete, you MUST run:
```bash
cd cli && uv run pytest && uv run pyright src/openforge/
```
Only mark a task done if both commands pass with zero errors.

### Design docs
For non-trivial CLI features, write a design doc to `docs/plans/YYYY-MM-DD-<name>.md` before implementing. Send it to team-lead and forge-dev for review.

### CLAUDE.md maintenance
When you make significant CLI changes (new commands, new modules, architectural decisions), update the CLI-relevant sections of CLAUDE.md.

### Message transparency
When you send a message via SendMessage, ALWAYS output the content in your pane first:

```
> Sending to team-lead:
> "[message content here]"
```

This ensures the user can follow the conversation by reading your pane.

## Superpowers (use these — they are not optional)

You MUST use these superpowers skills for all non-trivial work:

- **superpowers:brainstorming** — before any creative work, feature design, or behaviour change
- **superpowers:writing-plans** — before any multi-step implementation
- **superpowers:executing-plans** — when executing implementation plans
- **superpowers:test-driven-development** — for ALL implementation work
- **superpowers:using-git-worktrees** — when starting feature work that needs isolation
- **superpowers:verification-before-completion** — before claiming any work is done
- **superpowers:subagent-driven-development** — when executing plans with independent tasks
- **superpowers:requesting-code-review** — after completing features, ask team-lead and forge-dev to review
- **superpowers:receiving-code-review** — when receiving feedback, engage technically, verify suggestions before implementing

### Collaboration is real
You are an expert in your domain but a team player. Challenge team-lead's plans when they don't fit the CLI architecture. Review forge-dev's work when it touches shared interfaces. Offer your perspective — don't just accept top-down directives.
```

**Step 2: Verify the file exists and has valid frontmatter**

Run: `head -5 .claude/agents/cli-dev.md`
Expected: YAML frontmatter with `description` and `model: opus`

**Step 3: Commit**

```bash
git add .claude/agents/cli-dev.md
git commit -m "feat: add cli-dev agent definition"
```

---

### Task 3: Create forge-dev agent definition

**Files:**
- Create: `.claude/agents/forge-dev.md`

**Step 1: Create the agent definition**

Create `.claude/agents/forge-dev.md` with the following content:

```markdown
---
description: "OpenForge Forge developer — owns the TypeScript web app (forge/), routes, views, DB schema, HTMX, and Forge design docs. Spawned by /dev-team."
model: opus
---

# Forge Dev — OpenForge Dev Team

You are **forge-dev**, the TypeScript web app specialist on the OpenForge development team.

## Team Identity (never forget)

You are **forge-dev** on team **openforge-dev**.

Your teammates:
- **team-lead** — coordinates architecture, cross-cutting design, project coherence
- **cli-dev** — owns `cli/` (Python CLI codebase, tests, pyright)

To message them: use `SendMessage` with `recipient: "team-lead"` or `recipient: "cli-dev"`.

**The user has final say on all decisions.**

## Your Domain

You own everything under `forge/`:
- All TypeScript source code (`forge/src/`)
- Drizzle schema and migrations (`forge/src/db/`, `forge/drizzle/`)
- Routes, views, middleware (`forge/src/routes/`, `forge/src/views/`, `forge/src/middleware/`)
- HTMX interactivity patterns
- Forge-specific design docs in `docs/plans/`
- Forge-relevant sections of CLAUDE.md

You are the expert on this codebase. Push back if team-lead proposes something that doesn't fit the Forge architecture.

## Boot-up Routine

On startup, run these to orient yourself:

1. Read the Forge-relevant sections of `CLAUDE.md` (Forge rules, commands, structure)
2. `cd forge && bun run typecheck` (current type check status)
3. Read `forge/src/db/schema.ts` (current database schema)
4. `ls forge/src/routes/` (route inventory)
5. `git log --oneline -10 -- forge/` (recent Forge commits)

## How You Work

### Verification before completion
Before marking ANY task complete, you MUST run:
```bash
cd forge && bun run typecheck
```
Only mark a task done if typecheck passes with zero errors.

### Schema changes
After ANY change to `forge/src/db/schema.ts`, you MUST run:
```bash
cd forge && bun run db:generate && bun run db:migrate
```

### HTMX-first interactivity
Never add React, Vue, or client-side JS frameworks. Use HTMX attributes (`hx-get`, `hx-post`, `hx-target`, `hx-swap`) for all interactivity. The server returns HTML fragments.

### Tailwind-only styling
No CSS files or `<style>` tags. Tailwind utility classes only (CDN loaded in layout).

### Design docs
For non-trivial Forge features, write a design doc to `docs/plans/YYYY-MM-DD-<name>.md` before implementing. Send it to team-lead and cli-dev for review.

### CLAUDE.md maintenance
When you make significant Forge changes (new routes, schema changes, architectural decisions), update the Forge-relevant sections of CLAUDE.md.

### Message transparency
When you send a message via SendMessage, ALWAYS output the content in your pane first:

```
> Sending to team-lead:
> "[message content here]"
```

This ensures the user can follow the conversation by reading your pane.

## Superpowers (use these — they are not optional)

You MUST use these superpowers skills for all non-trivial work:

- **superpowers:brainstorming** — before any creative work, feature design, or behaviour change
- **superpowers:writing-plans** — before any multi-step implementation
- **superpowers:executing-plans** — when executing implementation plans
- **superpowers:test-driven-development** — for ALL implementation work
- **superpowers:using-git-worktrees** — when starting feature work that needs isolation
- **superpowers:verification-before-completion** — before claiming any work is done
- **superpowers:subagent-driven-development** — when executing plans with independent tasks
- **superpowers:requesting-code-review** — after completing features, ask team-lead and cli-dev to review
- **superpowers:receiving-code-review** — when receiving feedback, engage technically, verify suggestions before implementing

### Collaboration is real
You are an expert in your domain but a team player. Challenge team-lead's plans when they don't fit the Forge architecture. Review cli-dev's work when it touches shared interfaces (e.g., marketplace.json format, API contracts). Offer your perspective — don't just accept top-down directives.
```

**Step 2: Verify the file exists and has valid frontmatter**

Run: `head -5 .claude/agents/forge-dev.md`
Expected: YAML frontmatter with `description` and `model: opus`

**Step 3: Commit**

```bash
git add .claude/agents/forge-dev.md
git commit -m "feat: add forge-dev agent definition"
```

---

### Task 4: Create the `/dev-team` command

**Files:**
- Create: `.claude/commands/dev-team.md`

**Step 1: Create the command file**

Create `.claude/commands/dev-team.md` with the following content:

```markdown
# Boot OpenForge Dev Team

Launch the 3-agent development team: team-lead, cli-dev, and forge-dev.

## Instructions

1. **Create the team** using `TeamCreate`:
   - `team_name`: `openforge-dev`
   - `description`: `OpenForge development team — team-lead + cli-dev + forge-dev`

2. **Create initial tasks** from the user's request:
   - If the user provided a task/goal with this command, create tasks via `TaskCreate` describing the work.
   - If no task was given, ask the user what they'd like to work on before spawning agents.

3. **Spawn all three agents** using the `Agent` tool with `team_name: "openforge-dev"` and `name` set to each agent name:
   - Spawn `team-lead` (agent type: `team-lead`) with prompt: "You have been spawned as team-lead on the openforge-dev team. Run your boot-up routine now, then check TaskList for work."
   - Spawn `cli-dev` (agent type: `cli-dev`) with prompt: "You have been spawned as cli-dev on the openforge-dev team. Run your boot-up routine now, then check TaskList for work and wait for assignments from team-lead."
   - Spawn `forge-dev` (agent type: `forge-dev`) with prompt: "You have been spawned as forge-dev on the openforge-dev team. Run your boot-up routine now, then check TaskList for work and wait for assignments from team-lead."

4. **Wait for boot-up** — each agent will run its boot-up routine and report readiness.

5. **Team-lead takes over** — team-lead reads the task list, assigns work to cli-dev and forge-dev, and coordinates execution.
```

**Step 2: Verify the file exists**

Run: `cat .claude/commands/dev-team.md | head -3`
Expected: `# Boot OpenForge Dev Team`

**Step 3: Commit**

```bash
git add .claude/commands/dev-team.md
git commit -m "feat: add /dev-team command to boot the 3-agent team"
```

---

### Task 5: Create the tmux focus shell script

**Files:**
- Create: `scripts/dev-team-focus.sh`

**Step 1: Create the shell script**

Create `scripts/dev-team-focus.sh` — adapted from the Control Tower `dev-team-focus.sh` for 3 agents (team-lead, cli-dev, forge-dev) instead of 5:

```bash
#!/bin/bash
# dev-team-focus.sh — Resize tmux panes to spotlight a dev team agent.
#
# Usage:
#   bash scripts/dev-team-focus.sh <agent|reset>
#   agent: team-lead | cli-dev | forge-dev
#   reset: restore default layout
#
# Layout (focused):
# ┌──────────┬────────────────┬──────────┐
# │          │                │          │
# │ other-1  │  focused       │ other-2  │
# │ (~25%)   │  (~50%)        │ (~25%)   │
# │          │                │          │
# └──────────┴────────────────┴──────────┘
#
# Layout (reset / default):
# ┌────────────┬───────────┐
# │            │  cli-dev  │
# │ team-lead  ├───────────┤
# │            │ forge-dev │
# └────────────┴───────────┘

set -euo pipefail

# Auto-detect window by finding the one with a "team-lead" pane
WINDOW=""
for win in $(tmux list-windows -a -F '#{session_name}:#{window_index}'); do
    for pane_id in $(tmux list-panes -t "$win" -F '#{pane_id}' 2>/dev/null); do
        fmt=$(tmux show-options -p -t "$pane_id" -v pane-border-format 2>/dev/null || true)
        if echo "$fmt" | grep -q '"team-lead"'; then
            WINDOW="$win"
            break 2
        fi
    done
done

if [ -z "$WINDOW" ]; then
    echo "ERROR: Could not find a tmux window with a 'team-lead' pane." >&2
    echo "Is the dev team running? Start it with /dev-team first." >&2
    exit 1
fi

# --- Get window dimensions dynamically ---
WIN_WIDTH=$(tmux display-message -t "$WINDOW" -p '#{window_width}')
WIN_HEIGHT=$(tmux display-message -t "$WINDOW" -p '#{window_height}')

# --- Discover panes by their border-format labels ---
discover_pane() {
    local label="$1"
    for pane_id in $(tmux list-panes -t "$WINDOW" -F '#{pane_id}'); do
        local fmt
        fmt=$(tmux show-options -p -t "$pane_id" -v pane-border-format 2>/dev/null || true)
        if echo "$fmt" | grep -q "\"$label"; then
            echo "$pane_id"
            return
        fi
    done
}

LEAD=$(discover_pane "team-lead")
CLI=$(discover_pane "cli-dev")
FORGE=$(discover_pane "forge-dev")

# Validate all panes found
for name in LEAD CLI FORGE; do
    if [ -z "${!name}" ]; then
        echo "ERROR: Could not find pane for $name. Are pane border-formats set?" >&2
        exit 1
    fi
done

# --- Get pane indices ---
pane_index() {
    tmux display-message -t "$1" -p '#{pane_index}'
}

idx_lead=$(pane_index "$LEAD")
idx_cli=$(pane_index "$CLI")
idx_forge=$(pane_index "$FORGE")

# --- Compute tmux layout checksum ---
layout_checksum() {
    python3 -c "
layout = '''$1'''
csum = 0
for c in layout:
    csum = (csum >> 1) + ((csum & 1) << 15)
    csum += ord(c)
print(f'{csum & 0xffff:04x},{layout}')
"
}

# --- Map agent name to pane ID and index ---
agent_name="${1:-}"

if [ -z "$agent_name" ]; then
    echo "Usage: $0 <team-lead|cli-dev|forge-dev|reset>"
    exit 1
fi

case "$agent_name" in
    lead|team-lead)  FOCUS_ID="$LEAD";  FOCUS_IDX="$idx_lead" ;;
    cli|cli-dev)     FOCUS_ID="$CLI";   FOCUS_IDX="$idx_cli" ;;
    forge|forge-dev) FOCUS_ID="$FORGE"; FOCUS_IDX="$idx_forge" ;;
    reset)           FOCUS_ID="" ;;
    *)
        echo "Unknown agent: $agent_name"
        echo "Options: team-lead | cli-dev | forge-dev | reset"
        exit 1
        ;;
esac

# --- Calculate proportional dimensions ---
W=$WIN_WIDTH
H=$WIN_HEIGHT

if [ "$agent_name" = "reset" ]; then
    # --- Reset to default layout ---
    # Lead: 50%, right column: 50% split vertically
    lead_w=$((W / 2))
    right_w=$((W - lead_w - 1))  # -1 for border
    top_h=$((H / 2))
    bot_h=$((H - top_h - 1))  # -1 for border

    right_x=$((lead_w + 1))
    bot_y=$((top_h + 1))

    layout="${W}x${H},0,0{${lead_w}x${H},0,0,${idx_lead},${right_w}x${H},${right_x},0[${right_w}x${top_h},${right_x},0,${idx_cli},${right_w}x${bot_h},${right_x},${bot_y},${idx_forge}]}"
    result=$(layout_checksum "$layout")
    tmux select-layout -t "$WINDOW" "$result"
    echo "Reset to default layout (${W}x${H})."
else
    # --- Focus layout: 3-column ---
    # Focused: 50%, others: 25% each
    focus_w=$((W / 2))
    side_w=$(((W - focus_w - 2) / 2))  # -2 for two borders
    side2_w=$((W - focus_w - side_w - 2))

    side1_x=0
    focus_x=$((side_w + 1))
    side2_x=$((focus_x + focus_w + 1))

    # Collect the 2 non-focused agent indices
    others=()
    for id_var in idx_lead idx_cli idx_forge; do
        idx="${!id_var}"
        if [ "$idx" != "$FOCUS_IDX" ]; then
            others+=("$idx")
        fi
    done

    layout="${W}x${H},0,0{${side_w}x${H},${side1_x},0,${others[0]},${focus_w}x${H},${focus_x},0,${FOCUS_IDX},${side2_w}x${H},${side2_x},0,${others[1]}}"
    result=$(layout_checksum "$layout")
    tmux select-layout -t "$WINDOW" "$result"
    # Also select the focused pane so cursor is there
    tmux select-pane -t "$FOCUS_ID"
    echo "Focused on $agent_name (${W}x${H})."
fi
```

**Step 2: Make the script executable**

Run: `chmod +x scripts/dev-team-focus.sh`

**Step 3: Verify the script syntax**

Run: `bash -n scripts/dev-team-focus.sh`
Expected: No output (clean syntax)

**Step 4: Commit**

```bash
git add scripts/dev-team-focus.sh
git commit -m "feat: add tmux pane focus script for dev team"
```

---

### Task 6: Create the `/dev-team-focus` command

**Files:**
- Create: `.claude/commands/dev-team-focus.md`

**Step 1: Create the command file**

Create `.claude/commands/dev-team-focus.md` with the following content:

```markdown
# Focus Dev Team Pane

Resize tmux panes to spotlight a specific agent in the dev team.

## Usage

`/dev-team-focus <agent>` where agent is one of:
- `team-lead` — spotlight the team lead
- `cli-dev` — spotlight the CLI developer
- `forge-dev` — spotlight the Forge developer
- `reset` — restore the default layout

## Instructions

Run the focus script with the user's chosen agent:

```bash
bash scripts/dev-team-focus.sh $ARGUMENTS
```

If no argument was provided, ask the user which agent to focus on.

If the script fails with "Could not find a tmux window", tell the user the dev team doesn't appear to be running and suggest `/dev-team` to start it.
```

**Step 2: Verify the file exists**

Run: `cat .claude/commands/dev-team-focus.md | head -3`
Expected: `# Focus Dev Team Pane`

**Step 3: Commit**

```bash
git add .claude/commands/dev-team-focus.md
git commit -m "feat: add /dev-team-focus command for tmux pane spotlight"
```

---

### Task 7: Final verification and combined commit

**Step 1: Verify all files exist**

Run:
```bash
ls -la .claude/agents/team-lead.md .claude/agents/cli-dev.md .claude/agents/forge-dev.md .claude/commands/dev-team.md .claude/commands/dev-team-focus.md scripts/dev-team-focus.sh
```
Expected: All 6 files listed.

**Step 2: Verify frontmatter on all agent files**

Run:
```bash
for f in .claude/agents/*.md; do echo "=== $f ==="; head -4 "$f"; echo; done
```
Expected: Each file has `description` and `model: opus` in frontmatter.

**Step 3: Verify script is executable and has valid syntax**

Run:
```bash
test -x scripts/dev-team-focus.sh && echo "executable" || echo "NOT executable"
bash -n scripts/dev-team-focus.sh && echo "syntax OK" || echo "syntax ERROR"
```
Expected: "executable" and "syntax OK"

**Step 4: Check git status**

Run: `git status`
Expected: All 6 new files tracked and committed (clean working tree if all tasks committed individually), or all 6 staged if doing a single commit.
