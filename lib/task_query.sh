#!/usr/bin/env zsh
# lib/task_query.sh - Read/Query operations for Task module

_vibe_task_branch_active_tasks_json() {
    local branch="${1#origin/}" registry_file="${2:-}"
    [[ -n "$registry_file" ]] || registry_file="$(_vibe_task_common_dir 2>/dev/null)/vibe/registry.json"
    [[ -f "$registry_file" ]] || { echo '[]'; return 0; }
    jq -c --arg branch "$branch" '
      [.tasks[]?
        | select((.status // "") != "completed" and (.status // "") != "archived")
        | select((.runtime_branch // "") == $branch or (.runtime_branch // "") == ("origin/" + $branch))
      ]
    ' "$registry_file" 2>/dev/null
}

_vibe_task_branch_focus_task_id() {
    local branch="${1#origin/}" registry_file="${2:-}" tasks_json count task_ids
    tasks_json="$(_vibe_task_branch_active_tasks_json "$branch" "$registry_file")" || return 1
    count="$(printf '%s' "$tasks_json" | jq 'length' 2>/dev/null || echo 0)"
    if [[ "$count" -eq 0 ]]; then
        echo ""
        return 0
    fi
    if [[ "$count" -eq 1 ]]; then
        printf '%s' "$tasks_json" | jq -r '.[0].task_id // empty'
        return 0
    fi
    task_ids="$(printf '%s' "$tasks_json" | jq -r '.[].task_id' 2>/dev/null | paste -sd ", " -)"
    vibe_die "Multiple active tasks are bound to branch '$branch': $task_ids"
    return 2
}

_vibe_task_branch_active_task_ids_json() {
    local branch="${1#origin/}" registry_file="${2:-}" tasks_json
    tasks_json="$(_vibe_task_branch_active_tasks_json "$branch" "$registry_file")" || return 1
    printf '%s' "$tasks_json" | jq -c '[.[].task_id]'
}

# Get all tasks (including completed/archived) for a branch - used by flow done
_vibe_task_branch_all_tasks_json() {
    local branch="${1#origin/}" registry_file="${2:-}"
    [[ -n "$registry_file" ]] || registry_file="$(_vibe_task_common_dir 2>/dev/null)/vibe/registry.json"
    [[ -f "$registry_file" ]] || { echo '[]'; return 0; }
    jq -c --arg branch "$branch" '
      [.tasks[]?
        | select((.runtime_branch // "") == $branch or (.runtime_branch // "") == ("origin/" + $branch))
      ]
    ' "$registry_file" 2>/dev/null
}

_vibe_task_branch_all_task_ids_json() {
    local branch="${1#origin/}" registry_file="${2:-}" tasks_json
    tasks_json="$(_vibe_task_branch_all_tasks_json "$branch" "$registry_file")" || return 1
    printf '%s' "$tasks_json" | jq -c '[.[].task_id]'
}

_vibe_task_count_by_branch() {
    local branch="$1" common_dir worktrees_file registry_file count
    common_dir="$(_vibe_task_common_dir)" || { echo "0"; return 0; }
    worktrees_file="$common_dir/vibe/worktrees.json"
    registry_file="$common_dir/vibe/registry.json"
    if [[ -f "$worktrees_file" ]]; then
      count=$(jq -rn --arg branch "$branch" \
        --slurpfile wt "${worktrees_file}" \
        --slurpfile reg "${registry_file}" '
        ( [($wt[0].worktrees // [])[] | select(.branch == $branch) | (.tasks // [])[]]
        + [($reg[0].tasks   // [])[] | select(.runtime_branch == $branch and .status != "completed" and .status != "archived") | .task_id]
        ) | unique | length
      ' 2>/dev/null || echo "0")
    else
      count=$(jq -rn --arg branch "$branch" \
        --slurpfile reg "${registry_file}" '
        [($reg[0].tasks // [])[] | select(.runtime_branch == $branch and .status != "completed" and .status != "archived") | .task_id]
        | unique
        | length
      ' 2>/dev/null || echo "0")
    fi
    echo "${count:-0}"
}
