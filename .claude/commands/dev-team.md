# Boot OpenForge Dev Team

Launch the 3-agent development team: team-lead (you), cli-dev, and forge-dev.

## Instructions

### 1. Create the team

`TeamCreate` with `team_name: "openforge-dev"`, `description: "OpenForge development team — team-lead + cli-dev + forge-dev"`.

### 2. You ARE team-lead

The current session becomes the team lead when TeamCreate runs. Do NOT spawn a separate team-lead agent — that would create a duplicate. Read the team-lead agent definition at `.claude/agents/team-lead.md` and adopt its identity, boot-up routine, and behaviour.

### 3. Create initial tasks (optional)

- If the user provided a task/goal with this command, create tasks via `TaskCreate` describing the work.
- If no task was given, that's fine — ask the user what they'd like to work on after boot-up.

### 4. Spawn cli-dev and forge-dev

Use the Agent tool with `team_name: "openforge-dev"` for each. Both in a single message. Use `mode: "bypassPermissions"` for both.

- Spawn `cli-dev` (agent type: `cli-dev`) with prompt: "You have been spawned as cli-dev on the openforge-dev team. Run your boot-up routine now, then check TaskList for work and wait for assignments from team-lead."
- Spawn `forge-dev` (agent type: `forge-dev`) with prompt: "You have been spawned as forge-dev on the openforge-dev team. Run your boot-up routine now, then check TaskList for work and wait for assignments from team-lead."

### 5. Set pane titles and layout

Run the setup script to label all panes and apply the default layout:

```bash
bash scripts/dev-team-setup.sh
```

This discovers pane IDs, sets descriptive `pane-border-format` titles ("team-lead", "cli-dev - Python CLI", "forge-dev - Forge web app"), and applies a 45%/55% split layout.

### 6. Run your own boot-up routine (from `.claude/agents/team-lead.md`)

- Read `CLAUDE.md`
- `git log --oneline -20`
- `ls docs/plans/`
- Read team config
- Check TaskList

### 7. Wait for teammates and summarise

Wait for cli-dev and forge-dev to report ready. Present a compact summary to the user:

```
Dev team ready.
- team-lead: [status]
- cli-dev: [tests] | [pyright] | [git]
- forge-dev: [typecheck] | [git]
```

Then ask what the user would like to work on (unless a task was already provided).

### 8. Ongoing coordination

- Create tasks with `TaskCreate` for each unit of work.
- Assign via `TaskUpdate` with `owner` set to the agent name.
- For cross-cutting changes: coordinate the sequence (e.g., update shared types first, then update consumers).
- **Do NOT shut down the team or idle agents unless the user explicitly asks.** Keep agents available between tasks.
