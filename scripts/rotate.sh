#!/usr/bin/env zsh
# scripts/rotate.sh - 从当前 worktree 旋转到新的可发布 workflow
# 用法: ./scripts/rotate.sh <new-branch-name>

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; NC='\033[0m'; BOLD='\033[1m'

log_step()    { echo "⏳ ${BOLD}$1${NC}"; }
log_success() { echo "✅ ${GREEN}$1${NC}"; }
log_error()   { echo "❌ ${RED}$1${NC}" >&2; }
log_info()    { echo "ℹ️  ${CYAN}$1${NC}"; }
log_warn()    { echo "⚠️  ${YELLOW}$1${NC}"; }

now_iso() { date +"%Y-%m-%dT%H:%M:%S%z"; }

is_generic_workflow_name() {
    local name="${1:l}"
    case "$name" in
        develop|refactor|bug-fix|fix|test|cleanup|misc)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

update_worktree_dashboard() {
    local new_branch="$1" git_common_dir worktrees_file current_dir current_path now tmp
    git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 1
    worktrees_file="$git_common_dir/vibe/worktrees.json"
    [[ -f "$worktrees_file" ]] || {
        log_info "No worktrees dashboard found. Skipping shared-state update."
        return 0
    }

    current_dir="$(basename "$PWD")"
    current_path="$PWD"
    now="$(now_iso)"
    tmp="$(mktemp)"

    jq --arg wt "$current_dir" --arg path "$current_path" --arg branch "$new_branch" --arg now "$now" '
      .worktrees = ((.worktrees // []) | map(
        if .worktree_name == $wt or .worktree_path == $path then
          .branch = $branch
          | .status = "active"
          | .last_updated = $now
        else . end
      ))
    ' "$worktrees_file" > "$tmp" && mv "$tmp" "$worktrees_file"
}

new_task="${1:-}"
if [[ -z "$new_task" ]]; then
    echo "Usage: $0 <new-branch-name>"
    echo "  从当前 worktree 旋转到新的可发布 workflow"
    echo "  当前 HEAD 上的已提交内容会保留，未提交改动会通过 stash 带过去"
    exit 1
fi

if ! git rev-parse --is-inside-work-tree &>/dev/null; then
    log_error "Not a git repository."
    exit 1
fi

if ! git check-ref-format --branch "$new_task" >/dev/null 2>&1; then
    log_error "Invalid branch name: $new_task"
    exit 1
fi

if is_generic_workflow_name "$new_task"; then
    log_error "Refusing generic workflow name: $new_task"
    log_warn "Use a concrete feature branch before submitting or continuing delivery."
    exit 1
fi

echo ""
echo "🔄 Rotating to new workflow: ${BOLD}${new_task}${NC}"
echo ""

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

log_step "Creating new branch: $new_task from current HEAD"
if ! git checkout -b "$new_task"; then
    log_error "Failed to create new branch $new_task"
    if $stashed; then
        log_warn "Restoring stash..."
        git stash pop 2>/dev/null || true
    fi
    exit 1
fi

log_step "Updating worktree dashboard"
if update_worktree_dashboard "$new_task"; then
    log_success "Updated worktree dashboard"
else
    log_error "Failed to update worktree dashboard"
    if $stashed; then
        log_warn "Restoring stash..."
        git stash pop 2>/dev/null || true
    fi
    exit 1
fi

if $stashed; then
    log_step "Applying saved changes"
    if git stash pop; then
        log_success "Applied changes to $new_task"
    else
        log_warn "Stash pop failed (conflicts?). Run 'git stash pop' manually."
    fi
fi

echo ""
log_success "Workflow rotated successfully!"
echo "  Previous branch: ${YELLOW}$old_branch${NC} (preserved)"
echo "  Current branch:  ${GREEN}$new_task${NC}"
echo ""
