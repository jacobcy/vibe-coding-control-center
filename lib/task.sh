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

_vibe_task_collect_openspec_tasks() {
    local repo_root="$1"
    local changes_dir="$repo_root/openspec/changes"
    local aggregate_file
    local change_dir
    local change_name
    local tasks_file
    local total_tasks
    local done_tasks
    local change_status
    local next_step

    [[ -d "$changes_dir" ]] || {
        echo '{"tasks":[]}'
        return 0
    }

    aggregate_file="$(mktemp)"
    echo '[]' > "$aggregate_file"

    for change_dir in "$changes_dir"/*; do
        [[ -d "$change_dir" ]] || continue
        change_name="$(basename "$change_dir")"
        [[ "$change_name" == "archive" ]] && continue

        tasks_file="$change_dir/tasks.md"
        total_tasks=0
        done_tasks=0

        if [[ -f "$tasks_file" ]]; then
            total_tasks="$(grep -E '^- \[( |x|X)\]' "$tasks_file" | wc -l | tr -d ' ')"
            done_tasks="$(grep -E '^- \[[xX]\]' "$tasks_file" | wc -l | tr -d ' ')"
        fi

        if [[ "$total_tasks" -gt 0 && "$done_tasks" -eq "$total_tasks" ]]; then
            change_status="completed"
        elif [[ "$done_tasks" -gt 0 ]]; then
            change_status="in-progress"
        else
            change_status="todo"
        fi

        next_step="Continue OpenSpec change: openspec/changes/$change_name/tasks.md"

        jq \
            --arg task_id "$change_name" \
            --arg title "$change_name" \
            --arg framework "openspec" \
            --arg source_path "openspec/changes/$change_name" \
            --arg status "$change_status" \
            --arg next_step "$next_step" \
            '. += [{
              "task_id": $task_id,
              "title": $title,
              "framework": $framework,
              "source_path": $source_path,
              "status": $status,
              "current_subtask_id": null,
              "assigned_worktree": null,
              "next_step": $next_step
            }]' \
            "$aggregate_file" > "$aggregate_file.tmp" && mv "$aggregate_file.tmp" "$aggregate_file"
    done

    jq -n --slurpfile tasks "$aggregate_file" '{"tasks":($tasks[0] // [])}'
    rm -f "$aggregate_file"
}

_vibe_task_missing_tasks() {
    local worktrees_file="$1"
    local registry_file="$2"
    local openspec_tasks_file="$3"

    jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" '
        (($registry[0].tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all_tasks |
        [
          .worktrees[]? as $worktree
          | select($worktree.current_task != null)
          | select(
              ($all_tasks | map(.task_id) | index($worktree.current_task)) == null
            )
          | $worktree.current_task
        ]
        | unique[]
    ' "$worktrees_file"
}

_vibe_task_render() {
    local worktrees_file="$1"
    local registry_file="$2"
    local openspec_tasks_file="$3"
    local show_all="$4"

    echo "==== Vibe Task Overview ===="
    echo ""

    echo "--- Active Worktrees ---"
    jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" '
        (($registry[0].tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all_tasks |
        (
            [ .worktrees[]? ] |
            if length == 0 then
                ["  (No active worktrees)", ""]
            else
                map(
                    . as $worktree
                    | ($all_tasks | map(select(.task_id == $worktree.current_task)) | .[0]) as $task
                    | [
                        "- \($worktree.worktree_name // "-")",
                        "  path: \($worktree.worktree_path // "-")",
                        "  branch: \($worktree.branch // "-")",
                        "  state: \($worktree.status // "-") \(if $worktree.dirty then "dirty" else "clean" end)",
                        "  task: \($worktree.current_task // "-")",
                        "  title: \($task.title // "-")",
                        "  framework: \($task.framework // "vibe")",
                        "  source: \($task.source_path // "-")",
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
    jq -r --slurpfile openspec "$openspec_tasks_file" --arg show_all "$show_all" '
        ((.tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all_tasks |
        (
            [ $all_tasks[] | select(
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
                        "  framework: \(.framework // "vibe")",
                        "  source: \(.source_path // "-")",
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
    local openspec_tasks_file
    local repo_root
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

    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
    openspec_tasks_file="$(mktemp)"
    _vibe_task_collect_openspec_tasks "$repo_root" > "$openspec_tasks_file"

    missing_tasks="$(_vibe_task_missing_tasks "$worktrees_file" "$registry_file" "$openspec_tasks_file")" || {
        rm -f "$openspec_tasks_file"
        return 1
    }
    [[ -z "$missing_tasks" ]] || {
        rm -f "$openspec_tasks_file"
        vibe_die "Task not found in registry: ${missing_tasks%%$'\n'*}"
        return 1
    }

    _vibe_task_render "$worktrees_file" "$registry_file" "$openspec_tasks_file" "$show_all"
    rm -f "$openspec_tasks_file"
}
