#!/usr/bin/env zsh
# v2/lib/check.sh - Minimalist Validation for Vibe 2.0
# Target: ~30 lines | Simplified API

vibe_check() {
    local file="${1:-}"
    
    if [[ "$file" == "-h" || "$file" == "--help" ]]; then
        echo "Usage: ${CYAN}vibe check [file]${NC}"
        echo "  - With file: Validates format (currently JSON)."
        echo "  - No file:   Performs comprehensive audit of registry, openspec, and branches."
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
        fi
    done

    # 3. Detect stale remote branches
    log_info "3. Scanning stale remote branches..."
    git fetch origin --prune --quiet 2>/dev/null || true
    # Local cleanup of merged branches
    git branch --merged main | grep -v '^*\|main' | xargs git branch -d 2>/dev/null || true
    
    # 4. Health Check Summary
    local total; total=$(jq '.tasks | length' "$reg")
    local in_progress; in_progress=$(jq '[.tasks[] | select(.status == "in_progress" or .status == "todo")] | length' "$reg")
    local completed; completed=$(jq '[.tasks[] | select(.status == "completed")] | length' "$reg")
    local archived_count; archived_count=$(ls -1 "$archive_dir" 2>/dev/null | wc -l | xargs)

    log_success "Audit complete."
    echo "  - Total Tasks: $total"
    echo "  - Active (Todo/In-Progress): $in_progress"
    echo "  - Completed (Pending Archive): $completed"
    echo "  - Archived Folders: $archived_count"
    echo ""
    log_info "Tip: Use ${CYAN}/vibe-check (slash)${NC} for AI-assisted remediation."
}
