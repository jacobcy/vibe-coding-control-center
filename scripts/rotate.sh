#!/usr/bin/env zsh
# scripts/rotate.sh - 从当前 worktree 旋转到新的可发布 workflow
# 用法: ./scripts/rotate.sh <new-branch-name>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${(%):-%N}")" && pwd)"
export VIBE_ROOT="${VIBE_ROOT:-${SCRIPT_DIR:h}}"
export VIBE_LIB="${VIBE_LIB:-$VIBE_ROOT/lib}"

source "$VIBE_LIB/config.sh"
source "$VIBE_LIB/utils.sh"
source "$VIBE_LIB/flow.sh"

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

new_task="${1:-}"
if [[ -z "$new_task" ]]; then
    echo "Usage: $0 <new-branch-name>"
    echo "  兼容入口：委托给内部 flow new 逻辑，并保留原始 branch 名称"
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

old_branch=$(git branch --show-current)
if [[ -z "$old_branch" ]]; then
    log_error "Not on a branch."
    exit 1
fi
_flow_switch_target_branch() { echo "$1"; }
_flow_new "$new_task" --branch "$old_branch" --save-unstash
