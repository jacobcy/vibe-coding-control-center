#!/usr/bin/env zsh
# lib/task_audit.sh - Task Registry Audit & Repair Functions

# Helper: Check if worktrees.json has null branch fields
_task_audit_branches() {
    local worktrees_file="$1"
    local -a null_branch_worktrees

    # Find worktrees with null branch
    while IFS= read -r line; do
        null_branch_worktrees+=("$line")
    done < <(jq -r '.worktrees[]? | select(.branch == null or .branch == "") | .worktree_name' "$worktrees_file" 2>/dev/null)

    # Output results
    if [[ ${#null_branch_worktrees[@]} -eq 0 ]]; then
        return 0
    fi

    for wt_name in "${null_branch_worktrees[@]}"; do
        echo "$wt_name"
    done

    return ${#null_branch_worktrees[@]}
}

# Helper: Get actual branch from git worktree
_task_get_worktree_branch() {
    local worktree_path="$1"
    local branch

    # Validate worktree path exists
    if [[ ! -d "$worktree_path" ]]; then
        return 1
    fi

    # Try to get branch from git worktree
    # Method 1: Use git branch --show-current (Git 2.22+)
    branch=$(git -C "$worktree_path" branch --show-current 2>/dev/null) || {
        # Method 2: Fallback for older git versions
        branch=$(git -C "$worktree_path" symbolic-ref --short HEAD 2>/dev/null) || {
            # Method 3: Check if we're on a detached HEAD
            local ref
            ref=$(git -C "$worktree_path" rev-parse --abbrev-ref HEAD 2>/dev/null)
            if [[ "$ref" != "HEAD" ]]; then
                branch="$ref"
            fi
        }
    }

    if [[ -n "$branch" ]]; then
        echo "$branch"
        return 0
    fi

    return 1
}

# Helper: Fix null branch fields in worktrees.json
_task_fix_branches() {
    local worktrees_file="$1"
    local dry_run="${2:-false}"
    local backup_file="${worktrees_file}.backup"
    local common_dir
    common_dir=$(dirname "$worktrees_file")
    common_dir=$(dirname "$common_dir")

    local -a fixed_worktrees
    local -a failed_worktrees

    # Get worktrees with null branch
    local -a null_branch_worktrees
    while IFS= read -r line; do
        null_branch_worktrees+=("$line")
    done < <(_task_audit_branches "$worktrees_file")

    if [[ ${#null_branch_worktrees[@]} -eq 0 ]]; then
        log_info "No null branch fields found in worktrees.json"
        return 0
    fi

    log_info "Found ${#null_branch_worktrees[@]} worktrees with null branch field"

    # Create backup if not dry-run
    if [[ "$dry_run" != "true" ]]; then
        cp "$worktrees_file" "$backup_file"
        log_info "Created backup: $backup_file"
    fi

    # Fix each worktree
    for wt_name in "${null_branch_worktrees[@]}"; do
        local wt_path actual_branch

        # Get worktree path
        wt_path=$(jq -r --arg name "$wt_name" '.worktrees[]? | select(.worktree_name == $name) | .worktree_path' "$worktrees_file" 2>/dev/null)

        if [[ -z "$wt_path" ]]; then
            log_warn "Could not find path for worktree: $wt_name"
            failed_worktrees+=("$wt_name (no path in worktrees.json)")
            continue
        fi

        # Check if worktree path exists
        if [[ ! -d "$wt_path" ]]; then
            log_warn "Worktree path does not exist: $wt_name ($wt_path)"
            failed_worktrees+=("$wt_name (path not found)")
            continue
        fi

        # Check if it's a valid git worktree
        if [[ ! -e "$wt_path/.git" ]] && ! git -C "$wt_path" rev-parse --git-dir >/dev/null 2>&1; then
            log_warn "Not a valid git worktree: $wt_name ($wt_path)"
            failed_worktrees+=("$wt_name (not a git worktree)")
            continue
        fi

        # Get actual branch from git
        actual_branch=$(_task_get_worktree_branch "$wt_path")

        if [[ -z "$actual_branch" ]]; then
            log_warn "Could not determine branch for worktree: $wt_name"
            failed_worktrees+=("$wt_name (no branch)")
            continue
        fi

        if [[ "$dry_run" == "true" ]]; then
            log_success "[DRY-RUN] Would update $wt_name: null → $actual_branch"
            fixed_worktrees+=("$wt_name")
        else
            # Update worktrees.json
            local temp_file="${worktrees_file}.tmp"
            if jq --arg wt "$wt_name" --arg branch "$actual_branch" \
                '(.worktrees[] | select(.worktree_name == $wt) | .branch) |= $branch' \
                "$worktrees_file" > "$temp_file" && mv "$temp_file" "$worktrees_file"; then
                log_success "Fixed $wt_name: null → $actual_branch"
                fixed_worktrees+=("$wt_name")
            else
                log_error "Failed to update $wt_name"
                failed_worktrees+=("$wt_name (update failed)")
            fi
        fi
    done

    # Summary
    echo ""
    log_info "Summary:"
    echo "  Fixed: ${#fixed_worktrees[@]}"
    echo "  Failed: ${#failed_worktrees[@]}"

    if [[ ${#failed_worktrees[@]} -gt 0 ]]; then
        log_warn "Failed worktrees:"
        for wt in "${failed_worktrees[@]}"; do
            echo "  - $wt"
        done
        return 1
    fi

    return 0
}

# Main audit function - orchestrates all audit phases
vibe_task_audit() {
    local fix_branches=false
    local dry_run=false
    local check_branches=false
    local check_openspec=false
    local check_prs=false
    local all_checks=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --fix-branches)
                fix_branches=true
                shift
                ;;
            --dry-run)
                dry_run=true
                shift
                ;;
            --check-branches)
                check_branches=true
                shift
                ;;
            --check-openspec)
                check_openspec=true
                shift
                ;;
            --check-prs)
                check_prs=true
                shift
                ;;
            --all)
                all_checks=true
                shift
                ;;
            -h|--help)
                _task_audit_usage
                return 0
                ;;
            *)
                log_error "Unknown option: $1"
                _task_audit_usage
                return 1
                ;;
        esac
    done

    # Get common directory and files
    local common_dir worktrees_file registry_file
    common_dir="$(_vibe_task_common_dir)" || return 1
    worktrees_file="$common_dir/vibe/worktrees.json"
    registry_file="$common_dir/vibe/registry.json"

    _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1

    # Phase 1: Data Quality Check (null branches)
    if [[ "$fix_branches" == "true" ]] || [[ "$all_checks" == "true" ]]; then
        log_step "Phase 1: Data Quality Check (Branch Fields)"
        _task_fix_branches "$worktrees_file" "$dry_run"
        echo ""
    fi

    # Phase 2: Branch Registration Check (future implementation)
    if [[ "$check_branches" == "true" ]]; then
        log_step "Phase 2: Branch Registration Check"
        log_info "Not yet implemented"
        echo ""
    fi

    # Phase 2: OpenSpec Sync Check (future implementation)
    if [[ "$check_openspec" == "true" ]]; then
        log_step "Phase 2: OpenSpec Sync Check"
        log_info "Not yet implemented"
        echo ""
    fi

    # Phase 3: PR Association Check (future implementation)
    if [[ "$check_prs" == "true" ]]; then
        log_step "Phase 3: PR Association Check"
        log_info "Not yet implemented"
        echo ""
    fi

    # If no specific check was requested, show status
    if [[ "$fix_branches" == "false" && "$check_branches" == "false" && \
          "$check_openspec" == "false" && "$check_prs" == "false" && \
          "$all_checks" == "false" ]]; then
        log_step "Task Registry Audit Status"
        echo ""
        log_info "Data Quality:"
        local null_count
        null_count=$(_task_audit_branches "$worktrees_file" | wc -l | xargs)
        if [[ "$null_count" -eq 0 ]]; then
            log_success "All worktrees have valid branch fields"
        else
            log_warn "$null_count worktrees with null branch field"
            log_info "Run with --fix-branches to repair"
        fi
    fi

    return 0
}
