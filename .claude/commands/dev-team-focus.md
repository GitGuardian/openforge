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
