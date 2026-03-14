#!/usr/bin/env zsh
# lib/roadmap_dependency.sh - Derived dependency views for roadmap items

[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/check_pr_status.sh" ]] && source "$VIBE_LIB/check_pr_status.sh"

_vibe_roadmap_merged_prs_json() {
    if [[ -n "${_VIBE_ROADMAP_MERGED_PRS_JSON:-}" ]]; then
        print -r -- "$_VIBE_ROADMAP_MERGED_PRS_JSON"
        [[ "${_VIBE_ROADMAP_MERGED_PRS_JSON_VALID:-false}" == "true" ]]
        return $?
    fi

    if _check_gh_available; then
        _VIBE_ROADMAP_MERGED_PRS_JSON="$(_get_merged_prs 1000)"
        if print -r -- "$_VIBE_ROADMAP_MERGED_PRS_JSON" | jq -e 'type == "array"' >/dev/null 2>&1; then
            _VIBE_ROADMAP_MERGED_PRS_JSON_VALID="true"
        else
            _VIBE_ROADMAP_MERGED_PRS_JSON='[]'
            _VIBE_ROADMAP_MERGED_PRS_JSON_VALID="false"
        fi
    else
        _VIBE_ROADMAP_MERGED_PRS_JSON='[]'
        _VIBE_ROADMAP_MERGED_PRS_JSON_VALID="false"
    fi

    print -r -- "$_VIBE_ROADMAP_MERGED_PRS_JSON"
    [[ "$_VIBE_ROADMAP_MERGED_PRS_JSON_VALID" == "true" ]]
}

_vibe_roadmap_has_dependency_item() {
    local roadmap_file="$1" dep_id="$2"
    jq -e --arg id "$dep_id" '.items[]? | select(.roadmap_item_id == $id)' "$roadmap_file" >/dev/null 2>&1
}

_vibe_roadmap_dependency_task_prs() {
    local registry_file="$1" dep_id="$2"
    jq -r --arg rid "$dep_id" '
        [
            .tasks[]?
            | select((.roadmap_item_ids // []) | index($rid))
            | .pr_ref // ""
            | select(. != "")
        ]
        | unique
        | .[]
    ' "$registry_file" 2>/dev/null
}

_vibe_roadmap_pr_is_merged() {
    local pr_ref="${1#\#}" merged_prs_json
    [[ -n "$pr_ref" ]] || return 1

    merged_prs_json="$(_vibe_roadmap_merged_prs_json)" || return 2
    print -r -- "$merged_prs_json" | jq -e --arg ref "$pr_ref" '.[]? | select((.number | tostring) == $ref)' >/dev/null 2>&1
}

_vibe_roadmap_compute_dependency_status() {
    local common_dir="$1" item_id="$2"
    local roadmap_file registry_file depends_on blockers_json blocker_count gh_available merged_prs_ready

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    registry_file="$common_dir/vibe/registry.json"
    depends_on="$(jq -c --arg id "$item_id" '.items[]? | select(.roadmap_item_id == $id) | .depends_on_item_ids // []' "$roadmap_file")"
    gh_available="false"
    merged_prs_ready="false"
    if _check_gh_available; then
        gh_available="true"
        if _vibe_roadmap_merged_prs_json >/dev/null; then
            merged_prs_ready="true"
        fi
    fi

    if [[ "$(print -r -- "$depends_on" | jq 'length')" -eq 0 ]]; then
        jq -n '{ready: true, blocked: false, blockers: []}'
        return 0
    fi

    blockers_json="$(
        print -r -- "$depends_on" | jq -r '.[]' | while read -r dep_id; do
            local matched_pr_refs has_merged_pr

            if ! _vibe_roadmap_has_dependency_item "$roadmap_file" "$dep_id"; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "missing_dependency_item"}'
                continue
            fi

            matched_pr_refs="$(_vibe_roadmap_dependency_task_prs "$registry_file" "$dep_id")"
            if [[ -z "$matched_pr_refs" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "missing_pr_ref"}'
                continue
            fi

            if [[ "$gh_available" != "true" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "merge_status_unavailable"}'
                continue
            fi

            if [[ "$merged_prs_ready" != "true" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "merge_status_unavailable"}'
                continue
            fi

            has_merged_pr="false"
            while read -r pr_ref; do
                [[ -n "$pr_ref" ]] || continue
                if _vibe_roadmap_pr_is_merged "$pr_ref"; then
                    has_merged_pr="true"
                    break
                fi
            done <<< "$matched_pr_refs"

            if [[ "$has_merged_pr" != "true" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "pr_not_merged"}'
            fi
        done | jq -s '. | map(select(. != null))'
    )"

    blocker_count="$(print -r -- "$blockers_json" | jq 'length')"
    if [[ "$blocker_count" -eq 0 ]]; then
        jq -n '{ready: true, blocked: false, blockers: []}'
    else
        print -r -- "$blockers_json" | jq -c '{ready: false, blocked: true, blockers: .}'
    fi
}

_vibe_roadmap_status_with_dependency_counts() {
    local common_dir="$1" roadmap_file="$2" status_json="$3"
    local dependency_ready=0 dependency_blocked=0 dep_status

    while IFS= read -r item_id; do
        dep_status="$(_vibe_roadmap_compute_dependency_status "$common_dir" "$item_id")"
        if [[ "$(echo "$dep_status" | jq -r '.ready')" == "true" ]]; then
            ((dependency_ready++))
        else
            ((dependency_blocked++))
        fi
    done < <(jq -r '.items[].roadmap_item_id' "$roadmap_file")

    print -r -- "$status_json" | jq -c --argjson ready "$dependency_ready" --argjson blocked "$dependency_blocked" '
        . + {dependency_counts: {ready: $ready, blocked: $blocked}}
    '
}

_vibe_roadmap_render_dependency_summary() {
    local status_json="$1" dep_ready dep_blocked
    dep_ready="$(print -r -- "$status_json" | jq -r '.dependency_counts.ready')"
    dep_blocked="$(print -r -- "$status_json" | jq -r '.dependency_counts.blocked')"

    echo "Dependency Status:"
    if _vibe_roadmap_supports_color; then
        printf "  %-16s  %b\n" "Ready:" "$(_vibe_roadmap_format "$GREEN" "($dep_ready)")"
        printf "  %-16s  %b\n" "Blocked:" "$(_vibe_roadmap_format "$RED" "($dep_blocked)")"
    else
        echo "  Ready:           $dep_ready"
        echo "  Blocked:         $dep_blocked"
    fi
    echo ""
}

_vibe_roadmap_render_item_dependency_status() {
    local dependency_status="$1"
    local dep_ready dep_blockers

    dep_ready="$(print -r -- "$dependency_status" | jq -r '.ready')"
    dep_blockers="$(print -r -- "$dependency_status" | jq -r '.blockers')"

    if [[ "$dep_ready" == "true" ]]; then
        echo "Dependency Status: $(_vibe_roadmap_format "$GREEN" "ready")"
    else
        echo "Dependency Status: $(_vibe_roadmap_format "$RED" "blocked")"
        echo ""
        echo "Blockers:"
        print -r -- "$dep_blockers" | jq -r '.[] | "  - \(.roadmap_item_id) (\(.reason))"'
        echo ""
    fi
}

# PR merge dependency management functions

_vibe_roadmap_pr_dependency_add() {
    local common_dir="$1" pr_number="$2" depends_on_pr="$3"
    local roadmap_file current_deps new_deps

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"

    # Get current dependencies
    current_deps="$(_vibe_roadmap_pr_get_dependencies "$common_dir" "$pr_number")"

    # Check if dependency already exists
    if echo "$current_deps" | jq -e --arg dep "$depends_on_pr" 'index($dep)' >/dev/null 2>&1; then
        log_error "PR #$pr_number already depends on PR #$depends_on_pr"
        return 1
    fi

    # Add new dependency
    new_deps="$(echo "$current_deps" | jq -c --arg dep "$depends_on_pr" '. + [$dep]')"

    # Check for circular dependencies
    if _vibe_roadmap_pr_has_circular_dependency "$common_dir" "$pr_number" "$new_deps"; then
        log_error "Circular dependency detected: adding PR #$depends_on_pr would create a cycle"
        return 1
    fi

    # Get PR URL (if available)
    local pr_url
    pr_url="$(jq -r --arg pr "$pr_number" '.prs[$pr].url // "https://github.com"' "$roadmap_file")"

    # Update PR metadata
    _vibe_roadmap_pr_set "$common_dir" "$pr_number" "$pr_url" "$new_deps" || return 1

    log_success "Added dependency: PR #$pr_number now depends on PR #$depends_on_pr"
}

_vibe_roadmap_pr_dependency_remove() {
    local common_dir="$1" pr_number="$2" depends_on_pr="$3"
    local current_deps new_deps pr_url

    # Get current dependencies
    current_deps="$(_vibe_roadmap_pr_get_dependencies "$common_dir" "$pr_number")"

    # Check if dependency exists
    if ! echo "$current_deps" | jq -e --arg dep "$depends_on_pr" 'index($dep)' >/dev/null 2>&1; then
        log_error "PR #$pr_number does not depend on PR #$depends_on_pr"
        return 1
    fi

    # Remove dependency
    new_deps="$(echo "$current_deps" | jq -c --arg dep "$depends_on_pr" '. - [$dep]')"

    # Get PR URL
    pr_url="$(jq -r --arg pr "$pr_number" '.prs[$pr].url // "https://github.com"' "$(_vibe_roadmap_file "$common_dir")")"

    # Update PR metadata
    _vibe_roadmap_pr_set "$common_dir" "$pr_number" "$pr_url" "$new_deps" || return 1

    log_success "Removed dependency: PR #$pr_number no longer depends on PR #$depends_on_pr"
}

_vibe_roadmap_pr_has_circular_dependency() {
    local common_dir="$1" pr_number="$2" new_deps="$3"
    local roadmap_file visited

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"

    # Build dependency graph and check for cycles using DFS
    # A cycle exists if we can reach pr_number by following dependencies from any dep in new_deps
    local -A visited
    local queue=()

    # Initialize queue with new dependencies
    while read -r dep; do
        [[ -n "$dep" ]] && queue+=("$dep")
    done < <(echo "$new_deps" | jq -r '.[]')

    # BFS to check if we can reach pr_number
    while [[ ${#queue[@]} -gt 0 ]]; do
        local current="${queue[0]}"
        queue=("${queue[@]:1}")

        # If we reach the original PR, we have a cycle
        [[ "$current" == "$pr_number" ]] && return 0

        # Skip if already visited
        [[ -n "${visited[$current]:-}" ]] && continue
        visited[$current]=1

        # Get dependencies of current PR and add to queue
        local dep_deps
        dep_deps="$(jq -r --arg pr "$current" '(.prs[$pr].merge_dependencies // []) | .[]' "$roadmap_file" 2>/dev/null || true)"
        while read -r dep; do
            [[ -n "$dep" ]] && queue+=("$dep")
        done <<< "$dep_deps"
    done

    # No cycle found
    return 1
}

_vibe_roadmap_pr_check_unmet_dependencies() {
    local common_dir="$1" pr_number="$2"
    local dependencies merged_prs_json unmet=()

    # Get PR dependencies
    dependencies="$(_vibe_roadmap_pr_get_dependencies "$common_dir" "$pr_number")"

    # If no dependencies, all met
    if [[ "$(echo "$dependencies" | jq 'length')" -eq 0 ]]; then
        echo "[]"
        return 0
    fi

    # Get merged PRs
    if ! _vibe_roadmap_merged_prs_json >/dev/null 2>&1; then
        log_warn "Unable to check PR merge status (GitHub API unavailable)"
        echo "[]"
        return 0
    fi
    merged_prs_json="$(_vibe_roadmap_merged_prs_json)"

    # Check each dependency
    while read -r dep_pr; do
        [[ -n "$dep_pr" ]] || continue
        if ! echo "$merged_prs_json" | jq -e --arg ref "$dep_pr" '.[]? | select((.number | tostring) == $ref)' >/dev/null 2>&1; then
            unmet+=("$dep_pr")
        fi
    done < <(echo "$dependencies" | jq -r '.[]')

    # Return unmet dependencies as JSON array
    if [[ ${#unmet[@]} -eq 0 ]]; then
        echo "[]"
    else
        printf '%s\n' "${unmet[@]}" | jq -R . | jq -s .
    fi
}

# PR dependency command handler

_vibe_roadmap_pr_dependency_command() {
    local action="${1:-}"
    shift || true

    case "$action" in
        add|remove)
            local pr_number="" depends_on_pr=""

            # Parse arguments
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --pr) pr_number="$2"; shift 2 ;;
                    --depends-on) depends_on_pr="$2"; shift 2 ;;
                    -*)
                        log_error "Unknown option: $1"
                        return 1
                        ;;
                    *)
                        # Positional arguments: <pr> <depends-on-pr>
                        if [[ -z "$pr_number" ]]; then
                            pr_number="$1"
                        elif [[ -z "$depends_on_pr" ]]; then
                            depends_on_pr="$1"
                        fi
                        shift
                        ;;
                esac
            done

            # Validate arguments
            if [[ -z "$pr_number" || -z "$depends_on_pr" ]]; then
                log_error "Usage: vibe roadmap dependency $action <pr-number> <depends-on-pr-number>"
                return 1
            fi

            # Execute action
            local common_dir
            common_dir="$(_vibe_roadmap_common_dir)" || return 1

            if [[ "$action" == "add" ]]; then
                _vibe_roadmap_pr_dependency_add "$common_dir" "$pr_number" "$depends_on_pr"
            else
                _vibe_roadmap_pr_dependency_remove "$common_dir" "$pr_number" "$depends_on_pr"
            fi
            ;;
        check)
            local pr_number="" common_dir unmet_deps

            # Parse arguments
            while [[ $# -gt 0 ]]; do
                case "$1" in
                    --pr) pr_number="$2"; shift 2 ;;
                    *)
                        if [[ -z "$pr_number" ]]; then
                            pr_number="$1"
                        fi
                        shift
                        ;;
                esac
            done

            if [[ -z "$pr_number" ]]; then
                log_error "Usage: vibe roadmap dependency check <pr-number>"
                return 1
            fi

            common_dir="$(_vibe_roadmap_common_dir)" || return 1
            unmet_deps="$(_vibe_roadmap_pr_check_unmet_dependencies "$common_dir" "$pr_number")"

            if [[ "$(echo "$unmet_deps" | jq 'length')" -eq 0 ]]; then
                log_success "All dependencies for PR #$pr_number are met"
            else
                log_warn "PR #$pr_number has unmet dependencies:"
                echo "$unmet_deps" | jq -r '.[]' | while read -r dep; do
                    echo "  - PR #$dep"
                done
                return 1
            fi
            ;;
        -h|--help|help|"")
            cat <<EOF
Usage: vibe roadmap dependency <action> ...

PR merge dependency management commands.

Actions:
  add <pr> <depends-on-pr>    Add a merge dependency
  remove <pr> <depends-on-pr> Remove a merge dependency
  check <pr>                  Check if all dependencies are met

Examples:
  vibe roadmap dependency add 123 122
  vibe roadmap dependency remove 123 122
  vibe roadmap dependency check 123
EOF
            ;;
        *)
            log_error "Unknown dependency action: $action"
            log_error "Run 'vibe roadmap dependency --help' for usage"
            return 1
            ;;
    esac
}
