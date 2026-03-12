#!/usr/bin/env zsh
# lib/roadmap_query.sh - Read/Query operations for Roadmap module
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_store.sh" ]] && source "$VIBE_LIB/roadmap_store.sh"

# Compute dependency status for a roadmap item
_vibe_roadmap_compute_dependency_status() {
    local common_dir="$1" item_id="$2"
    local roadmap_file registry_file

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    registry_file="$common_dir/vibe/registry.json"

    # Get depends_on_item_ids for this item
    local depends_on
    depends_on="$(jq -r --arg id "$item_id" '.items[]? | select(.roadmap_item_id == $id) | .depends_on_item_ids // []' "$roadmap_file")"

    # If no dependencies, item is ready
    if [[ "$(echo "$depends_on" | jq 'length')" -eq 0 ]]; then
        jq -n '{ready: true, blocked: false, blockers: []}'
        return 0
    fi

    # Check each dependency and collect blockers
    local blockers_json
    blockers_json="$(echo "$depends_on" | jq -r '.[]' | while read -r dep_id; do
        # Check if dependency has a merged PR
        local dep_task_json dep_pr_status

        # Find task linked to this roadmap item with PR (get full JSON object)
        dep_task_json="$(jq -c --arg rid "$dep_id" '
            .tasks[]? | select((.roadmap_item_ids // []) | index($rid)) | select(.pr_ref != null)
        ' "$registry_file" 2>/dev/null | head -n 1)"

        if [[ -z "$dep_task_json" ]]; then
            # No task with PR found for this dependency
            jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "missing_pr_ref"}'
        else
            # Check PR status
            dep_pr_status="$(echo "$dep_task_json" | jq -r '.pr_status // "open"')"
            if [[ "$dep_pr_status" != "merged" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "pr_not_merged"}'
            fi
        fi
    done | jq -s '. | map(select(. != null))')"

    # If blockers is empty or null, item is ready
    if [[ -z "$blockers_json" || "$blockers_json" == "null" ]]; then
        jq -n '{ready: true, blocked: false, blockers: []}'
    else
        local blocker_count
        blocker_count="$(echo "$blockers_json" | jq 'length')"
        if [[ "$blocker_count" -eq 0 ]]; then
            jq -n '{ready: true, blocked: false, blockers: []}'
        else
            echo "$blockers_json" | jq -c '{ready: false, blocked: true, blockers: .}'
        fi
    fi
}

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
            p0: ([.items[]? | select(.status == "p0")] | length),
            current: ([.items[]? | select(.status == "current")] | length),
            next: ([.items[]? | select(.status == "next")] | length),
            deferred: ([.items[]? | select(.status == "deferred")] | length),
            rejected: ([.items[]? | select(.status == "rejected")] | length)
        },
        official_layer: {
            total_items: ([.items[]?] | length),
            mirrored_items: ([.items[]? | select(.github_project_item_id != null)] | length),
            with_github_project_item_id: ([.items[]? | select(.github_project_item_id != null)] | length),
            with_content_type: ([.items[]? | select(.content_type != null)] | length),
            remote_only_imports: ([.items[]?
              | select(.source_type == "github")
              | select(.github_project_item_id != null)
              | select((.execution_record_id == null) and ((.linked_task_ids // []) | length == 0))
            ] | length)
        },
        sync_check: {
            missing_project_id: (if (.project_id // null) == null then 1 else 0 end),
            missing_github_project_item_id: ([.items[]? | select(.github_project_item_id == null)] | length),
            missing_content_type: ([.items[]? | select(.content_type == null)] | length)
        },
        extension_layer: {
            with_execution_record_id: ([.items[]? | select(.execution_record_id != null)] | length),
            with_spec_standard: ([.items[]? | select((.spec_standard // "none") != "none")] | length),
            with_spec_ref: ([.items[]? | select(.spec_ref != null)] | length)
        }
    } | .sync_check += {
        recommended: ((.sync_check.missing_project_id > 0) or (.sync_check.missing_github_project_item_id > 0) or (.sync_check.missing_content_type > 0)),
        recommended_command: "vibe roadmap sync --provider github --json"
    }' "$roadmap_file")"

    # Add dependency counts
    local dependency_ready dependency_blocked dep_status
    dependency_ready=0
    dependency_blocked=0

    # Count ready/blocked items
    while IFS= read -r item_id; do
        dep_status="$(_vibe_roadmap_compute_dependency_status "$common_dir" "$item_id")"
        if [[ "$(echo "$dep_status" | jq -r '.ready')" == "true" ]]; then
            ((dependency_ready++))
        else
            ((dependency_blocked++))
        fi
    done < <(jq -r '.items[].roadmap_item_id' "$roadmap_file")

    status_json="$(echo "$status_json" | jq -c --argjson ready "$dependency_ready" --argjson blocked "$dependency_blocked" '
        . + {dependency_counts: {ready: $ready, blocked: $blocked}}
    ')"

    if [[ "$output_json" == "true" ]]; then
        echo "$status_json"
        return 0
    fi

    local version_goal project_id counts p0_count current_count next_count deferred_count rejected_count
    local official_counts official_total official_mirrored official_item_id official_content_type official_remote_only
    local sync_counts sync_missing_item_id sync_missing_content_type sync_recommended sync_command
    local extension_counts extension_execution extension_spec_standard extension_spec_ref
    version_goal="$(echo "$status_json" | jq -r '.version_goal // "none"')"
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

    # Display dependency summary
    local dep_ready dep_blocked
    dep_ready="$(echo "$status_json" | jq -r '.dependency_counts.ready')"
    dep_blocked="$(echo "$status_json" | jq -r '.dependency_counts.blocked')"

    echo "Dependency Status:"
    if _vibe_roadmap_supports_color; then
        printf "  %-16s  %b\n" "Ready:" "$(_vibe_roadmap_format "$GREEN" "($dep_ready)")"
        printf "  %-16s  %b\n" "Blocked:" "$(_vibe_roadmap_format "$RED" "($dep_blocked)")"
    else
        echo "  Ready:           $dep_ready"
        echo "  Blocked:         $dep_blocked"
    fi
    echo ""

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

_vibe_roadmap_list() {
    local common_dir="$1" output_json="false" status_filter="" source_filter="" keywords="" linked="false" unlinked="false" roadmap_file
    shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_json="true"
                shift
                ;;
            --status)
                status_filter="$2"
                shift 2
                ;;
            --source)
                source_filter="$2"
                shift 2
                ;;
            --keywords)
                keywords="$2"
                shift 2
                ;;
            --linked)
                linked="true"
                shift
                ;;
            --unlinked)
                unlinked="true"
                shift
                ;;
            *)
                echo "Error: Unknown option: $1"
                return 1
                ;;
        esac
    done

    [[ "$linked" == "true" && "$unlinked" == "true" ]] && {
        echo "Error: --linked and --unlinked cannot be used together"
        return 1
    }

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1

    local items_json
    items_json="$(jq -c \
        --arg status "$status_filter" \
        --arg source "$source_filter" \
        --arg keywords "${keywords:l}" \
        --argjson linked "$linked" \
        --argjson unlinked "$unlinked" \
        '[.items[]?
          | select(
              ($status == "" or .status == $status)
              and ($source == "" or .source_type == $source)
              and ($keywords == "" or ((.roadmap_item_id + " " + .title + " " + (.description // "")) | ascii_downcase | contains($keywords)))
              and (($linked | not) or ((.linked_task_ids | length) > 0))
              and (($unlinked | not) or ((.linked_task_ids | length) == 0))
            )]' \
        "$roadmap_file")"

    if [[ "$output_json" == "true" ]]; then
        echo "$items_json"
        return 0
    fi

    if [[ "$(print -r -- "$items_json" | jq 'length')" == "0" ]]; then
        echo "No roadmap items found."
        return 0
    fi

    local first_group="true" group_status group_items group_count row rid title
    local -a ordered_statuses=(p0 current next deferred rejected)

    for group_status in "${ordered_statuses[@]}"; do
        group_items="$(print -r -- "$items_json" | jq -c --arg status "$group_status" '[.[] | select(.status == $status)]')"
        group_count="$(print -r -- "$group_items" | jq 'length')"
        [[ "$group_count" == "0" ]] && continue

        if [[ "$first_group" == "true" ]]; then
            first_group="false"
        else
            printf '\n'
        fi

        printf '%s\n' "$(_vibe_roadmap_group_heading "$group_status" "$group_count")"
        print -r -- "$group_items" | jq -c '.[]' | while read -r row; do
            rid=$(print -r -- "$row" | jq -r '.roadmap_item_id')
            title=$(print -r -- "$row" | jq -r '.title')

            if [[ "$title" == "$rid" || -z "$title" ]]; then
                printf '  %s\n' "$rid"
            else
                printf '  %s  %s\n' "$rid" "$title"
            fi
        done
    done
}

_vibe_roadmap_show() {
    local common_dir="$1" item_id="$2" output_json="false" roadmap_file item_json
    shift 2

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
    item_json="$(jq -c --arg id "$item_id" '.items[]? | select(.roadmap_item_id == $id)' "$roadmap_file" | head -n 1)"
    [[ -n "$item_json" ]] || { echo "Error: roadmap item not found: $item_id"; return 1; }

    # Compute dependency status
    local dependency_status
    dependency_status="$(_vibe_roadmap_compute_dependency_status "$common_dir" "$item_id")"

    if [[ "$output_json" == "true" ]]; then
        echo "$item_json" | jq -c --argjson dep_status "$dependency_status" '. + {dependency_status: $dep_status}'
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

    # Display dependency status
    local dep_ready dep_blocked dep_blockers
    dep_ready="$(echo "$dependency_status" | jq -r '.ready')"
    dep_blocked="$(echo "$dependency_status" | jq -r '.blocked')"
    dep_blockers="$(echo "$dependency_status" | jq -r '.blockers')"

    if [[ "$dep_ready" == "true" ]]; then
        echo "Dependency Status: $(_vibe_roadmap_format "$GREEN" "ready")"
    else
        echo "Dependency Status: $(_vibe_roadmap_format "$RED" "blocked")"
        echo ""
        echo "Blockers:"
        echo "$dep_blockers" | jq -r '.[] | "  - \(.roadmap_item_id) (\(.reason))"'
        echo ""
    fi

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
