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
# ┌───────────────┬──────────┐
# │               │ cli-dev  │
# │  team-lead    ├──────────┤
# │  (~45%)       │forge-dev │
# │               │          │
# └───────────────┴──────────┘

set -euo pipefail

# Auto-detect window by finding the one with a "team-lead" pane
WINDOW=""
for win in $(tmux list-windows -a -F '#{session_name}:#{window_index}'); do
    for pane_id in $(tmux list-panes -t "$win" -F '#{pane_id}' 2>/dev/null); do
        fmt=$(tmux show-options -p -t "$pane_id" -v pane-border-format 2>/dev/null || true)
        if echo "$fmt" | grep -q '"openforge:team-lead"'; then
            WINDOW="$win"
            break 2
        fi
    done
done

if [ -z "$WINDOW" ]; then
    echo "ERROR: Could not find a tmux window with an 'openforge:team-lead' pane." >&2
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

LEAD=$(discover_pane "openforge:team-lead")
CLI=$(discover_pane "openforge:cli-dev")
FORGE=$(discover_pane "openforge:forge-dev")

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
    # Lead: 40%, right column: 60% split vertically
    lead_w=$((W * 40 / 100))
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
