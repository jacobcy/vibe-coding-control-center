#!/usr/bin/env zsh

# PR merge dependency management functions
# Part of the roadmap system for managing stacked PR merge order

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
    local -A visited
    local queue=()

    # Initialize queue with new dependencies
    while read -r dep; do
        [[ -n "$dep" ]] && queue+=("$dep")
    done < <(echo "$new_deps" | jq -r '.[]')

    # BFS to check if we can reach pr_number
    while [[ ${#queue[@]} -gt 0 ]]; do
        local current="${queue[1]}"
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
                        if [[ -z "$pr_number" ]]; then
                            pr_number="$1"
                        elif [[ -z "$depends_on_pr" ]]; then
                            depends_on_pr="$1"
                        fi
                        shift
                        ;;
                esac
            done

            if [[ -z "$pr_number" || -z "$depends_on_pr" ]]; then
                log_error "Usage: vibe roadmap dependency $action <pr-number> <depends-on-pr-number>"
                return 1
            fi

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
