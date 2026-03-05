#!/usr/bin/env zsh
# lib/task_write.sh - Task Write/Persistence operations

_vibe_task_write_registry() {
    local registry_file="$1" task_id="$2" task_status="$3" next_step="$4" assigned="$5" assigned_mode="$6" agent="$7" now="$8" tmp
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg assigned_mode "$assigned_mode" --arg agent "$agent" --arg now "$now" '
      .tasks |= map(if .task_id == $task_id then
        (if $task_status != "" then .status = $task_status else . end)
        | (if $next_step != "" then .next_step = $next_step else . end)
        | (if $assigned_mode == "set" then .assigned_worktree = (if $assigned == "" then null else $assigned end)
           elif $assigned_mode == "clear" then .assigned_worktree = null
           else . end)
        | (if $agent != "" then .agent = $agent else . end)
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
    local common_dir="$1" registry_file="$2" task_id="$3" now="$4" task_file tmp task_title task_status next_step assigned
    task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    task_title="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .title // ""' "$registry_file")"
    task_status="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .status // "todo"' "$registry_file")"
    next_step="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .next_step // ""' "$registry_file")"
    assigned="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .assigned_worktree // ""' "$registry_file")"
    mkdir -p "$(dirname "$task_file")"; tmp="$(mktemp)" || return 1
    if [[ -f "$task_file" ]]; then
        jq --arg task_id "$task_id" --arg task_title "$task_title" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg now "$now" '
          .task_id = $task_id | .title = (if (.title // "") == "" then $task_title else .title end) | .subtasks = (.subtasks // []) | .status = $task_status | .assigned_worktree = (if $assigned == "" then null else $assigned end) | .next_step = $next_step | .updated_at = $now
        ' "$task_file" >"$tmp" && mv "$tmp" "$task_file"
    else
        jq -n --arg task_id "$task_id" --arg task_title "$task_title" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg now "$now" '
          {task_id: $task_id, title: $task_title, status: $task_status, subtasks: [], assigned_worktree: (if $assigned == "" then null else $assigned end), next_step: $next_step, updated_at: $now}
        ' >"$tmp" && mv "$tmp" "$task_file"
    fi
}

_vibe_task_refresh_cache() {
    local common_dir="$1" registry_file="$2" task_id="$3" worktree_name="$4" now="$5" task_path title next_step subtask_json worktrees_file tasks_json
    local vibe_dir=".vibe"; mkdir -p "$vibe_dir"; task_path="$common_dir/vibe/tasks/$task_id/task.json"
    worktrees_file="$common_dir/vibe/worktrees.json"
    title="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .title // ""' "$registry_file")"; next_step="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .next_step // ""' "$registry_file")"
    subtask_json="$(jq -c --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | (.current_subtask_id // null)' "$registry_file")"
    tasks_json="$(jq -c --arg wt "$worktree_name" '.worktrees[]? | select(.worktree_name == $wt) | .tasks // []' "$worktrees_file" 2>/dev/null || echo "[]")"
    jq -n --arg task_id "$task_id" --arg task_path "$task_path" --arg registry_path "$registry_file" --arg worktree_name "$worktree_name" --argjson tasks "${tasks_json:-[]}" --arg updated_at "$now" \
       '{task_id:$task_id, tasks:$tasks, task_path:$task_path, registry_path:$registry_path, worktree_name:$worktree_name, updated_at:$updated_at}' > "$vibe_dir/current-task.json"
    cat > "$vibe_dir/focus.md" <<EOF
# Focus
- task: $task_id
- title: $title
- next_step: $next_step
EOF
    jq -n --arg worktree_name "$worktree_name" --arg current_task "$task_id" --argjson tasks "${tasks_json:-[]}" --arg saved_at "$now" --argjson current_subtask_id "${subtask_json:-null}" \
       '{worktree_name:$worktree_name, current_task:$current_task, tasks:$tasks, current_subtask_id:$current_subtask_id, saved_at:$saved_at}' > "$vibe_dir/session.json"
}
