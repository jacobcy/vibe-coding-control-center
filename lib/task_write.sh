#!/usr/bin/env zsh
# lib/task_write.sh - Task Write/Persistence operations

_vibe_task_write_registry() {
    local registry_file="$1" task_id="$2" task_status="$3" next_step="$4" runtime_name="$5" runtime_path="$6" runtime_branch="$7" runtime_mode="$8" runtime_agent="$9" now="${10}" issue_refs_json="${11}" issue_mode="${12}" roadmap_item_ids_json="${13}" roadmap_mode="${14}" pr_ref="${15}" pr_mode="${16}" spec_standard="${17}" spec_ref="${18}" spec_mode="${19}" tmp
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg task_status "$task_status" --arg next_step "$next_step" \
       --arg runtime_name "$runtime_name" --arg runtime_path "$runtime_path" --arg runtime_branch "$runtime_branch" --arg runtime_mode "$runtime_mode" --arg runtime_agent "$runtime_agent" \
       --arg now "$now" --argjson issue_refs "$issue_refs_json" --arg issue_mode "$issue_mode" \
       --argjson roadmap_item_ids "$roadmap_item_ids_json" --arg roadmap_mode "$roadmap_mode" --arg pr_ref "$pr_ref" --arg pr_mode "$pr_mode" \
       --arg spec_standard "$spec_standard" --arg spec_ref "$spec_ref" --arg spec_mode "$spec_mode" '
      .tasks |= map(if .task_id == $task_id then
        (if $task_status != "" then .status = $task_status else . end)
        | (if $next_step != "" then .next_step = $next_step else . end)
        | (if $runtime_mode == "set" then
             .runtime_worktree_name = (if $runtime_name == "" then null else $runtime_name end)
             | .runtime_worktree_path = (if $runtime_path == "" then .runtime_worktree_path // null else $runtime_path end)
             | .runtime_branch = (if $runtime_branch == "" then .runtime_branch // null else $runtime_branch end)
             | .runtime_agent = (if $runtime_agent == "" then .runtime_agent // null else $runtime_agent end)
             | .assigned_worktree = (if $runtime_name == "" then null else $runtime_name end)
           elif $runtime_mode == "clear" then
             .runtime_worktree_name = null
             | .runtime_worktree_path = null
             | .runtime_branch = null
             | .runtime_agent = null
             | .assigned_worktree = null
           else . end)
        | (if $runtime_mode != "set" and $runtime_branch != "" then .runtime_branch = $runtime_branch else . end)
        | (if $runtime_mode != "set" and $runtime_agent != "" then .runtime_agent = $runtime_agent else . end)
        | (if $runtime_agent != "" then 
             .agent = $runtime_agent 
             | (.agent_log // {planned_by: $runtime_agent, executed_by: [], committed_by: null, latest_actor: null}) as $log
             | .agent_log = ($log | .latest_actor = $runtime_agent | .executed_by = ((.executed_by + [$runtime_agent]) | unique))
           else . end)
        | .runtime_worktree_name = (.runtime_worktree_name // .assigned_worktree // null)
        | (if $issue_mode == "append" then .issue_refs = (((.issue_refs // []) + $issue_refs) | unique) else . end)
        | (if $roadmap_mode == "append" then .roadmap_item_ids = (((.roadmap_item_ids // []) + $roadmap_item_ids) | unique) else . end)
        | (if $pr_mode == "set" then .pr_ref = (if $pr_ref == "" then null else $pr_ref end) else . end)
        | (if $spec_mode == "set" then .spec_standard = $spec_standard | .spec_ref = (if $spec_ref == "" then null else $spec_ref end) else . end)
        | (if $task_status == "completed" then .completed_at = (.completed_at // $now) else . end)
        | (if $task_status == "archived" then .archived_at = (.archived_at // $now) else . end)
        | (if $task_status != "" and ($task_status != "completed" and $task_status != "archived") then .completed_at = null | .archived_at = null else . end)
        | .updated_at = $now
      else . end)
    ' "$registry_file" >"$tmp" && mv "$tmp" "$registry_file"
}

_vibe_task_write_worktrees() {
    local worktrees_file="$1" target_name="$2" target_path="$3" task_id="$4" branch="$5" agent="$6" bind_current="$7" now="$8" unassign="$9" tmp
    # echo "DEBUG: wt_file=$worktrees_file target=$target_name task=$task_id bind=$bind_current unassign=$unassign" >&2
    tmp="$(mktemp)" || return 1
    jq --arg target_name "$target_name" --arg target_path "$target_path" --arg task_id "$task_id" \
       --arg branch "$branch" --arg agent "$agent" --arg now "$now" \
       --argjson bind_current "$bind_current" --argjson unassign "${unassign:-false}" '
      .worktrees = ((.worktrees // []) as $items 
        | if $unassign then
            $items | map(
              if .current_task == $task_id then .current_task = null else . end
              | .tasks = ((.tasks // []) | map(select(. != $task_id)))
              | .last_updated = $now
            )
          else
            ([ $items[] | select(.worktree_name == $target_name or ($target_path != "" and .worktree_path == $target_path)) ] | length) as $hits
            | if $hits == 0 and $bind_current then
                $items + [{
                  worktree_name: $target_name,
                  worktree_path: $target_path,
                  branch: (if $branch == "" then null else $branch end),
                  current_task: $task_id,
                  tasks: [$task_id],
                  status: "active",
                  dirty: false,
                  agent: (if $agent == "" then null else $agent end),
                  last_updated: $now
                }]
              else
                $items | map(if .worktree_name == $target_name or ($target_path != "" and .worktree_path == $target_path) then
                  (if $target_path != "" then .worktree_path = $target_path else . end)
                  | .branch = (if $branch == "" then .branch else $branch end)
                  | .agent = (if $agent == "" then .agent else $agent end)
                  | (if $bind_current then 
                      .current_task = $task_id 
                      | .tasks = ((.tasks // []) as $t | if ($t | index($task_id)) == null then $t + [$task_id] else $t end)
                      | .status = "active" 
                    else . end)
                  | .last_updated = $now
                else . end)
              end
          end)
    ' "$worktrees_file" >"$tmp" && mv "$tmp" "$worktrees_file"
}

_vibe_task_write_task_file() {
    local common_dir="$1" registry_file="$2" task_id="$3" now="$4" task_file tmp registry_task_json
    task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    registry_task_json="$(jq -c --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id)' "$registry_file" | head -n 1)"
    [[ -n "$registry_task_json" ]] || return 1
    mkdir -p "$(dirname "$task_file")"; tmp="$(mktemp)" || return 1
    if [[ -f "$task_file" ]]; then
        jq --argjson reg "$registry_task_json" --arg now "$now" '
          (. + $reg)
          | .subtasks = (.subtasks // [])
          | .runtime_worktree_name = (.runtime_worktree_name // .assigned_worktree // null)
          | .assigned_worktree = (.runtime_worktree_name // .assigned_worktree // null)
          | .updated_at = $now
        ' "$task_file" >"$tmp" && mv "$tmp" "$task_file"
    else
        jq -n --argjson reg "$registry_task_json" --arg now "$now" '
          ($reg + {subtasks: ($reg.subtasks // [])})
          | .runtime_worktree_name = (.runtime_worktree_name // .assigned_worktree // null)
          | .assigned_worktree = (.runtime_worktree_name // .assigned_worktree // null)
          | .updated_at = $now
        ' >"$tmp" && mv "$tmp" "$task_file"
    fi
}
