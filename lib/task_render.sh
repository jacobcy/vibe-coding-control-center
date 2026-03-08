#!/usr/bin/env zsh
# lib/task_render.sh - Task rendering logic

_vibe_task_render() {
    local worktrees_file="$1" registry_file="$2" openspec_tasks_file="$3" show_all="$4" current_task_id="$5"
    echo "${BOLD}==== Vibe Task Registry Overview ====${NC}"
    echo ""
    jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" \
      --arg cur "$current_task_id" --arg show_all "$show_all" \
      --arg BOLD "$BOLD" --arg GREEN "$GREEN" --arg CYAN "$CYAN" --arg NC "$NC" \
      '
      def norm_status:
        if . == "review" then "in_progress"
        elif . == "done" or . == "merged" then "completed"
        elif . == "skipped" then "archived"
        else . end;
      ((($registry[0].tasks // []) + ($openspec[0].tasks // [])
          | unique_by(.task_id)
          | map(.status = ((.status // "todo") | norm_status))
          | map(.runtime_worktree_name = (.runtime_worktree_name // .assigned_worktree // null))
       ) as $all_tasks
      | .worktrees as $wts
      | (
          # 1. Render Worktree Groups
          ($wts[] |
            (.worktree_name) as $wn |
            (.current_task) as $ct |
            (.tasks // []) as $ids |
            
            # Determine if this is the focused worktree
            ([$wts[] | select(.current_task == $cur or (.tasks // [] | index($cur) != null)) | .worktree_name] | any(. == $wn)) as $is_cur_wt |

            # Map to task objects
            ($all_tasks | map(select(.task_id as $tid | $ids | index($tid) != null))) as $wt_tasks |

            if ($wt_tasks | length) > 0 then
              (if $is_cur_wt then "\($GREEN)\($BOLD)● WORKTREE: \($wn)\($NC)" else "\($CYAN)\($BOLD)○ WORKTREE: \($wn)\($NC)" end),
              ($wt_tasks[] |
                (if .task_id == $ct then "  [Main] " else "  [Sub ] " end) +
                "\(.task_id) \(.title) [\(.status)]" +
                (if .task_id == $cur then " \($GREEN)(focused)\($NC)" else "" end)
              ),
              ""
            else empty end
          ),

          # 2. Render Unassigned Tasks
          (($all_tasks | map(select(.runtime_worktree_name == null and (.task_id as $tid | ($wts | map(.tasks // []) | flatten | index($tid)) == null))) |
            map(select($show_all == "1" or (.status != "completed" and .status != "archived")))) as $u_tasks |
            if ($u_tasks | length) > 0 then
              "\($NC)\($BOLD)Unassigned Tasks\($NC)",
              ($u_tasks[] |
                "  - \(.task_id) \(.title) [\(.status)]" +
                (if (.framework // "") != "" then " {\(.framework)}" else "" end) +
                (if (.source_path // "") != "" then " <\(.source_path)>" else "" end)
              ),
              ""
            else empty end
          )
        )
      )' "$worktrees_file"
}
