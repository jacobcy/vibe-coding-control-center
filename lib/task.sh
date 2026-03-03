#!/usr/bin/env zsh
# v2/lib/task.sh - Task Management Module
# Target: ~100 lines | Orchestrates task registry and worktree binding

_vibe_task_common_dir() { git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { vibe_die "Not in a git repository"; return 1; }; git rev-parse --git-common-dir; }
_vibe_task_now() { date +"%Y-%m-%dT%H:%M:%S%z"; }
_vibe_task_today() { date +"%Y-%m-%d"; }
_vibe_task_slugify() { print -r -- "$1" | tr '[:upper:]' '[:lower:]' | sed -E "s/[^a-z0-9]+/-/g; s/^-+//; s/-+$//"; }
_vibe_task_require_file() { [[ -f "$1" ]] || { vibe_die "Missing $2: $1"; return 1; }; }
_vibe_task_task_file() { echo "$1/vibe/tasks/$2/task.json"; }

# Load sub-modules
source "$VIBE_LIB/task_render.sh"
source "$VIBE_LIB/task_write.sh"
source "$VIBE_LIB/task_help.sh"
source "$VIBE_LIB/task_query.sh"
source "$VIBE_LIB/task_actions.sh"

vibe_task() {
    local subcommand="${1:-list}"
    case "$subcommand" in
        list) [[ $# -gt 0 ]] && shift; _vibe_task_list "$@" ;;
        add) [[ $# -gt 0 ]] && shift; _vibe_task_add "$@" ;;
        update) [[ $# -gt 0 ]] && shift; _vibe_task_update "$@" ;;
        remove) [[ $# -gt 0 ]] && shift; _vibe_task_remove "$@" ;;
        sync) [[ $# -gt 0 ]] && shift; _vibe_task_sync "$@" ;;
        -h|--help|help) _vibe_task_usage ;;
        -*) _vibe_task_list "$@" ;;
        "") _vibe_task_list ;;
        *) vibe_die "Unknown task subcommand: $subcommand"; return 1 ;;
    esac
}

