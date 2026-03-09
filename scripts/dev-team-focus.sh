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

# --- Apply a layout using the CURRENT pane order ---
apply_layout() {
    local layout_str="$1"
    local result
    result=$(layout_checksum "$layout_str")
    tmux select-layout -t "$WINDOW" "$result"
}

# --- Get the ordered list of pane IDs as tmux sees them ---
get_pane_order() {
    tmux list-panes -t "$WINDOW" -F '#{pane_id}'
}

# --- Build layout string using current pane order ---
build_layout_ids() {
    local panes
    panes=($(get_pane_order))
    echo "${panes[0]#%} ${panes[1]#%} ${panes[2]#%}"
}

# --- Restore canonical order: lead, cli, forge ---
restore_canonical_order() {
    local canonical=("$LEAD" "$CLI" "$FORGE")
    local panes
    panes=($(get_pane_order))

    for i in 0 1 2; do
        if [ "${panes[$i]}" != "${canonical[$i]}" ]; then
            for j in $(seq $((i+1)) 2); do
                if [ "${panes[$j]}" = "${canonical[$i]}" ]; then
                    tmux swap-pane -d -s "${panes[$j]}" -t "${panes[$i]}"
                    local tmp="${panes[$i]}"
                    panes[$i]="${panes[$j]}"
                    panes[$j]="$tmp"
                    break
                fi
            done
        fi
    done
}

# --- Swap focused agent into the first agent slot (position after lead) ---
swap_to_front() {
    local target_id="$1"
    local panes
    panes=($(get_pane_order))
    local first_agent="${panes[1]}"

    if [ "$target_id" != "$first_agent" ]; then
        tmux swap-pane -d -s "$target_id" -t "$first_agent"
    fi
}

# --- Map agent name ---
agent_name="${1:-}"

if [ -z "$agent_name" ]; then
    echo "Usage: $0 <team-lead|cli-dev|forge-dev|reset>"
    exit 1
fi

case "$agent_name" in
    lead|team-lead)  FOCUS_ID="$LEAD" ;;
    cli|cli-dev)     FOCUS_ID="$CLI" ;;
    forge|forge-dev) FOCUS_ID="$FORGE" ;;
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

if [ "$agent_name" = "reset" ] || [ "$agent_name" = "lead" ] || [ "$agent_name" = "team-lead" ]; then
    # --- Reset/Lead: restore canonical order, then apply layout ---
    restore_canonical_order
    local_ids=($(build_layout_ids))
    id0=${local_ids[0]}; id1=${local_ids[1]}; id2=${local_ids[2]}

    if [ "$agent_name" = "reset" ]; then
        # Lead: 40%, right column: 60% split vertically
        lead_w=$((W * 40 / 100))
    else
        # Lead focused: 55%, right column: 45%
        lead_w=$((W * 55 / 100))
    fi

    right_w=$((W - lead_w - 1))
    top_h=$((H / 2))
    bot_h=$((H - top_h - 1))
    right_x=$((lead_w + 1))
    bot_y=$((top_h + 1))

    layout="${W}x${H},0,0{${lead_w}x${H},0,0,${id0},${right_w}x${H},${right_x},0[${right_w}x${top_h},${right_x},0,${id1},${right_w}x${bot_h},${right_x},${bot_y},${id2}]}"
    apply_layout "$layout"
    tmux select-pane -t "$LEAD"
    if [ "$agent_name" = "reset" ]; then
        echo "Reset to default layout (${W}x${H})."
    else
        echo "Focused on team-lead (${W}x${H}). Lead: 55%, agents: 45%."
    fi
else
    # --- Focus layout: 3-column ---
    # Swap the focused agent into the first agent slot, then apply layout
    swap_to_front "$FOCUS_ID"

    local_ids=($(build_layout_ids))
    id0=${local_ids[0]}; id1=${local_ids[1]}; id2=${local_ids[2]}
    # id0=lead, id1=focused agent (swapped to front), id2=other

    lead_w=$((W * 25 / 100))
    focus_w=$((W / 2))
    side_w=$((W - lead_w - focus_w - 2))

    focus_x=$((lead_w + 1))
    side_x=$((focus_x + focus_w + 1))

    layout="${W}x${H},0,0{${lead_w}x${H},0,0,${id0},${focus_w}x${H},${focus_x},0,${id1},${side_w}x${H},${side_x},0,${id2}}"
    apply_layout "$layout"
    tmux select-pane -t "$FOCUS_ID"
    echo "Focused on $agent_name (${W}x${H})."
fi
