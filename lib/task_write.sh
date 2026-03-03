#!/usr/bin/env zsh
# lib/task_write.sh - Task Write/Persistence operations

_vibe_task_write_registry() {
    local registry_file="$1" task_id="$2" task_status="$3" next_step="$4" assigned="$5" agent="$6" now="$7" tmp
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg task_status "$task_status" --arg next_step "$next_step" --arg assigned "$assigned" --arg agent "$agent" --arg now "$now" '
      .tasks |= map(if .task_id == $task_id then
        (if $task_status != "" then .status = $task_status else . end)
        | (if $next_step != "" then .next_step = $next_step else . end)
        | (if $assigned != "" then .assigned_worktree = $assigned else . end)
        | (if $agent != "" then .agent = $agent else . end)
        | .updated_at = $now
      else . end)
    ' "$registry_file" >"$tmp" && mv "$tmp" "$registry_file"
}

_vibe_task_write_worktrees() {
    local worktrees_file="$1" target_name="$2" target_path="$3" task_id="$4" branch="$5" agent="$6" bind_current="$7" now="$8" tmp
    [[ -n "$target_name" || -n "$target_path" ]] || return 0
    tmp="$(mktemp)" || return 1
    jq --arg target_name "$target_name" --arg target_path "$target_path" --arg task_id "$task_id" --arg branch "$branch" --arg agent "$agent" --arg now "$now" --argjson bind_current "$bind_current" '
      .worktrees = ((.worktrees // []) as $items | ([ $items[] | select(.worktree_name == $target_name or ($target_path != "" and .worktree_path == $target_path)) ] | length) as $hits
        | if $hits == 0 and $bind_current then
            $items + [{worktree_name:$target_name, worktree_path:$target_path, branch:($branch | select(. != "")), current_task:$task_id, status:"active", dirty:false, agent:($agent | select(. != "")), last_updated:$now}]
          else
            $items | map(if .worktree_name == $target_name or ($target_path != "" and .worktree_path == $target_path) then
              (if $target_path != "" then .worktree_path = $target_path else . end)
              | (if $branch != "" then .branch = $branch else . end)
              | (if $agent != "" then .agent = $agent else . end)
              | (if $bind_current then .current_task = $task_id | .status = "active" else . end)
              | .last_updated = $now
            else . end)
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
    local common_dir="$1" registry_file="$2" task_id="$3" worktree_name="$4" now="$5" task_path title next_step subtask_json
    local vibe_dir=".vibe"; mkdir -p "$vibe_dir"; task_path="$common_dir/vibe/tasks/$task_id/task.json"
    title="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .title // ""' "$registry_file")"; next_step="$(jq -r --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | .next_step // ""' "$registry_file")"
    subtask_json="$(jq -c --arg task_id "$task_id" '.tasks[] | select(.task_id == $task_id) | (.current_subtask_id // null)' "$registry_file")"
    jq -n --arg task_id "$task_id" --arg task_path "$task_path" --arg registry_path "$registry_file" --arg worktree_name "$worktree_name" --arg updated_at "$now" '{task_id:$task_id, task_path:$task_path, registry_path:$registry_path, worktree_name:$worktree_name, updated_at:$updated_at}' > "$vibe_dir/current-task.json"
    cat > "$vibe_dir/focus.md" <<EOF
# Focus
- task: $task_id
- title: $title
- next_step: $next_step
EOF
    jq -n --arg worktree_name "$worktree_name" --arg current_task "$task_id" --arg saved_at "$now" --argjson current_subtask_id "${subtask_json:-null}" '{worktree_name:$worktree_name, current_task:$current_task, current_subtask_id:$current_subtask_id, saved_at:$saved_at}' > "$vibe_dir/session.json"
}
