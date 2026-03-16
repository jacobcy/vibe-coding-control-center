#!/usr/bin/env zsh
# lib/roadmap_status.sh - Roadmap status command
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_store.sh" ]] && source "$VIBE_LIB/roadmap_store.sh"
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_dependency.sh" ]] && source "$VIBE_LIB/roadmap_dependency.sh"

_vibe_roadmap_status() {
    local common_dir roadmap_file output_json="false"
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

    common_dir="$(_vibe_roadmap_common_dir)" || return 1
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1
    local status_json
    status_json="$(jq -c '{
        project_id: .project_id,
        version_goal: .version_goal,
        counts: {
            p0: ([.items[]? | objects | select(.status == "p0")] | length),
            current: ([.items[]? | objects | select(.status == "current")] | length),
            next: ([.items[]? | objects | select(.status == "next")] | length),
            deferred: ([.items[]? | objects | select(.status == "deferred")] | length),
            rejected: ([.items[]? | objects | select(.status == "rejected")] | length)
        },
        official_layer: {
            total_items: ([.items[]? | objects] | length),
            mirrored_items: ([.items[]? | objects | select(.github_project_item_id != null)] | length),
            with_github_project_item_id: ([.items[]? | objects | select(.github_project_item_id != null)] | length),
            with_content_type: ([.items[]? | objects | select(.content_type != null)] | length),
            remote_only_imports: ([.items[]? | objects
              | select(.source_type == "github")
              | select(.github_project_item_id != null)
              | select((.execution_record_id == null) and ((.linked_task_ids // []) | length == 0))
            ] | length)
        },
        sync_check: {
            missing_project_id: (if (.project_id // null) == null then 1 else 0 end),
            missing_github_project_item_id: ([.items[]? | objects | select(.github_project_item_id == null)] | length),
            missing_content_type: ([.items[]? | objects | select(.content_type == null)] | length)
        },
        extension_layer: {
            with_execution_record_id: ([.items[]? | objects | select(.execution_record_id != null)] | length),
            with_spec_standard: ([.items[]? | objects | select((.spec_standard // "none") != "none")] | length),
            with_spec_ref: ([.items[]? | objects | select(.spec_ref != null)] | length)
        }
    } | .sync_check += {
        recommended: ((.sync_check.missing_project_id > 0) or (.sync_check.missing_github_project_item_id > 0) or (.sync_check.missing_content_type > 0)),
        recommended_command: "vibe roadmap sync --provider github --json"
    }' "$roadmap_file")"
    status_json="$(_vibe_roadmap_status_with_dependency_counts "$common_dir" "$roadmap_file" "$status_json")"
    if [[ "$output_json" == "true" ]]; then
        print -r -- "$status_json"
        return 0
    fi
    local version_goal project_id counts p0_count current_count next_count deferred_count rejected_count
    local official_counts official_total official_mirrored official_item_id official_content_type official_remote_only
    local sync_counts sync_missing_item_id sync_missing_content_type sync_recommended sync_command
    local extension_counts extension_execution extension_spec_standard extension_spec_ref
    version_goal="$(echo "$status_json" | jq -r '.version_goal // empty' | grep -v '^null$' || echo "none")"
    project_id="$(echo "$status_json" | jq -r '.project_id // "none"')"

    echo "========================================"
    echo "         $(_vibe_roadmap_format "$BOLD" "Roadmap Status")"
    echo "========================================"
    echo ""
    echo "Version Goal: $(_vibe_roadmap_format "$CYAN" "$version_goal")"
    echo "Project ID:   $(_vibe_roadmap_format "$CYAN" "$project_id")"
    echo ""
    echo "Roadmap Item Summary:"
    counts="$(echo "$status_json" | jq -r '"\(.counts.p0) \(.counts.current) \(.counts.next) \(.counts.deferred) \(.counts.rejected)"')"
    IFS=' ' read -r p0_count current_count next_count deferred_count rejected_count <<< "$counts"

    if _vibe_roadmap_supports_color; then
        printf "  %-16s  %b\n" "P0 (urgent):" "$(_vibe_roadmap_color_status "p0") ($p0_count)"
        printf "  %-16s  %b\n" "Current:" "$(_vibe_roadmap_color_status "current") ($current_count)"
        printf "  %-16s  %b\n" "Next:" "$(_vibe_roadmap_color_status "next") ($next_count)"
        printf "  %-16s  %b\n" "Deferred:" "$(_vibe_roadmap_color_status "deferred") ($deferred_count)"
        printf "  %-16s  %b\n" "Rejected:" "$(_vibe_roadmap_color_status "rejected") ($rejected_count)"
    else
        echo "  P0 (urgent):      $p0_count"
        echo "  Current:          $current_count"
        echo "  Next:             $next_count"
        echo "  Deferred:         $deferred_count"
        echo "  Rejected:         $rejected_count"
    fi
    echo ""
    _vibe_roadmap_render_dependency_summary "$status_json"
    official_counts="$(echo "$status_json" | jq -r '"\(.official_layer.total_items) \(.official_layer.mirrored_items) \(.official_layer.with_github_project_item_id) \(.official_layer.with_content_type) \(.official_layer.remote_only_imports)"')"
    IFS=' ' read -r official_total official_mirrored official_item_id official_content_type official_remote_only <<< "$official_counts"
    echo "GitHub Project Mirror:"
    echo "  Total Items:       $official_total"
    echo "  Mirrored Items:    $official_mirrored"
    echo "  Project Item IDs:  $official_item_id"
    echo "  Content Types:     $official_content_type"
    echo "  Remote-only Imports: $official_remote_only"
    echo ""

    sync_counts="$(echo "$status_json" | jq -r '"\(.sync_check.missing_project_id) \(.sync_check.missing_github_project_item_id) \(.sync_check.missing_content_type) \(.sync_check.recommended)"')"
    IFS=' ' read -r sync_missing_project_id sync_missing_item_id sync_missing_content_type sync_recommended sync_command <<< "$sync_counts"
    sync_command="$(echo "$status_json" | jq -r '.sync_check.recommended_command')"
    if [[ "$sync_recommended" == "true" ]]; then
        echo "$(_vibe_roadmap_format "$YELLOW" "Roadmap sync recommended before relying on GitHub Projects coverage.")"
        echo "  Missing Project ID:       $sync_missing_project_id"
        echo "  Missing Project Item IDs: $sync_missing_item_id"
        echo "  Missing Content Types:    $sync_missing_content_type"
        echo "  Next: $sync_command"
        echo ""
    fi
    extension_counts="$(echo "$status_json" | jq -r '"\(.extension_layer.with_execution_record_id) \(.extension_layer.with_spec_standard) \(.extension_layer.with_spec_ref)"')"
    IFS=' ' read -r extension_execution extension_spec_standard extension_spec_ref <<< "$extension_counts"
    echo "Local Execution Bridge:"
    echo "  Execution Records: $extension_execution"
    echo "  Spec Standards:    $extension_spec_standard"
    echo "  Spec Refs:         $extension_spec_ref"
    echo ""

    if [[ "$version_goal" == "none" ]]; then
        echo "$(_vibe_roadmap_format "$YELLOW" "No version goal set. Run 'vibe roadmap assign' to set one.")"
    fi
}
