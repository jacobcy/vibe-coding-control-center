#!/usr/bin/env zsh
# lib/task_query.sh - Read/Query operations for Task module
_vibe_task_collect_openspec_tasks() {
    local repo_root="$1" changes_dir="$repo_root/openspec/changes" aggregate_file change_dir change_name
    local bridge_script="$VIBE_ROOT/scripts/openspec_bridge.sh"
    local task_json tasks_file total_tasks done_tasks change_status next_step
    [[ -d "$changes_dir" ]] || { echo '{"tasks":[]}'; return 0; }
    aggregate_file="$(mktemp)" || return 1
    echo '[]' > "$aggregate_file"
    { setopt nullglob 2>/dev/null || shopt -s nullglob 2>/dev/null; } || true
    for change_dir in "$changes_dir"/*; do
        [[ -d "$change_dir" ]] || continue
        change_name="$(basename "$change_dir")"
        [[ "$change_name" == "archive" ]] && continue

        task_json=""
        if [[ -f "$bridge_script" ]]; then
            task_json="$(cd "$repo_root" && zsh "$bridge_script" find "$change_name" 2>/dev/null || true)"
            if [[ -n "$task_json" ]] && echo "$task_json" | jq -e . >/dev/null 2>&1; then
                task_json="$(echo "$task_json" | jq -c --arg cid "$change_name" '{
                    task_id: (.task_id // $cid),
                    title: (.title // $cid),
                    framework: (.framework // "openspec"),
                    source_path: (.source_path // ("openspec/changes/" + $cid)),
                    status: (.status // "todo"),
                    spec_standard: "openspec",
                    spec_ref: (.source_path // ("openspec/changes/" + $cid)),
                    current_subtask_id: null,
                    runtime_worktree_name: null,
                    assigned_worktree: null,
                    next_step: (.next_step // ("Continue OpenSpec change: openspec/changes/" + $cid + "/tasks.md"))
                }')"
            else
                task_json=""
            fi
        fi
        if [[ -z "$task_json" ]]; then
            tasks_file="$change_dir/tasks.md"
            total_tasks=0
            done_tasks=0
            if [[ -f "$tasks_file" ]]; then
                total_tasks="$(grep -E '^- \[( |x|X)\]' "$tasks_file" 2>/dev/null | wc -l | tr -d ' ')"
                done_tasks="$(grep -E '^- \[[xX]\]' "$tasks_file" 2>/dev/null | wc -l | tr -d ' ')"
            fi
            if [[ "$total_tasks" -gt 0 && "$done_tasks" -eq "$total_tasks" ]]; then
                change_status="completed"
            elif [[ "$done_tasks" -gt 0 ]]; then
                change_status="in_progress"
            else
                change_status="todo"
            fi
            next_step="Continue OpenSpec change: openspec/changes/$change_name/tasks.md"
            task_json="$(jq -nc --arg task_id "$change_name" --arg title "$change_name" \
                --arg framework "openspec" --arg source_path "openspec/changes/$change_name" \
                --arg status "$change_status" --arg next_step "$next_step" \
                '{task_id:$task_id,title:$title,framework:$framework,source_path:$source_path,status:$status,spec_standard:"openspec",spec_ref:$source_path,current_subtask_id:null,runtime_worktree_name:null,assigned_worktree:null,next_step:$next_step}')"
        fi
        jq --argjson t "$task_json" '. += [$t]' "$aggregate_file" > "$aggregate_file.tmp" && mv "$aggregate_file.tmp" "$aggregate_file"
    done
    jq -n --slurpfile tasks "$aggregate_file" '{"tasks":($tasks[0] // [])}'
    rm -f "$aggregate_file"
}

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

_vibe_task_list() {
    local common_dir worktrees_file registry_file worktrees_source cleanup_worktrees_source="0"
    local show_all="0" json_out="0" missing repo_root openspec_tasks_file
    local status_filter="" source_filter="" keywords="" list_has_filters="0"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            -a|--all)
                show_all="1"
                shift
                ;;
            --json)
                json_out="1"
                shift
                ;;
            --status)
                [[ $# -ge 2 ]] || { vibe_die "Missing value for --status"; return 1; }
                status_filter="$2"
                list_has_filters="1"
                shift 2
                ;;
            --source)
                [[ $# -ge 2 ]] || { vibe_die "Missing value for --source"; return 1; }
                source_filter="$2"
                list_has_filters="1"
                shift 2
                ;;
            --keywords)
                [[ $# -ge 2 ]] || { vibe_die "Missing value for --keywords"; return 1; }
                keywords="${2:l}"
                list_has_filters="1"
                shift 2
                ;;
            -h|--help)
                _vibe_task_usage
                echo "  Show active worktrees and tasks in the registry."
                echo "  -a, --all         Show all tasks including completed/archived."
                echo "  --status <state>  Filter by status."
                echo "  --source <type>   Filter by source (issue|local|openspec)."
                echo "  --keywords <txt>  Keyword search in task id/title/next_step."
                echo "  --json            Output merged task/worktree data as JSON."
                return 0
                ;;
            *)
                vibe_die "Unknown list option: $1"
                return 1
                ;;
        esac
    done
    [[ -z "$status_filter" || "$status_filter" == "todo" || "$status_filter" == "in_progress" || "$status_filter" == "blocked" || "$status_filter" == "completed" || "$status_filter" == "archived" ]] || { vibe_die "Invalid status filter: $status_filter"; return 1; }
    [[ -z "$source_filter" || "$source_filter" == "issue" || "$source_filter" == "local" || "$source_filter" == "openspec" ]] || { vibe_die "Invalid source filter: $source_filter"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1
    worktrees_file="$common_dir/vibe/worktrees.json"
    registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    if [[ -f "$worktrees_file" ]]; then
        worktrees_source="$worktrees_file"
        missing="$(jq -r --slurpfile reg "$registry_file" '.worktrees[] | .current_task | select(. != null) as $ct | select([$reg[0].tasks[] | select(.task_id == $ct)] | length == 0)' "$worktrees_file" | head -n 1)"
        [[ -n "$missing" ]] && { vibe_die "Task not found in registry: $missing"; return 1; }
    else
        worktrees_source="$(mktemp)" || return 1
        cleanup_worktrees_source="1"
        printf '%s\n' '{"schema_version":"v1","worktrees":[]}' > "$worktrees_source"
    fi
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
    openspec_tasks_file="$(mktemp)" || return 1
    _vibe_task_collect_openspec_tasks "$repo_root" > "$openspec_tasks_file"
    if [[ "$json_out" == "1" ]]; then
        jq -n --slurpfile reg "$registry_file" --slurpfile wt "$worktrees_source" --slurpfile os "$openspec_tasks_file" \
          --arg status "$status_filter" \
          --arg source "$source_filter" \
          --arg keywords "$keywords" \
          --arg show_all "$show_all" \
          'def norm_status:
             if . == "review" then "in_progress"
             elif . == "done" or . == "merged" then "completed"
             elif . == "skipped" then "archived"
             else . end;
           def norm_source:
             if (.source_type // "") != "" then .source_type
             elif (.framework // "") == "openspec" then "openspec"
             else "local" end;
           {tasks: ((($reg[0].tasks // []) + ($os[0].tasks // [])
              | unique_by(.task_id)
              | map(.status = ((.status // "todo") | norm_status))
              | map(.source_type = norm_source)
              | map(.spec_standard = (.spec_standard // (if .source_type == "openspec" then "openspec" else "none" end)))
              | map(.spec_ref = (.spec_ref // null))
              | map(.runtime_worktree_name = (.runtime_worktree_name // .assigned_worktree // null))
              | map(del(.github_project_item_id, .content_type))
              | map(select(
                  ($status == "" or .status == $status)
                  and ($source == "" or .source_type == $source)
                  and ($keywords == "" or ((.task_id + " " + (.title // "") + " " + (.next_step // "")) | ascii_downcase | contains($keywords)))
                  and ($show_all == "1" or (.status != "completed" and .status != "archived"))
              ))
            )), worktrees: ($wt[0].worktrees // [])}'
        rm -f "$openspec_tasks_file"
        [[ "$cleanup_worktrees_source" == "1" ]] && rm -f "$worktrees_source"
        return 0
    fi
    local cur_tid="" current_branch="" repo_root wt_name
    current_branch="$(git branch --show-current 2>/dev/null || echo "")"
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"; wt_name="$(basename "$repo_root")"
    cur_tid="$(jq -r --arg wn "$wt_name" '.worktrees[]? | select(.worktree_name == $wn) | .current_task // empty' "$worktrees_source" | head -1)"
    [[ -z "$cur_tid" ]] && cur_tid="$(jq -r --arg b "$current_branch" '.tasks[]? | select(.runtime_branch == $b and .status != "completed" and .status != "archived") | .task_id // empty' "$registry_file" | head -1)"
    if [[ "$list_has_filters" == "1" ]]; then
        local filtered_output
        filtered_output="$(jq -rn --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" \
          --arg status "$status_filter" \
          --arg source "$source_filter" \
          --arg keywords "$keywords" \
          --arg show_all "$show_all" \
          '
          def norm_status:
            if . == "review" then "in_progress"
            elif . == "done" or . == "merged" then "completed"
            elif . == "skipped" then "archived"
            else . end;
          def norm_source:
            if (.source_type // "") != "" then .source_type
            elif (.framework // "") == "openspec" then "openspec"
            else "local" end;
          ((($registry[0].tasks // []) + ($openspec[0].tasks // []))
            | unique_by(.task_id)
            | map(.status = ((.status // "todo") | norm_status))
            | map(.source_type = norm_source)
            | map(.spec_standard = (.spec_standard // (if .source_type == "openspec" then "openspec" else "none" end)))
            | map(.spec_ref = (.spec_ref // null))
            | map(del(.github_project_item_id, .content_type))
            | map(select(
                ($status == "" or .status == $status)
                and ($source == "" or .source_type == $source)
                and ($keywords == "" or ((.task_id + " " + (.title // "") + " " + (.next_step // "")) | ascii_downcase | contains($keywords)))
                and ($show_all == "1" or (.status != "completed" and .status != "archived"))
            ))
            | map("- \(.task_id) \(.title) [\(.status)] {\(.source_type)}")
            | .[])' 2>/dev/null)"
        if [[ -z "$filtered_output" ]]; then
            echo "No tasks found."
        else
            printf '%s\n' "$filtered_output"
        fi
        rm -f "$openspec_tasks_file"
        [[ "$cleanup_worktrees_source" == "1" ]] && rm -f "$worktrees_source"
        return 0
    fi
    _vibe_task_render "$worktrees_source" "$registry_file" "$openspec_tasks_file" "$show_all" "$cur_tid"
    rm -f "$openspec_tasks_file"
    [[ "$cleanup_worktrees_source" == "1" ]] && rm -f "$worktrees_source"
    return 0
}

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
