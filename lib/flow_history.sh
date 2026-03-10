#!/usr/bin/env zsh

_flow_history_file() { echo "$(git rev-parse --git-common-dir)/vibe/flow-history.json"; }

_flow_history_ensure_file() {
  local history_file
  history_file="$(_flow_history_file 2>/dev/null)" || return 1
  mkdir -p "${history_file:h}"
  [[ -f "$history_file" ]] || printf '%s\n' '{"schema_version":"v1","flows":[]}' > "$history_file"
  echo "$history_file"
}

_flow_feature_slug() { local raw="${1#origin/}"; raw="${raw#refs/heads/}"; raw="${raw#task/}"; echo "$(_vibe_task_slugify "$raw")"; }

_flow_history_has_closed_feature() {
  local feature="$(_flow_feature_slug "$1")" history_file
  history_file="$(_flow_history_ensure_file)" || return 1
  jq -e --arg feature "$feature" '.flows[]? | select(.feature == $feature and .state == "closed")' "$history_file" >/dev/null 2>&1
}

_flow_history_show() {
  local target="$1" feature history_file
  feature="$(_flow_feature_slug "$target")"
  history_file="$(_flow_history_ensure_file)" || return 1
  jq -c --arg target "$target" --arg feature "$feature" '
    .flows[]?
    | select(.feature == $feature or .branch == $target or .branch == ("task/" + $feature))
  ' "$history_file" | tail -n 1
}

_flow_history_close() {
  local feature="$1" branch="$2" worktree_name="$3" worktree_path="$4" current_task="$5" tasks_json="$6" pr_ref="$7" now="$8" history_file tmp
  history_file="$(_flow_history_ensure_file)" || return 1
  tmp="$(mktemp)" || return 1
  jq \
    --arg feature "$feature" \
    --arg branch "$branch" \
    --arg worktree_name "$worktree_name" \
    --arg worktree_path "$worktree_path" \
    --arg current_task "$current_task" \
    --arg pr_ref "$pr_ref" \
    --arg now "$now" \
    --argjson tasks "${tasks_json:-[]}" '
    .flows = ((.flows // [])
      | map(select(.feature != $feature))
      | . + [{
          feature: $feature,
          branch: $branch,
          state: "closed",
          worktree_name: (if $worktree_name == "" then null else $worktree_name end),
          worktree_path: (if $worktree_path == "" then null else $worktree_path end),
          current_task: (if $current_task == "" then null else $current_task end),
          tasks: $tasks,
          pr_ref: (if $pr_ref == "" then null else $pr_ref end),
          closed_at: $now
      }])
  ' "$history_file" > "$tmp" && mv "$tmp" "$history_file"
}

_flow_branch_has_pr() {
  local branch_name="${1#origin/}" registry_file current_task
  if vibe_has gh; then
    gh pr view "$branch_name" --json number,state >/dev/null 2>&1 && return 0
  fi
  registry_file="$(_flow_registry_file)"
  current_task="$(jq -r --arg branch "$branch_name" '
    .tasks[]?
    | select(.runtime_branch == $branch or .runtime_branch == ("origin/" + $branch))
    | select((.pr_ref // "") != "")
    | .task_id
  ' "$registry_file" 2>/dev/null | head -n 1)"
  [[ -n "$current_task" ]]
}

_flow_branch_pr_merged() { local branch_name="${1#origin/}" pr_state=""; vibe_has gh || return 1; pr_state="$(gh pr view "$branch_name" --json state --jq '.state' 2>/dev/null || true)"; [[ "$pr_state" == "MERGED" ]]; }

_flow_close_branch_runtime() {
  local branch_name="${1#origin/}" git_common_dir worktrees_file tmp now
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 0
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  [[ -f "$worktrees_file" ]] || return 0
  now="$(_flow_now_iso)"
  tmp="$(mktemp)" || return 1
  jq --arg branch "$branch_name" --arg now "$now" '
    .worktrees = ((.worktrees // []) | map(
      if (.branch // "") == $branch or (.branch // "") == ("origin/" + $branch) then
        .branch = null
        | .current_task = null
        | .tasks = []
        | .status = "idle"
        | .last_updated = $now
      else . end
    ))
  ' "$worktrees_file" > "$tmp" && mv "$tmp" "$worktrees_file"
}

_flow_checkout_detached_main() {
  git fetch origin main --quiet 2>/dev/null || true
  git checkout --detach origin/main >/dev/null 2>&1 || git checkout --detach main >/dev/null 2>&1
}

_flow_branch_dashboard_entry() {
  local branch="$1" worktrees_file registry_file branch_name wt_data current_task tasks_json pr_ref issue_refs_json title task_status next_step spec_standard spec_ref
  worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
  registry_file="$(_flow_registry_file)"
  branch_name="${branch#origin/}"
  wt_data="$(jq -c --arg branch "$branch_name" '.worktrees[]? | select(.branch == $branch)' "$worktrees_file" 2>/dev/null | head -n 1)"
  [[ -n "$wt_data" ]] || return 1
  current_task="$(echo "$wt_data" | jq -r '.current_task // empty')"
  tasks_json="$(echo "$wt_data" | jq -c '.tasks // []')"
  title=""; pr_ref=""; issue_refs_json='[]'; spec_standard=""; spec_ref=""
  if [[ -n "$current_task" ]]; then
    title="$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .title // empty' "$registry_file" 2>/dev/null | head -n 1)"
    task_status="$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .status // empty' "$registry_file" 2>/dev/null | head -n 1)"
    next_step="$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .next_step // empty' "$registry_file" 2>/dev/null | head -n 1)"
    pr_ref="$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .pr_ref // empty' "$registry_file" 2>/dev/null | head -n 1)"
    spec_standard="$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .spec_standard // empty' "$registry_file" 2>/dev/null | head -n 1)"
    spec_ref="$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .spec_ref // empty' "$registry_file" 2>/dev/null | head -n 1)"
    issue_refs_json="$(jq -c --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | (.issue_refs // [])' "$registry_file" 2>/dev/null | head -n 1)"
    [[ -z "$issue_refs_json" ]] && issue_refs_json='[]'
  fi
  jq -n \
    --arg feature "$(_flow_feature_slug "$branch_name")" \
    --arg branch "$branch_name" \
    --arg state "open" \
    --arg worktree_name "$(echo "$wt_data" | jq -r '.worktree_name // empty')" \
    --arg worktree_path "$(echo "$wt_data" | jq -r '.worktree_path // empty')" \
    --arg current_task "$current_task" \
    --arg title "$title" \
    --arg task_status "$task_status" \
    --arg next_step "$next_step" \
    --arg pr_ref "$pr_ref" \
    --arg spec_standard "$spec_standard" \
    --arg spec_ref "$spec_ref" \
    --argjson tasks "$tasks_json" \
    --argjson issue_refs "$issue_refs_json" '
      {
        feature: $feature,
        branch: $branch,
        state: $state,
        worktree_name: (if $worktree_name == "" then null else $worktree_name end),
        worktree_path: (if $worktree_path == "" then null else $worktree_path end),
        current_task: (if $current_task == "" then null else $current_task end),
        title: (if $title == "" then null else $title end),
        task_status: (if $task_status == "" then null else $task_status end),
        next_step: (if $next_step == "" then null else $next_step end),
        spec_standard: (if $spec_standard == "" then null else $spec_standard end),
        spec_ref: (if $spec_ref == "" then null else $spec_ref end),
        tasks: $tasks,
        pr_ref: (if $pr_ref == "" then null else $pr_ref end),
        issue_refs: $issue_refs
      }
    '
}
