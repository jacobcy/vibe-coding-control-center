#!/usr/bin/env zsh
# lib/task_list.sh - Task list operations

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
    if [[ "$cleanup_worktrees_source" == "1" ]]; then
        jq -nc --slurpfile reg "$registry_file" '{schema_version:"v1", worktrees: ([($reg[0].tasks // []) | map(select((.status // "") != "completed" and (.status // "") != "archived")) | map(select((.runtime_worktree_name // .assigned_worktree // "") != "")) | group_by(.runtime_worktree_name // .assigned_worktree) | .[] | {worktree_name:(.[0].runtime_worktree_name // .[0].assigned_worktree), worktree_path:(.[0].runtime_worktree_path // null), branch:(.[0].runtime_branch // null), current_task:null, tasks:(map(.task_id) | unique), status:"active"}])}' > "$worktrees_source"
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