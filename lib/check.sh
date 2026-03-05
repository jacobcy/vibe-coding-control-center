#!/usr/bin/env zsh
# v2/lib/check.sh - Minimalist Validation for Vibe 2.0
# Target: ~30 lines | Simplified API

vibe_check() {
    local file="${1:-}"
    
    if [[ "$file" == "-h" || "$file" == "--help" ]]; then
        echo "${BOLD}Vibe Health Checker${NC}"
        echo ""
        echo "Usage: ${CYAN}vibe check${NC} [file]"
        echo ""
        echo "Modes:"
        echo "  ${GREEN}[file]${NC}        验证文件格式（目前支持 JSON 及其 Vibe Schema）"
        echo "  ${GREEN}(无参数)${NC}      执行项目全要素审计（Registry、OpenSpec、归档、僵尸分支）"
        return 0
    fi

    if [[ -n "$file" ]]; then
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

    # --- Audit Mode (No arguments) ---
    log_step "Starting Comprehensive Vibe Audit..."
    local reg; reg="$(git rev-parse --git-common-dir)/vibe/registry.json"
    [[ -f "$reg" ]] || { log_error "Missing registry.json"; return 1; }

    # 1. Registry vs OpenSpec
    log_info "1. Syncing Registry with OpenSpec..."
    vibe_task sync 2>/dev/null || true

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

    # 6. Health Check Summary
    local total; total=$(jq '.tasks | length' "$reg")
    local in_progress; in_progress=$(jq '[.tasks[] | select(.status == "in_progress" or .status == "todo")] | length' "$reg")
    local archived; archived=$(jq '[.tasks[] | select(.status == "archived")] | length' "$reg")
    local completed; completed=$(jq '[.tasks[] | select(.status == "completed")] | length' "$reg")
    local archived_folders; archived_folders=$(ls -1 "$archive_dir" 2>/dev/null | wc -l | xargs)

    log_success "Audit complete."
    echo "  - Total Tasks: $total"
    echo "  - Active (Todo/In-Progress): $in_progress"
    echo "  - Completed (Pending Archive): $completed"
    echo "  - Ghost Branches: ${#ghost_branches[@]}"
    echo "  - Scattered Docs: ${#scattered[@]}"
    echo ""
    log_info "Tip: Use ${CYAN}/vibe-check (slash)${NC} for AI-assisted remediation."
}
