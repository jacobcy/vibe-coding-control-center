#!/usr/bin/env zsh
# lib/roadmap_query.sh - Read/Query operations for Roadmap module

_vibe_roadmap_require_file() {
    if [[ -f "$1" ]]; then
        return 0
    fi
    vibe_die "Missing $2: $1"
}

_vibe_roadmap_common_dir() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        vibe_die "Not in a git repository"
    fi
    git rev-parse --git-common-dir
}

_vibe_roadmap_file() {
    local common_dir="$1"
    echo "$common_dir/vibe/roadmap.json"
}

_vibe_roadmap_project_id() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1
    jq -r '.project_id // empty' "$roadmap_file"
}

_vibe_roadmap_current_repo() {
    local remote_url repo_path
    remote_url="$(git remote get-url origin 2>/dev/null || git config --get remote.origin.url 2>/dev/null || true)"
    [[ -n "$remote_url" ]] || { vibe_die "Unable to infer current repo from git remote origin"; return 1; }

    case "$remote_url" in
        git@github.com:*)
            repo_path="${remote_url#git@github.com:}"
            ;;
        ssh://git@github.com/*)
            repo_path="${remote_url#ssh://git@github.com/}"
            ;;
        https://github.com/*)
            repo_path="${remote_url#https://github.com/}"
            ;;
        http://github.com/*)
            repo_path="${remote_url#http://github.com/}"
            ;;
        *)
            vibe_die "Unsupported GitHub remote URL: $remote_url"
            return 1
            ;;
    esac

    repo_path="${repo_path%.git}"
    [[ "$repo_path" == */* ]] || { vibe_die "Unable to normalize repo from remote origin: $remote_url"; return 1; }
    print -r -- "$repo_path"
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
            with_github_project_item_id: ([.items[]? | select(.github_project_item_id != null)] | length),
            with_content_type: ([.items[]? | select(.content_type != null)] | length)
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

    if [[ "$output_json" == "true" ]]; then
        echo "$status_json"
        return 0
    fi

    local version_goal project_id counts p0_count current_count next_count deferred_count rejected_count
    local official_counts official_total official_item_id official_content_type
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

    official_counts="$(echo "$status_json" | jq -r '"\(.official_layer.total_items) \(.official_layer.with_github_project_item_id) \(.official_layer.with_content_type)"')"
    IFS=' ' read -r official_total official_item_id official_content_type <<< "$official_counts"
    echo "GitHub Project Mirror:"
    echo "  Total Items:       $official_total"
    echo "  Project Item IDs:  $official_item_id"
    echo "  Content Types:     $official_content_type"
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

    if [[ "$(echo "$items_json" | jq 'length')" == "0" ]]; then
        echo "No roadmap items found."
        return 0
    fi

    local first_group="true" group_status group_items group_count row rid title
    local -a ordered_statuses=(p0 current next deferred rejected)

    for group_status in "${ordered_statuses[@]}"; do
        group_items="$(echo "$items_json" | jq -c --arg status "$group_status" '[.[] | select(.status == $status)]')"
        group_count="$(echo "$group_items" | jq 'length')"
        [[ "$group_count" == "0" ]] && continue

        if [[ "$first_group" == "true" ]]; then
            first_group="false"
        else
            printf '\n'
        fi

        printf '%s\n' "$(_vibe_roadmap_group_heading "$group_status" "$group_count")"
        echo "$group_items" | jq -c '.[]' | while read -r row; do
            rid=$(echo "$row" | jq -r '.roadmap_item_id')
            title=$(echo "$row" | jq -r '.title')

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

    if [[ "$output_json" == "true" ]]; then
        echo "$item_json"
        return 0
    fi

    # Read fields
    local id title item_status source description tasks issues updated
    id=$(echo "$item_json" | jq -r '.roadmap_item_id')
    title=$(echo "$item_json" | jq -r '.title')
    item_status=$(echo "$item_json" | jq -r '.status')
    source=$(echo "$item_json" | jq -r '.source_type')
    description=$(echo "$item_json" | jq -r '.description // ""')
    tasks=$(echo "$item_json" | jq -r '.linked_task_ids | join(", ")')
    issues=$(echo "$item_json" | jq -r '.issue_refs | join(", ")')
    updated=$(echo "$item_json" | jq -r '.updated_at')

    local colored_status
    colored_status=$(_vibe_roadmap_color_status "$item_status")

    echo "Roadmap Item: $(_vibe_roadmap_format "${CYAN}${BOLD}" "$id")"
    echo "----------------------------------------"
    echo "Title:       $(_vibe_roadmap_format "$BOLD" "$title")"
    echo "Status:      ${colored_status}"
    echo "Source:      ${source}"
    echo "Updated:     ${updated}"
    echo ""
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

_vibe_roadmap_get_version_goal() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq -r '.version_goal // empty' "$roadmap_file"
}

_vibe_roadmap_has_version_goal() {
    local common_dir="$1" version_goal
    version_goal="$(_vibe_roadmap_get_version_goal "$common_dir")"
    [[ -n "$version_goal" ]]
}

_vibe_roadmap_get_current_issues() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq -c '[.items[]? | select(.status == "current" or .status == "p0")]' "$roadmap_file"
}
