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

_vibe_task_usage() {
    echo "Usage: vibe task [list] [-a|--all]"
    echo "       vibe task add [options]"
    echo "       vibe task update <task-id> [options]"
    echo "       vibe task remove <task-id>"
}

_vibe_task_add_usage() {
    echo "Usage: vibe task add [options]"
    echo "  Register a task in the shared registry."
}

_vibe_task_update_usage() {
    echo "Usage: vibe task update <task-id> [options]"
    echo "  Supported fields: --status --agent --worktree --branch --bind-current --next-step"
}

_vibe_task_remove_usage() {
    echo "Usage: vibe task remove <task-id>"
    echo "  Remove a task from the shared registry."
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
            [ (.tasks // [])[] | select(
                $show_all == "1"
                or ((.status // "") != "completed"
                and (.status // "") != "archived"
                and (.status // "") != "done"
                and (.status // "") != "skipped")
              ) ] |
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

_vibe_task_list() {
    local common_dir
    local worktrees_file
    local registry_file
    local missing_tasks
    local show_all="0"

    for arg in "$@"; do
        case "$arg" in
            -a|--all) show_all="1" ;;
            -h|--help)
                _vibe_task_usage
                echo "  Show active worktrees and tasks in the registry."
                echo "  -a, --all    Show all tasks including completed/archived."
                return 0
                ;;
            *)
                vibe_die "Unknown list option: $arg"
                return 1
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

_vibe_task_add() {
    case "${1:-}" in
        -h|--help)
            _vibe_task_add_usage
            return 0
            ;;
    esac

    vibe_die "Task add is not implemented yet"
    return 1
}

_vibe_task_update() {
    local task_id="${1:-}"
    local has_changes="0"

    if [[ "$task_id" == "-h" || "$task_id" == "--help" ]]; then
        _vibe_task_update_usage
        return 0
    fi

    [[ -n "$task_id" ]] || {
        vibe_die "Missing task id for update"
        return 1
    }

    shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status|--agent|--worktree|--branch|--next-step)
                [[ $# -ge 2 ]] || {
                    vibe_die "Missing value for $1"
                    return 1
                }
                has_changes="1"
                shift 2
                ;;
            --bind-current)
                has_changes="1"
                shift
                ;;
            -h|--help)
                _vibe_task_update_usage
                return 0
                ;;
            *)
                vibe_die "Unknown update option: $1"
                return 1
                ;;
        esac
    done

    [[ "$has_changes" == "1" ]] || {
        vibe_die "No update fields provided"
        return 1
    }

    vibe_die "Task update is not implemented yet"
    return 1
}

_vibe_task_remove() {
    local task_id="${1:-}"

    if [[ "$task_id" == "-h" || "$task_id" == "--help" ]]; then
        _vibe_task_remove_usage
        return 0
    fi

    [[ -n "$task_id" ]] || {
        vibe_die "Missing task id for remove"
        return 1
    }

    vibe_die "Task remove is not implemented yet"
    return 1
}

vibe_task() {
    local subcommand="${1:-list}"

    case "$subcommand" in
        list)
            shift
            _vibe_task_list "$@"
            ;;
        add)
            shift
            _vibe_task_add "$@"
            ;;
        update)
            shift
            _vibe_task_update "$@"
            ;;
        remove)
            shift
            _vibe_task_remove "$@"
            ;;
        -h|--help)
            _vibe_task_usage
            ;;
        -*)
            _vibe_task_list "$@"
            ;;
        "")
            _vibe_task_list
            ;;
        *)
            vibe_die "Unknown task subcommand: $subcommand"
            return 1
            ;;
    esac
}
