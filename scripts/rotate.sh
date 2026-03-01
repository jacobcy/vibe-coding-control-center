#!/usr/bin/env zsh
# scripts/rotate.sh - 删除当前任务分支并基于 origin/main 创建新分支
# 用法: ./scripts/rotate.sh <new-branch-name>

set -euo pipefail

# ─── Colors ──────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_step()    { echo "⏳ ${BOLD}$1${NC}"; }
log_success() { echo "✅ ${GREEN}$1${NC}"; }
log_error()   { echo "❌ ${RED}$1${NC}" >&2; }
log_info()    { echo "ℹ️  ${CYAN}$1${NC}"; }
log_warn()    { echo "⚠️  ${YELLOW}$1${NC}"; }

# ─── Args ────────────────────────────────────────────────
new_task="${1:-}"
if [[ -z "$new_task" ]]; then
    echo "Usage: $0 <new-branch-name>"
    echo "  删除当前分支，基于 origin/main 创建新分支"
    echo "  未提交的改动会通过 stash 保留"
    exit 1
fi

# ─── Guard: must be in a git repo ────────────────────────
if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    log_error "Not a git repository."
    exit 1
fi

# ─── Guard: validate target branch name ──────────────────
if ! git check-ref-format --branch "$new_task" >/dev/null 2>&1; then
    log_error "Invalid branch name: $new_task"
    exit 1
fi

echo ""
echo "🔄 Rotating to new task: ${BOLD}${new_task}${NC}"
echo ""

# ─── 1. Record current branch ───────────────────────────
old_branch=$(git branch --show-current)
if [[ -z "$old_branch" ]]; then
    log_error "Not on a branch."
    exit 1
fi
case "$old_branch" in
    main|master)
        log_error "Refusing to rotate protected branch: $old_branch"
        exit 1
        ;;
esac
if [[ "$old_branch" == "$new_task" ]]; then
    log_error "New branch name matches current branch: $old_branch"
    exit 1
fi
log_info "Current branch: $old_branch"

# ─── 2. Stash uncommitted changes ───────────────────────
stashed=false
log_step "Stashing uncommitted changes"
if [[ -n "$(git status --porcelain)" ]]; then
    if git stash push -u -m "Rotate to $new_task: saved WIP"; then
        log_success "Stashed changes"
        stashed=true
    else
        log_error "Failed to stash changes"
        exit 1
    fi
else
    log_info "No uncommitted changes to stash"
fi

# ─── 3. Fetch latest main ───────────────────────────────
log_step "Fetching origin/main..."
if ! git fetch origin main --quiet; then
    log_warn "Fetch failed, falling back to local origin/main reference"
fi

# ─── 4. Verify origin/main exists ───────────────────────
if ! git show-ref --verify --quiet refs/remotes/origin/main; then
    log_error "origin/main not found. Fetch the remote branch before rotating."
    if $stashed; then
        log_warn "Restoring stash..."
        git stash pop 2>/dev/null || true
    fi
    exit 1
fi

# ─── 5. Create new branch before deleting old one ───────
log_step "Creating new branch: $new_task from origin/main"
if ! git checkout -b "$new_task" origin/main; then
    log_error "Failed to create new branch $new_task"
    if $stashed; then
        log_warn "Restoring stash..."
        git stash pop 2>/dev/null || true
    fi
    exit 1
fi

# ─── 6. Remove old branch after successful checkout ─────
log_step "Removing old branch: $old_branch"
if git branch -D "$old_branch" 2>/dev/null; then
    log_success "Deleted $old_branch"
else
    log_warn "Could not delete $old_branch"
fi

# ─── 7. Pop stash ───────────────────────────────────────
if $stashed; then
    log_step "Applying saved changes"
    if git stash pop; then
        log_success "Applied changes to $new_task"
    else
        log_warn "Stash pop failed (conflicts?). Run 'git stash pop' manually."
    fi
fi

# ─── Done ────────────────────────────────────────────────
echo ""
log_success "Task rotated successfully!"
echo "  Old branch: ${RED}$old_branch${NC} (Deleted)"
echo "  New branch: ${GREEN}$new_task${NC}"
echo ""
