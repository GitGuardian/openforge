# Boot OpenForge Dev Team

Launch the 3-agent development team: team-lead (you), cli-dev, and forge-dev.

**The dev team is persistent.** Once booted, the team stays running indefinitely — across tasks, idle periods, and conversation compactions. Never shut down the team or any agent unless the user explicitly asks (e.g., `/dev-team-shutdown`). Do not auto-shutdown after completing work.

## Instructions

### 1. Clean up any existing team

If an `openforge-dev` team already exists (from a crashed or stale session), clean it up first:
1. Check if `~/.claude/teams/openforge-dev/config.json` exists.
2. If it does, send `shutdown_request` to any active members, then call `TeamDelete`.
3. If `TeamDelete` fails due to ghost members (agents whose panes died), manually remove the stale member entries from the config JSON and retry `TeamDelete`.

### 2. Create the team

`TeamCreate` with `team_name: "openforge-dev"`, `description: "OpenForge development team — team-lead + cli-dev + forge-dev"`.

### 3. You ARE team-lead

The current session becomes the team lead when TeamCreate runs. Do NOT spawn a separate team-lead agent — that would create a duplicate. Read the team-lead agent definition at `.claude/agents/team-lead.md` and adopt its identity, boot-up routine, and behaviour.

### 4. Create initial tasks (optional)

- If the user provided a task/goal with this command, create tasks via `TaskCreate` describing the work.
- If no task was given, that's fine — ask the user what they'd like to work on after boot-up.

### 5. Spawn cli-dev and forge-dev

Use the Agent tool with `team_name: "openforge-dev"` for each. Both in a single message. Use `mode: "bypassPermissions"` for both.

- Spawn `cli-dev` (agent type: `cli-dev`) with prompt: "You have been spawned as cli-dev on the openforge-dev team. First `cd cli` to set your working directory. Then run your boot-up routine, check TaskList for work, and wait for assignments from team-lead."
- Spawn `forge-dev` (agent type: `forge-dev`) with prompt: "You have been spawned as forge-dev on the openforge-dev team. First `cd forge` to set your working directory. Then run your boot-up routine, check TaskList for work, and wait for assignments from team-lead."

### 6. Set pane titles and layout

Run the setup script to label all panes and apply the default layout:

```bash
bash scripts/dev-team-setup.sh
```

This discovers pane IDs, sets descriptive `pane-border-format` titles ("team-lead", "cli-dev - Python CLI", "forge-dev - Forge web app"), and applies a 45%/55% split layout.

### 7. Run your own boot-up routine (from `.claude/agents/team-lead.md`)

- Read `CLAUDE.md`
- `git log --oneline -20`
- `ls docs/plans/`
- Read team config
- Check TaskList

### 8. Wait for teammates and summarise

Wait for cli-dev and forge-dev to report ready. Present a compact summary to the user:

```
Dev team ready.
- team-lead: [status]
- cli-dev: [tests] | [pyright] | [git]
- forge-dev: [typecheck] | [git]
```

Then ask what the user would like to work on (unless a task was already provided).

### 9. Respawning a crashed agent

If an agent crashes or needs to be replaced mid-session, follow this exact sequence:

1. **Remove the stale config entry first** — edit `~/.claude/teams/openforge-dev/config.json` to remove the dead agent's member entry. Do NOT send shutdown requests to dead agents — queued messages persist by name and will hit the replacement.
2. **Kill the stale tmux pane** — `tmux kill-pane -t <pane_id>` for the dead agent's pane.
3. **Spawn the replacement** — use the Agent tool with the same `name` and `subagent_type`.
4. **Re-run `bash scripts/dev-team-setup.sh`** — this re-labels all panes (including the new one) and fixes the layout.

**Never** send `shutdown_request` to an agent that is already dead — the message will queue and kill the replacement.

### 10. Research and exploration

**Always delegate research to forge-dev or cli-dev** based on the domain. Do NOT spawn ad-hoc exploration agents — use the team you already have.

### 11. Ongoing coordination

- Create tasks with `TaskCreate` for each unit of work.
- Assign via `TaskUpdate` with `owner` set to the agent name.
- For cross-cutting changes: coordinate the sequence (e.g., update shared types first, then update consumers).
- **Do NOT shut down the team or idle agents unless the user explicitly asks.** Keep agents available between tasks.
