#!/usr/bin/env zsh
# lib/task_query.sh - Read/Query operations for Task module

_vibe_task_list() {
    local common_dir worktrees_file registry_file show_all="0" json_out="0" missing repo_root
    for arg in "$@"; do
        case "$arg" in
            -a|--all) show_all="1" ;;
            --json) json_out="1" ;;
            -h|--help)
                _vibe_task_usage
                echo "  Show active worktrees and tasks in the registry."
                echo "  -a, --all    Show all tasks including completed/archived."
                echo "  --json       Output merged task/worktree data as JSON."
                return 0
                ;;
            *) vibe_die "Unknown list option: $arg"; return 1 ;;
        esac
    done
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1
    worktrees_file="$common_dir/vibe/worktrees.json"
    registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"

    if [[ "$json_out" == "1" ]]; then
        return 0
    fi

    local cur_tid; cur_tid="$(jq -r '.task_id // empty' .vibe/current-task.json 2>/dev/null || true)"
    if [[ -z "$cur_tid" ]]; then
        local current_wt_path; current_wt_path=$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")
        cur_tid="$(jq -r --arg p "$current_wt_path" '.worktrees[]? | select(.worktree_path == $p) | .current_task // empty' "$worktrees_file" | head -1)"
    fi

    _vibe_task_render "$worktrees_file" "$registry_file" "$show_all" "$cur_tid"
}
