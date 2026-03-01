#!/usr/bin/env zsh
# temp/rotate.sh – 临时脚本：删除当前分支并基于 main 重建
# 用法: ./temp/rotate.sh <new-branch-name>
# 注意: 不影响 .gitignore 中的临时文件

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

echo ""
echo "🔄 Rotating to new task: ${BOLD}${new_task}${NC}"
echo ""

# ─── 1. Stash uncommitted changes ───────────────────────
stashed=false
log_step "Stashing uncommitted changes"
if [[ -n "$(git status --porcelain)" ]]; then
    if git stash push -m "Rotate to $new_task: saved WIP"; then
        log_success "Stashed changes"
        stashed=true
    else
        log_error "Failed to stash changes"
        exit 1
    fi
else
    log_info "No uncommitted changes to stash"
fi

# ─── 2. Record current branch ───────────────────────────
old_branch=$(git branch --show-current)
log_info "Current branch: $old_branch"

# ─── 3. Fetch latest main ───────────────────────────────
log_step "Fetching origin/main..."
git fetch origin main --quiet 2>/dev/null || true

# ─── 4. Detach → delete old → create new ────────────────
# Detach HEAD first so the current branch can be deleted
log_step "Detaching HEAD"
git checkout --detach HEAD --quiet

log_step "Removing old branch: $old_branch"
if git branch -D "$old_branch" 2>/dev/null; then
    log_success "Deleted $old_branch"
else
    log_warn "Could not delete $old_branch"
fi

log_step "Creating new branch: $new_task from origin/main"
if ! git checkout -b "$new_task" origin/main; then
    log_error "Failed to create new branch $new_task"
    if $stashed; then
        log_warn "Restoring stash..."
        git stash pop 2>/dev/null || true
    fi
    exit 1
fi

# ─── 5. Pop stash ───────────────────────────────────────
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
