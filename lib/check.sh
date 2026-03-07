#!/usr/bin/env zsh
# v2/lib/check.sh - Minimalist Validation for Vibe 2.0
# Target: ~30 lines | Simplified API

# Helper function: Check if gh CLI is available
_check_gh_available() {
    if ! vibe_has gh; then
        return 1
    fi

    # Check if gh is authenticated
    if ! gh auth status >/dev/null 2>&1; then
        return 1
    fi

    return 0
}

# Helper function: Get merged PRs
_get_merged_prs() {
    local limit="${1:-10}"
    gh pr list --state merged --limit "$limit" --json number,headRefName,title,mergedAt 2>/dev/null
}

# Helper function: Get in-progress tasks
_get_in_progress_tasks() {
    local registry_file="$1"
    jq -r '.tasks[] | select(.status == "in_progress") | @json' "$registry_file" 2>/dev/null
}

# Helper function: Check PR merged status for tasks
_check_pr_merged_status() {
    local registry_file="$1"
    local worktrees_file="$2"
    local -a merged_pr_branches
    local -a uncertain_tasks

    # Get all merged PR branches
    local merged_prs
    merged_prs=$(_get_merged_prs 50)

    if [[ -z "$merged_prs" ]] || [[ "$merged_prs" == "[]" ]]; then
        return 0
    fi

    # Extract branch names from merged PRs
    while IFS= read -r branch; do
        merged_pr_branches+=("$branch")
    done < <(echo "$merged_prs" | jq -r '.[].headRefName')

    # Get all in-progress tasks
    while IFS= read -r task_json; do
        local task_id assigned_worktree branch
        task_id=$(echo "$task_json" | jq -r '.task_id')
        assigned_worktree=$(echo "$task_json" | jq -r '.assigned_worktree // empty')

        [[ -z "$assigned_worktree" ]] && continue

        # Get branch from worktree (match by worktree_name)
        branch=$(jq -r --arg wt "$assigned_worktree" '.worktrees[]? | select(.worktree_name == $wt) | .branch // empty' "$worktrees_file" 2>/dev/null)

        [[ -z "$branch" ]] && continue

        # Check if branch has merged PR
        for merged_branch in "${merged_pr_branches[@]}"; do
            if [[ "$branch" == "$merged_branch" ]]; then
                # Found a match - this task should be analyzed
                uncertain_tasks+=("$task_id|$branch")
                break
            fi
        done
    done < <(_get_in_progress_tasks "$registry_file")

    # Output uncertain tasks (those with merged PRs)
    for task_info in "${uncertain_tasks[@]}"; do
        echo "$task_info"
    done
}

vibe_check() {
    local file="${1:-}"
    local audit_tasks=false

    # Parse arguments
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --audit-tasks)
                audit_tasks=true
                shift
                ;;
            -h|--help)
                echo "${BOLD}Vibe Health Checker${NC}"
                echo ""
                echo "Usage: ${CYAN}vibe check${NC} [options] [file]"
                echo ""
                echo "Modes:"
                echo "  ${GREEN}[file]${NC}        验证文件格式（目前支持 JSON 及其 Vibe Schema）"
                echo "  ${GREEN}(无参数)${NC}      执行项目全要素审计（Registry、OpenSpec、归档、僵尸分支）"
                echo ""
                echo "Options:"
                echo "  ${GREEN}--audit-tasks${NC}  运行任务注册审计与修复（在主检查前执行）"
                return 0
                ;;
            *)
                file="$1"
                shift
                ;;
        esac
    done

    if [[ -n "$file" && "$file" != "--audit-tasks" ]]; then
        [[ -f "$file" ]] || { log_error "File not found: $file"; return 1; }
        if [[ "$file" == *.json ]]; then
            jq empty "$file" >/dev/null 2>&1 || { log_error "Invalid JSON: $file"; return 1; }
            jq -e 'has("tasks") or has("worktrees")' "$file" >/dev/null 2>&1 && log_success "Valid Vibe Data: $file" || log_success "Valid JSON: $file"
        else
            log_warn "Unsupported file type for check: $file"
            return 1
        fi
        return 0
    fi

    # --- Task Audit Mode (--audit-tasks) ---
    if [[ "$audit_tasks" == true ]]; then
        log_step "Running Task Registration Audit..."
        log_info "Phase 0: Task registry audit and repair"
        echo ""

        # Run vibe task audit (which triggers repair workflow)
        if vibe task audit; then
            log_success "Task audit complete. Proceeding to project audit..."
            echo ""
        else
            log_warn "Task audit encountered issues. Review the output above."
            echo ""
        fi
    fi

    # --- Audit Mode (No arguments) ---
    log_step "Starting Comprehensive Vibe Audit..."
    local reg; reg="$(git rev-parse --git-common-dir)/vibe/registry.json"
    [[ -f "$reg" ]] || { log_error "Missing registry.json"; return 1; }

    # 1. OpenSpec registration audit
    log_info "1. Auditing OpenSpec registration..."
    vibe task audit --check-openspec >/dev/null 2>&1 || true

    # 2. Archive completed tasks
    log_info "2. Archiving completed tasks..."
    local archive_dir="docs/tasks/archive"
    mkdir -p "$archive_dir"
    jq -r '.tasks[] | select(.status == "completed") | .task_id' "$reg" | while read -r tid; do
        if [[ -d "docs/tasks/$tid" ]]; then
            log_info "   Archiving $tid..."
            mv "docs/tasks/$tid" "$archive_dir/" 2>/dev/null
            vibe task update "$tid" --status archived >/dev/null 2>&1
        elif [[ -d "$archive_dir/$tid" ]]; then
            # Folder already in archive, but status still "completed" - sync it
            vibe task update "$tid" --status archived >/dev/null 2>&1
        fi
    done

    # 3. Detect stale remote branches
    log_info "3. Scanning stale remote branches..."
    git fetch origin --prune --quiet 2>/dev/null || true
    # Local cleanup of merged branches
    git branch --merged main | grep -v '^*\|main' | xargs git branch -d 2>/dev/null || true
    
    # 4. Detect scattered documents (plans only, prds are canonical)
    log_info "4. Searching for scattered task documents (docs/plans)..."
    local scattered=()
    if [[ -d "docs/plans" ]]; then
        while read -r f; do
            scattered+=("$f")
        done < <(find "docs/plans" -maxdepth 1 -name "*.md" ! -name "README.md" 2>/dev/null)
    fi
    if [[ ${#scattered[@]} -gt 0 ]]; then
        log_warn "   Found ${#scattered[@]} scattered documents in docs/plans:"
        for f in "${scattered[@]}"; do echo "     - $f"; done
    fi

    # 5. Branch Consistency Check
    log_info "5. Verifying branch-to-task consistency..."
    local active_tasks; active_tasks=$(jq -r '.tasks[] | select(.status == "in_progress" or .status == "todo") | .task_id' "$reg")
    local branches_in_use; branches_in_use=($(git worktree list --porcelain | awk '$1=="branch" {print $2}'))
    local ghost_branches=()
    while read -r branch; do
        branch="${branch#* }" # Remove star if current
        # 1. Exempt branches currently checked out in any worktree
        local in_use=0
        for b in "${branches_in_use[@]}"; do
            [[ "refs/heads/$branch" == "$b" ]] && { in_use=1; break; }
        done
        [[ $in_use -eq 1 ]] && continue

        # 2. Check if branch name matches any active task ID or slug
        local match_found=0
        for tid in ${(f)active_tasks}; do
            # Full match or slug match (e.g. branch "claude/feat" matches task "YYYY-MM-DD-feat")
            [[ "$branch" == *"$tid"* ]] && { match_found=1; break; }
            local slug="${tid#????-??-??-}" # Extract slug from YYYY-MM-DD-slug
            [[ -n "$slug" && "$branch" == *"$slug"* ]] && { match_found=1; break; }
        done
        # Ignore main and v* branches
        [[ "$branch" == "main" || "$branch" == v* ]] && match_found=1
        
        [[ $match_found -eq 0 ]] && ghost_branches+=("$branch")
    done < <(git branch --list --no-column | sed 's/^[ *]*//')
    
    if [[ ${#ghost_branches[@]} -gt 0 ]]; then
        log_warn "   Found ${#ghost_branches[@]} ghost branches (no active task matching):"
        for gb in "${ghost_branches[@]}"; do echo "     - $gb"; done
    fi

    # Phase 2: Git Status Check (PR merged detection)
    log_info "6. Checking PR merged status..."
    if ! _check_gh_available; then
        log_warn "   gh CLI not available or not authenticated. Skipping PR status check."
    else
        local worktrees_file; worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
        local -a uncertain_tasks
        while IFS='|' read -r task_id branch; do
            [[ -n "$task_id" && -n "$branch" ]] && uncertain_tasks+=("$task_id|$branch")
        done < <(_check_pr_merged_status "$reg" "$worktrees_file")

        if [[ ${#uncertain_tasks[@]} -gt 0 ]]; then
            log_info "   Found ${#uncertain_tasks[@]} task(s) with merged PRs:"
            for task_info in "${uncertain_tasks[@]}"; do
                local tid br
                IFS='|' read -r tid br <<< "$task_info"
                echo "     - $tid (branch: $br)"
            done
            echo ""
            log_info "   Run ${CYAN}/vibe-check${NC} for AI-assisted task completion analysis."
        fi
    fi

    # 7. Health Check Summary
    local total; total=$(jq '.tasks | length' "$reg")
    local in_progress; in_progress=$(jq '[.tasks[] | select(.status == "in_progress" or .status == "todo")] | length' "$reg")
    local archived; archived=$(jq '[.tasks[] | select(.status == "archived")] | length' "$reg")
    local completed; completed=$(jq '[.tasks[] | select(.status == "completed")] | length' "$reg")
    local archived_folders; archived_folders=$(ls -1 "$archive_dir" 2>/dev/null | wc -l | xargs)

    log_success "Audit complete."
    echo "  - Total Tasks: $total"
    echo "  - Active (Todo/In-Progress): $in_progress"
    echo "  - Completed (Pending Archive): $completed"
    echo "  - Archived Tasks: $archived (Docs in archive/: $archived_folders)"
    echo "  - Ghost Branches: ${#ghost_branches[@]}"
    echo "  - Scattered Docs: ${#scattered[@]}"
    echo ""
    log_info "Tip: Use ${CYAN}/vibe-check (slash)${NC} for AI-assisted remediation."
}
