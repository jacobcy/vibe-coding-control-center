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
    local rollback_needed=false
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
                rollback_needed=true
            fi
        fi
    done


    # Rollback if critical failure occurred
    if [[ "$rollback_needed" == "true" && -f "$backup_file" ]]; then
        log_warn "Critical failure detected, rolling back from backup..."
        cp "$backup_file" "$worktrees_file"
        log_info "Restored from backup: $backup_file"
        return 1
    fi

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
        _task_fix_branches "$worktrees_file" "$dry_run" || true
        echo ""
    fi

    # Phase 2: Branch Registration Check
    if [[ "$check_branches" == "true" ]] || [[ "$all_checks" == "true" ]]; then
        log_step "Phase 2: Branch Registration Check"
        local -a unregistered_branches
        while IFS= read -r line; do
            unregistered_branches+=("$line")
        done < <(_task_check_branch_registration "$common_dir")
        
        if [[ ${#unregistered_branches[@]} -eq 0 ]]; then
            log_success "All branch tasks are registered"
        else
            log_warn "Found ${#unregistered_branches[@]} unregistered branch tasks:"
            for entry in "${unregistered_branches[@]}"; do
                local wt_name branch pattern
                wt_name=$(echo "$entry" | cut -d'|' -f1)
                branch=$(echo "$entry" | cut -d'|' -f2)
                pattern=$(echo "$entry" | cut -d'|' -f3)
                echo "  - $wt_name (branch: $branch, pattern: $pattern)"
            done
        fi
        echo ""
    fi

    # Phase 2: OpenSpec Sync Check
    if [[ "$check_openspec" == "true" ]] || [[ "$all_checks" == "true" ]]; then
        log_step "Phase 2: OpenSpec Sync Check"
        local -a unsynced_changes
        while IFS= read -r line; do
            unsynced_changes+=("$line")
        done < <(_task_check_openspec_sync "$common_dir")
        
        if [[ ${#unsynced_changes[@]} -eq 0 ]]; then
            log_success "All OpenSpec changes are synced"
        else
            log_warn "Found ${#unsynced_changes[@]} unsynced OpenSpec changes:"
            for change in "${unsynced_changes[@]}"; do
                echo "  - $change"
            done
            log_info "Run 'vibe task sync' to sync OpenSpec changes to registry"
        fi
        echo ""
    fi

    # Phase 3: PR Association Check (future implementation)
    if [[ "$check_prs" == "true" ]]; then
        log_step "Phase 3: PR Association Check"
        log_info "Not yet implemented"
        echo ""
    fi


    # Generate summary report if running comprehensive audit
    if [[ "$all_checks" == "true" ]]; then
        _task_generate_audit_summary "$common_dir"
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
# Helper: Extract task pattern from branch name
_task_extract_branch_pattern() {
    local branch_name="$1"
    local pattern=""
    
    # Match YYYY-MM-DD-slug pattern
    if [[ "$branch_name" =~ ^([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)$ ]]; then
        pattern="${match[1]}"
    # Match codex/YYYY-MM-DD-slug pattern
    elif [[ "$branch_name" =~ codex/([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)$ ]]; then
        pattern="${match[1]}"
    # Match feature/YYYY-MM-DD-slug pattern
    elif [[ "$branch_name" =~ feature/([0-9]{4}-[0-9]{2}-[0-9]{2}-[a-z0-9-]+)$ ]]; then
        pattern="${match[1]}"
    fi
    
    if [[ -n "$pattern" ]]; then
        echo "$pattern"
        return 0
    fi
    
    return 1
}

# Helper: Check if branch task is registered
_task_is_branch_registered() {
    local branch_pattern="$1"
    local registry_file="$2"
    
    # Check if task exists with matching ID or slug
    if jq -e --arg pattern "$branch_pattern" \
        '.tasks[]? | select(.task_id == $pattern or .slug == $pattern)' \
        "$registry_file" >/dev/null 2>&1; then
        return 0
    fi
    
    return 1
}

# Helper: Check branch registration status
_task_check_branch_registration() {
    local common_dir="$1"
    local worktrees_file="$common_dir/vibe/worktrees.json"
    local registry_file="$common_dir/vibe/registry.json"
    local -a unregistered_branches
    
    # Get all worktrees with valid branches
    while IFS= read -r line; do
        local wt_name branch pattern
        wt_name=$(echo "$line" | cut -d'|' -f1)
        branch=$(echo "$line" | cut -d'|' -f2)
        
        # Extract task pattern from branch name
        pattern=$(_task_extract_branch_pattern "$branch")
        
        if [[ -n "$pattern" ]]; then
            # Check if registered
            if ! _task_is_branch_registered "$pattern" "$registry_file"; then
                unregistered_branches+=("$wt_name|$branch|$pattern")
            fi
        fi
    done < <(jq -r '.worktrees[]? | select(.branch != null and .branch != "") | "\(.worktree_name)|\(.branch)"' "$worktrees_file" 2>/dev/null)
    
    # Output results
    if [[ ${#unregistered_branches[@]} -eq 0 ]]; then
        return 0
    fi
    
    for entry in "${unregistered_branches[@]}"; do
        echo "$entry"
    done
    
    return ${#unregistered_branches[@]}
}

# Helper: Check OpenSpec sync status
_task_check_openspec_sync() {
    local common_dir="$1"
    local registry_file="$common_dir/vibe/registry.json"
    local openspec_changes_dir="openspec/changes"
    local -a unsynced_changes
    
    # Check if OpenSpec directory exists
    if [[ ! -d "$openspec_changes_dir" ]]; then
        return 0
    fi
    
    # Scan all changes directories (excluding archive)
    while IFS= read -r change_dir; do
        local change_name
        change_name=$(basename "$change_dir")
        
        # Skip archive directory
        if [[ "$change_name" == "archive" ]]; then
            continue
        fi
        
        # Check if change is registered
        if ! jq -e --arg change "$change_name" \
            '.tasks[]? | select(.task_id == $change or .slug == $change or (.openspec_change == $change))' \
            "$registry_file" >/dev/null 2>&1; then
            unsynced_changes+=("$change_name")
        fi
    done < <(find "$openspec_changes_dir" -maxdepth 1 -type d ! -path "$openspec_changes_dir")
    
    # Output results
    if [[ ${#unsynced_changes[@]} -eq 0 ]]; then
        return 0
    fi
    
    for change in "${unsynced_changes[@]}"; do
        echo "$change"
    done
    
    return ${#unsynced_changes[@]}
}

# Helper: Generate audit summary report
_task_generate_audit_summary() {
    local common_dir="$1"
    local worktrees_file="$common_dir/vibe/worktrees.json"
    local registry_file="$common_dir/vibe/registry.json"
    
    local -a data_quality_issues
    local -a registration_issues
    local -a sync_issues
    
    echo ""
    log_step "Audit Summary Report"
    echo ""
    
    # Data Quality Issues
    log_info "=== Data Quality Issues ==="
    local null_count
    null_count=$(_task_audit_branches "$worktrees_file" | wc -l | xargs)
    if [[ "$null_count" -eq 0 ]]; then
        log_success "✓ All worktrees have valid branch fields"
    else
        log_warn "✗ $null_count worktrees with null branch field"
        log_info "  Repair: vibe task audit --fix-branches"
        data_quality_issues+=("null_branch_fields")
    fi
    echo ""
    
    # Registration Issues
    log_info "=== Task Registration Issues ==="
    local -a unregistered_branches
    while IFS= read -r line; do
        unregistered_branches+=("$line")
    done < <(_task_check_branch_registration "$common_dir")
    
    if [[ ${#unregistered_branches[@]} -eq 0 ]]; then
        log_success "✓ All branch tasks are registered"
    else
        log_warn "✗ ${#unregistered_branches[@]} unregistered branch tasks found"
        for entry in "${unregistered_branches[@]}"; do
            local wt_name branch pattern
            wt_name=$(echo "$entry" | cut -d'|' -f1)
            branch=$(echo "$entry" | cut -d'|' -f2)
            pattern=$(echo "$entry" | cut -d'|' -f3)
            echo "    - $wt_name (branch: $branch)"
        done
        log_info "  Action: Review and register tasks as needed"
        registration_issues+=("unregistered_branches")
    fi
    echo ""
    
    # Sync Issues
    log_info "=== OpenSpec Sync Issues ==="
    local -a unsynced_changes
    while IFS= read -r line; do
        unsynced_changes+=("$line")
    done < <(_task_check_openspec_sync "$common_dir")
    
    if [[ ${#unsynced_changes[@]} -eq 0 ]]; then
        log_success "✓ All OpenSpec changes are synced"
    else
        log_warn "✗ ${#unsynced_changes[@]} unsynced OpenSpec changes found"
        for change in "${unsynced_changes[@]}"; do
            echo "    - $change"
        done
        log_info "  Repair: vibe task sync"
        sync_issues+=("unsynced_changes")
    fi
    echo ""
    
    # Overall Health
    log_step "Overall Health Status"
    local total_issues=$((${#data_quality_issues[@]} + ${#registration_issues[@]} + ${#sync_issues[@]}))
    
    if [[ $total_issues -eq 0 ]]; then
        log_success "✓✓✓ All checks passed! Task registry is healthy."
        return 0
    else
        log_warn "✗✗✗ Found $total_issues category(s) with issues"
        echo ""
        log_info "Next Steps:"
        [[ ${#data_quality_issues[@]} -gt 0 ]] && echo "  1. Fix data quality: vibe task audit --fix-branches"
        [[ ${#registration_issues[@]} -gt 0 ]] && echo "  2. Review unregistered tasks and register as needed"
        [[ ${#sync_issues[@]} -gt 0 ]] && echo "  3. Sync OpenSpec changes: vibe task sync"
        return 1
    fi
}
