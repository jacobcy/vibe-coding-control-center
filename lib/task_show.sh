#!/usr/bin/env zsh
# lib/task_show.sh - Task show operations

_vibe_task_show() {
    local task_id="" json_out="0" common_dir registry_file task_file registry_json detail_json merged_json
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json) json_out="1"; shift ;;
            -h|--help)
                echo "Usage: vibe task show <task-id> [--json]"
                return 0
                ;;
            -*)
                vibe_die "Unknown show option: $1"
                return 1
                ;;
            *)
                if [[ -z "$task_id" ]]; then
                    task_id="$1"
                    shift
                else
                    vibe_die "Unexpected argument: $1"
                    return 1
                fi
                ;;
        esac
    done
    [[ -n "$task_id" ]] || { vibe_die "Usage: vibe task show <task-id> [--json]"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1
    registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    registry_json="$(jq -c --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" | head -n 1)"
    [[ -n "$registry_json" ]] || { vibe_die "Task not found in registry: $task_id"; return 1; }
    task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    if [[ -f "$task_file" ]]; then
        detail_json="$(jq -c '.' "$task_file")"
    else
        detail_json='{}'
    fi
    merged_json="$(jq -n \
        --argjson reg "$registry_json" \
        --argjson detail "$detail_json" \
        'def norm_status:
           if . == "review" then "in_progress"
           elif . == "done" or . == "merged" then "completed"
           elif . == "skipped" then "archived"
           else . end;
         ($detail + $reg)
         | .task_id = ($reg.task_id // .task_id)
         | .title = ($reg.title // .title)
         | .status = (($reg.status // .status // "todo") | norm_status)
         | .subtasks = (.subtasks // [])
         | .spec_standard = ($reg.spec_standard // .spec_standard // "none")
         | .spec_ref = ($reg.spec_ref // .spec_ref // null)
         | .runtime_worktree_name = (.runtime_worktree_name // .assigned_worktree // null)
         | .next_step = (.next_step // null)
         | del(.github_project_item_id, .content_type)' )"
    if [[ "$json_out" == "1" ]]; then
        echo "$merged_json"
        return 0
    fi
    echo "$merged_json" | jq -r '
        "Task: \(.task_id)\n" +
        "Title: \(.title)\n" +
        "Status: \(.status)\n" +
        "Runtime Worktree: \((.runtime_worktree_name // "null"))\n" +
        "Issue Refs: \((.issue_refs // []) | if length == 0 then "none" else join(", ") end)\n" +
        "Spec Ref: \((.spec_ref // "null"))\n" +
        "Next Step: \((.next_step // "null"))\n" +
        "Subtasks: \(.subtasks | length)"'
}