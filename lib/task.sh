#!/usr/bin/env zsh

_vibe_task_common_dir() {
    git rev-parse --is-inside-work-tree >/dev/null 2>&1 || {
        vibe_die "Not in a git repository"
        return 1
    }
    git rev-parse --git-common-dir
}

_vibe_task_require_file() {
    local path="$1"
    local label="$2"

    [[ -f "$path" ]] || {
        vibe_die "Missing $label: $path"
        return 1
    }
}

_vibe_task_missing_tasks() {
    local worktrees_file="$1"
    local registry_file="$2"

    jq -r --slurpfile registry "$registry_file" '
        [
          .worktrees[]? as $worktree
          | select($worktree.current_task != null)
          | select(
              (($registry[0].tasks // []) | map(.task_id) | index($worktree.current_task)) == null
            )
          | $worktree.current_task
        ]
        | unique[]
    ' "$worktrees_file"
}

_vibe_task_render() {
    local worktrees_file="$1"
    local registry_file="$2"
    local show_all="$3"

    echo "==== Vibe Task Overview ===="
    echo ""

    echo "--- Active Worktrees ---"
    jq -r --slurpfile registry "$registry_file" '
        (
            [ .worktrees[]? ] | 
            if length == 0 then
                ["  (No active worktrees)", ""]
            else
                map(
                    . as $worktree
                    | (($registry[0].tasks // []) | map(select(.task_id == $worktree.current_task)) | .[0]) as $task
                    | [
                        "- \($worktree.worktree_name // "-")",
                        "  path: \($worktree.worktree_path // "-")",
                        "  branch: \($worktree.branch // "-")",
                        "  state: \($worktree.status // "-") \(if $worktree.dirty then "dirty" else "clean" end)",
                        "  task: \($worktree.current_task // "-")",
                        "  title: \($task.title // "-")",
                        "  status: \($task.status // "-")",
                        "  current subtask: \($task.current_subtask_id // "-")",
                        "  next step: \($task.next_step // "-")",
                        ""
                      ]
                ) | flatten
            end
        ) | .[]
    ' "$worktrees_file"

    echo "--- Task Registry Overview ---"
    jq -r --arg show_all "$show_all" '
        (
            [ (.tasks // [])[] | select($show_all == "1" or (.status == "in_progress" or .status == "planning" or .status == "todo")) ] |
            if length == 0 then
                ["  (No tasks found matching criteria)", ""]
            else
                map(
                    [
                        "- \(.task_id // "-")",
                        "  title: \(.title // "-")",
                        "  status: \(.status // "-")",
                        "  assigned: \(.assigned_worktree // "-")",
                        "  subtask: \(.current_subtask_id // "-")",
                        "  next step: \(.next_step // "-")",
                        ""
                    ]
                ) | flatten
            end
        ) | .[]
    ' "$registry_file"
}

vibe_task() {
    local common_dir
    local worktrees_file
    local registry_file
    local missing_tasks
    local show_all="0"

    for arg in "$@"; do
        case "$arg" in
            -a|--all) show_all="1" ;;
            -h|--help) 
                echo "Usage: vibe task [-a|--all]"
                echo "  Show active worktrees and tasks in the registry."
                echo "  -a, --all    Show all tasks including completed/archived."
                return 0
                ;;
        esac
    done

    vibe_require git jq || return 1

    common_dir="$(_vibe_task_common_dir)" || return 1
    worktrees_file="$common_dir/vibe/worktrees.json"
    registry_file="$common_dir/vibe/registry.json"

    _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    _vibe_task_require_file "$registry_file" "registry.json" || return 1

    missing_tasks="$(_vibe_task_missing_tasks "$worktrees_file" "$registry_file")" || return 1
    [[ -z "$missing_tasks" ]] || {
        vibe_die "Task not found in registry: ${missing_tasks%%$'\n'*}"
        return 1
    }

    _vibe_task_render "$worktrees_file" "$registry_file" "$show_all"
}
