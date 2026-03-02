#!/usr/bin/env zsh
# scripts/openspec_bridge.sh - Bridges OpenSpec changes into Vibe Tasks
# Usage: 
#   <vibe-json> | openspec_bridge.sh merge
#   openspec_bridge.sh find <task-id>

set -e

# --- Command: Find ---
if [[ "$1" == "find" ]]; then
    target_id="$2"
    [[ -n "$target_id" ]] || exit 1
    
    if [[ -d "openspec/changes/$target_id" ]]; then
        # Check if openspec is available to get rich status
        if command -v openspec >/dev/null 2>&1; then
            status_json=$(openspec status --json --change "$target_id" 2>/dev/null || true)
            if [[ -n "$status_json" ]]; then
                echo "$status_json" | jq -c --arg cid "$target_id" '{
                    task_id: $cid,
                    title: ("[OpenSpec] " + .changeName),
                    status: (if .isComplete then "completed" else "in_progress" end),
                    framework: "openspec",
                    source_path: ("openspec/changes/" + $cid),
                    next_step: (.artifacts | map(select(.status != "ready")) | .[0].id // "Apply change")
                }'
                exit 0
            fi
        fi
        # Fallback if no rich status
        echo "{\"task_id\":\"$target_id\",\"title\":\"$target_id\",\"status\":\"todo\",\"framework\":\"openspec\"}"
        exit 0
    fi
    exit 1
fi

# --- Command: Merge ---
[[ "$1" == "merge" ]] || exit 0

VIBE_JSON=$(cat)
if ! command -v openspec >/dev/null 2>&1; then
    echo "$VIBE_JSON"
    exit 0
fi

OPEN_SPEC_CHANGES_DIR="openspec/changes"
[[ -d "$OPEN_SPEC_CHANGES_DIR" ]] || { echo "$VIBE_JSON"; exit 0; }

OS_TASKS="[]"
for cid in "$OPEN_SPEC_CHANGES_DIR"/*(N/); do
    change_id=$(basename "$cid")
    [[ "$change_id" == "archive" ]] && continue
    
    status_json=$(openspec status --json --change "$change_id" 2>/dev/null || true)
    [[ -z "$status_json" ]] && continue
    
    mapped_task=$(echo "$status_json" | jq -c --arg cid "$change_id" '{
        task_id: $cid,
        title: ("[OpenSpec] " + .changeName),
        status: (if .isComplete then "completed" else "in_progress" end),
        framework: "openspec",
        source_path: ("openspec/changes/" + $cid),
        next_step: (.artifacts | map(select(.status != "ready")) | .[0].id // "Apply change")
    }')
    OS_TASKS=$(echo "$OS_TASKS" | jq -c --argjson t "$mapped_task" '. += [$t]')
done

echo "$VIBE_JSON" | jq --argjson ost "$OS_TASKS" '
    .tasks = ( (.tasks + $ost) | unique_by(.task_id) )
'
