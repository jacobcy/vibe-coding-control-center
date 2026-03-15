#!/usr/bin/env zsh
# lib/roadmap_show.sh - Roadmap show command
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_store.sh" ]] && source "$VIBE_LIB/roadmap_store.sh"
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_dependency.sh" ]] && source "$VIBE_LIB/roadmap_dependency.sh"

_vibe_roadmap_show() {
    local common_dir="$1" item_id="$2" output_json="false" roadmap_file item_json
    [[ $# -ge 2 ]] && shift 2 || shift $#

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_json="true"
                shift
                ;;
            *)
                echo "Error: Unknown option: $1"
                return 1
                ;;
        esac
    done

    [[ -n "$item_id" ]] || { echo "Usage: vibe roadmap show <roadmap-item-id> [--json]"; return 1; }

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1
    item_json="$(jq -c --arg id "$item_id" '.items[]? | objects | select(.roadmap_item_id == $id)' "$roadmap_file" | head -n 1)"
    [[ -n "$item_json" ]] || { echo "Error: roadmap item not found: $item_id"; return 1; }

    # Compute dependency status
    local dependency_status
    dependency_status="$(_vibe_roadmap_compute_dependency_status "$common_dir" "$item_id")"

    if [[ "$output_json" == "true" ]]; then
        print -r -- "$item_json" | jq -c --argjson dep_status "$dependency_status" '. + {dependency_status: $dep_status}'
        return 0
    fi

    # Read fields
    local id title item_status source description tasks issues updated
    id=$(print -r -- "$item_json" | jq -r '.roadmap_item_id')
    title=$(print -r -- "$item_json" | jq -r '.title')
    item_status=$(print -r -- "$item_json" | jq -r '.status')
    source=$(print -r -- "$item_json" | jq -r '.source_type')
    description=$(print -r -- "$item_json" | jq -r '.description // ""')
    tasks=$(print -r -- "$item_json" | jq -r '.linked_task_ids | join(", ")')
    issues=$(print -r -- "$item_json" | jq -r '.issue_refs | join(", ")')
    updated=$(print -r -- "$item_json" | jq -r '.updated_at')

    local colored_status
    colored_status=$(_vibe_roadmap_color_status "$item_status")

    echo "Roadmap Item: $(_vibe_roadmap_format "${CYAN}${BOLD}" "$id")"
    echo "----------------------------------------"
    echo "Title:       $(_vibe_roadmap_format "$BOLD" "$title")"
    echo "Status:      ${colored_status}"
    echo "Source:      ${source}"
    echo "Updated:     ${updated}"
    echo ""

    _vibe_roadmap_render_item_dependency_status "$dependency_status"

    if [[ -n "$description" ]]; then
        echo "Description:"
        echo "  ${description}"
        echo ""
    fi
    if [[ -n "$tasks" ]]; then
        echo "Linked Tasks:"
        echo "  ${tasks}"
    fi
    if [[ -n "$issues" ]]; then
        echo "Issue Refs:"
        echo "  ${issues}"
    fi
}
