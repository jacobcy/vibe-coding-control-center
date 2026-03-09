#!/usr/bin/env zsh

_flow_show_resolve_target() {
  local target="${1:-}" current_branch
  if [[ -n "$target" ]]; then
    echo "$target"
    return 0
  fi
  current_branch="$(git branch --show-current 2>/dev/null)"
  [[ -n "$current_branch" ]] && { echo "$current_branch"; return 0; }
  _detect_feature 2>/dev/null && return 0
  return 1
}

_flow_show_open_record() {
  local target="$1" git_common_dir worktrees_file branch_name
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 1
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  branch_name="${target#origin/}"

  jq -r --arg target "$target" --arg branch "$branch_name" --arg feature "$(_flow_feature_slug "$target")" '
    .worktrees[]?
    | select(
        (.branch // "") == $branch
        or (.branch // "") == $target
        or ((.branch // "") | sub("^task/"; "")) == $feature
    )
    | .branch // empty
  ' "$worktrees_file" 2>/dev/null | head -n 1 | while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue
    _flow_branch_dashboard_entry "$branch"
    return 0
  done
}

_flow_show() {
  setopt localoptions typeset_silent 2>/dev/null || true

  local json_out=0 target="" arg record current_task=""
  for arg in "$@"; do
    [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_show_usage; return 0; }
  done

  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json) json_out=1; shift ;;
      -*) log_error "Unknown option for flow show: $1"; _flow_show_usage; return 1 ;;
      *) [[ -z "$target" ]] && target="$1"; shift ;;
    esac
  done

  target="$(_flow_show_resolve_target "$target")" || { log_error "Unable to resolve current flow."; return 1; }
  record="$(_flow_show_open_record "$target")"
  [[ -z "$record" ]] && record="$(_flow_history_show "$target")"
  [[ -n "$record" ]] || { log_error "Flow not found: $target"; return 1; }

  current_task="$(echo "$record" | jq -r '.current_task // empty')"
  if [[ -n "$current_task" ]]; then
    local registry_file task_json issue_refs_json
    registry_file="$(_flow_registry_file)"
    task_json="$(jq -c --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null | head -n 1)"
    if [[ -n "$task_json" ]]; then
      issue_refs_json="$(echo "$task_json" | jq -c '.issue_refs // []')"
      record="$(echo "$record" | jq --argjson task "$task_json" --argjson issue_refs "${issue_refs_json:-[]}" '
        .title = (.title // ($task.title // null))
        | .task_status = ($task.status // null)
        | .next_step = ($task.next_step // null)
        | .pr_ref = (.pr_ref // ($task.pr_ref // null))
        | .issue_refs = (if (.issue_refs // []) | length > 0 then .issue_refs else $issue_refs end)
      ')"
    fi
  fi

  if (( json_out )); then
    echo "$record"
    return 0
  fi

  echo "${BOLD}Flow:${NC} $(echo "$record" | jq -r '.feature')"
  echo "${BOLD}State:${NC} $(echo "$record" | jq -r '.state')"
  echo "${BOLD}Branch:${NC} $(echo "$record" | jq -r '.branch')"
  echo "${BOLD}Worktree:${NC} $(echo "$record" | jq -r '.worktree_name // "none"')"
  echo "${BOLD}Task:${NC} $(echo "$record" | jq -r '.current_task // "none"')"
  echo "${BOLD}Title:${NC} $(echo "$record" | jq -r '.title // "N/A"')"
  echo "${BOLD}Task Status:${NC} $(echo "$record" | jq -r '.task_status // "N/A"')"
  echo "${BOLD}PR:${NC} $(echo "$record" | jq -r '.pr_ref // "none"')"
  echo "${BOLD}Issues:${NC} $(echo "$record" | jq -r '(.issue_refs // []) | if length == 0 then "none" else join(", ") end')"
  echo "${BOLD}Next Step:${NC} $(echo "$record" | jq -r '.next_step // "N/A"')"
  [[ "$(echo "$record" | jq -r '.closed_at // empty')" != "" ]] && echo "${BOLD}Closed At:${NC} $(echo "$record" | jq -r '.closed_at')"
}
