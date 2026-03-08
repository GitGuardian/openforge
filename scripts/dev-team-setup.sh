#!/bin/bash
# dev-team-setup.sh — Set pane titles and default layout for the OpenForge dev team.
#
# Usage:
#   bash scripts/dev-team-setup.sh
#
# Call this AFTER spawning cli-dev and forge-dev agents via /dev-team.
# It discovers panes, sets descriptive pane-border-format on each,
# and applies the default layout.
#
# Discovery: The lead pane is the active pane (running this script).
# The other two panes are agents in spawn order: cli-dev (first), forge-dev (second).
#
# Default layout:
# ┌───────────────┬──────────┐
# │               │ cli-dev  │
# │  team-lead    ├──────────┤
# │  (~45%)       │forge-dev │
# │               │          │
# └───────────────┴──────────┘

set -euo pipefail

# --- Discover lead pane ---
# Use $TMUX_PANE (the pane this shell runs in), NOT display-message -p
# (which returns the *active* pane, which may have shifted when agents were spawned).
LEAD="${TMUX_PANE}"

if [ -z "$LEAD" ]; then
    echo "ERROR: \$TMUX_PANE is not set. Are you running inside tmux?" >&2
    exit 1
fi

# Verify the pane actually exists
if ! tmux display-message -t "$LEAD" -p '#{pane_id}' &>/dev/null; then
    echo "ERROR: Pane $LEAD does not exist. \$TMUX_PANE may be stale." >&2
    exit 1
fi

# --- Find the window containing the lead pane ---
WINDOW=$(tmux display-message -t "$LEAD" -p '#{session_name}:#{window_index}')

# --- Get window dimensions ---
W=$(tmux display-message -t "$WINDOW" -p '#{window_width}')
H=$(tmux display-message -t "$WINDOW" -p '#{window_height}')

# The other panes are agents, ordered by pane index (spawn order).
# cli-dev was spawned first, forge-dev second.
AGENTS=()
for pane_id in $(tmux list-panes -t "$WINDOW" -F '#{pane_id}'); do
    if [ "$pane_id" != "$LEAD" ]; then
        AGENTS+=("$pane_id")
    fi
done

if [ "${#AGENTS[@]}" -lt 2 ]; then
    echo "ERROR: Expected 2 agent panes, found ${#AGENTS[@]}." >&2
    echo "Make sure cli-dev and forge-dev are spawned before running this script." >&2
    exit 1
fi

CLI="${AGENTS[0]}"
FORGE="${AGENTS[1]}"

echo "Discovered panes: lead=$LEAD cli=$CLI forge=$FORGE"

# --- Set pane-border-format (descriptive titles) ---
# Use pane-border-format, NOT pane_title — Claude Code overwrites pane_title.
tmux set-option -p -t "$LEAD" pane-border-format '#{?pane_active,#[reverse],}#{pane_index}#[default] "openforge:team-lead"'
tmux set-option -p -t "$CLI" pane-border-format '#{?pane_active,#[reverse],}#{pane_index}#[default] "openforge:cli-dev - Python CLI"'
tmux set-option -p -t "$FORGE" pane-border-format '#{?pane_active,#[reverse],}#{pane_index}#[default] "openforge:forge-dev - Forge web app"'

echo "Pane titles set."

# --- Get pane indices for layout ---
idx_lead=$(tmux display-message -t "$LEAD" -p '#{pane_index}')
idx_cli=$(tmux display-message -t "$CLI" -p '#{pane_index}')
idx_forge=$(tmux display-message -t "$FORGE" -p '#{pane_index}')

# --- Compute layout checksum ---
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

# --- Apply default layout: lead 45%, right column 55% split vertically ---
lead_w=$((W * 45 / 100))
right_w=$((W - lead_w - 1))  # -1 for border
top_h=$((H / 2))
bot_h=$((H - top_h - 1))  # -1 for border

right_x=$((lead_w + 1))
bot_y=$((top_h + 1))

layout="${W}x${H},0,0{${lead_w}x${H},0,0,${idx_lead},${right_w}x${H},${right_x},0[${right_w}x${top_h},${right_x},0,${idx_cli},${right_w}x${bot_h},${right_x},${bot_y},${idx_forge}]}"
result=$(layout_checksum "$layout")
tmux select-layout -t "$WINDOW" "$result"

# Select the lead pane
tmux select-pane -t "$LEAD"

echo "Default layout applied (${W}x${H}). team-lead: 45%, cli-dev + forge-dev: 55%."
