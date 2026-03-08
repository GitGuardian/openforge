# Shutdown OpenForge Dev Team

Gracefully shut down the 3-agent development team, preserving state.

## Instructions

### 1. Announce shutdown

Tell the user you're initiating a graceful shutdown. Briefly summarise any in-progress work.

### 2. Instruct agents to wrap up

Send a message to both cli-dev and forge-dev with the following (adapt as needed):

> "Team shutdown initiated. Before exiting, please:
> 1. If you have any uncommitted work, commit it now (do NOT push unless the user told you to).
> 2. Update your CLAUDE.md (`cli/CLAUDE.md` or `forge/CLAUDE.md`) with any significant changes from this session (new routes, schema changes, new commands, architectural decisions, etc.).
> 3. Update your auto-memory files with any insights, patterns, or decisions worth preserving.
> 4. Report back what you committed and updated."

### 3. Wait for agents to report, then shut them down

Wait for both agents to report back. If an agent has no changes, that's fine.

Once each agent reports back, send a `shutdown_request` to them via `SendMessage` (type: `"shutdown_request"`). Wait for both to confirm shutdown.

### 4. Update root CLAUDE.md

If any cross-cutting changes were made during this session (new architecture decisions, project structure changes, etc.), update the root `CLAUDE.md`.

### 5. Update team-lead memory

Update your own auto-memory files with:
- Session summary (what was accomplished)
- Any open tasks or follow-ups
- Decisions made during the session

### 6. Final commit (if needed)

If you or the agents made CLAUDE.md or memory updates during shutdown, commit them:
```
chore: update CLAUDE.md and memory files (dev team shutdown)
```

Do NOT push unless the user explicitly asks.

### 7. Reset team-lead pane title

Clear the `pane-border-format` set by the dev-team-setup script so the pane reverts to default:

```bash
tmux set-option -p -t "$TMUX_PANE" -u pane-border-format
```

### 8. Present shutdown summary

Show the user:

```
Dev team shutdown complete.
- cli-dev: [what was committed/updated, or "no changes"]
- forge-dev: [what was committed/updated, or "no changes"]
- team-lead: [what was committed/updated, or "no changes"]

Uncommitted work: [none / list any]
Unpushed commits: [count]
```

### 9. Delete the team

After both agents have confirmed shutdown, clean up team resources:

```
TeamDelete
```

This removes the team config and task list directories.
