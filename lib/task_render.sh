#!/usr/bin/env zsh
# lib/task_render.sh - Task rendering logic

_vibe_task_render() {
    local worktrees_file="$1" registry_file="$2" openspec_tasks_file="$3" show_all="$4" current_task_id="$5"
    echo "${BOLD}==== Vibe Task Registry ====${NC}"
    echo ""
    jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" \
      --arg cur "$current_task_id" --arg show_all "$show_all" \
      --arg BOLD "$BOLD" --arg GREEN "$GREEN" --arg CYAN "$CYAN" --arg NC "$NC" \
      '
      ((($registry[0].tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all 
      | {
          current: ($all | map(select(.task_id == $cur))),
          active: ($all | map(select(.task_id != $cur and ((.status // "") != "completed" and (.status // "") != "archived" and (.status // "") != "done" and (.status // "") != "skipped")))),
          completed: ($all | map(select(.task_id != $cur and ((.status // "") == "completed" or (.status // "") == "archived" or (.status // "") == "done" or (.status // "") == "skipped"))))
        } as $groups
      | (
          if ($groups.current | length) > 0 then ["\($GREEN)\($BOLD)● Current Task\($NC)", ($groups.current[] | "  - \(.task_id) \(.title) [\(.status)]\n    Next: \(.next_step // "No plan")"), ""] else [] end,
          if ($groups.active | length) > 0 then ["\($CYAN)\($BOLD)○ Other Active Tasks\($NC)", ($groups.active[] | "  - \(.task_id) \(.title) [\(.status)]\n    Next: \(.next_step // "No plan")"), ""] else [] end,
          if ($show_all == "1" and ($groups.completed | length) > 0) then ["\($NC)\($BOLD)◌ Completed/Archived Tasks\($NC)", ($groups.completed[] | "  - \(.task_id) \(.title) [\(.status)]"), ""] else [] end
        ) | flatten | .[]
      )' "$worktrees_file"
}
