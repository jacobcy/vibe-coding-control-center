#!/usr/bin/env zsh

_flow_show_resolve_target() {
  local target="${1:-}" current_branch
  [[ -n "$target" ]] && { echo "$target"; return 0; }
  current_branch="$(git branch --show-current 2>/dev/null)"
  [[ -n "$current_branch" ]] && { echo "$current_branch"; return 0; }
  _detect_feature 2>/dev/null && return 0
  return 1
}

_flow_show_open_record() {
  local target="$1" candidate_branch open_status
  candidate_branch="$(_flow_switch_target_branch "$target")"
  _flow_branch_dashboard_entry "$candidate_branch" && return 0
  open_status=$?
  [[ "$open_status" -ne 1 ]] && return "$open_status"
  if [[ "$candidate_branch" != "$target" ]]; then
    _flow_branch_dashboard_entry "$target" && return 0
    open_status=$?
    [[ "$open_status" -ne 1 ]] && return "$open_status"
  fi
  return 1
}

_flow_show() {
  setopt localoptions typeset_silent 2>/dev/null || true
  local json_out=0 target="" arg record current_task=""
  for arg in "$@"; do [[ "$arg" == "-h" || "$arg" == "--help" ]] && { _flow_show_usage; return 0; }; done
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json) json_out=1; shift ;;
      -*) log_error "Unknown option for flow show: $1"; _flow_show_usage; return 1 ;;
      *) [[ -z "$target" ]] && target="$1"; shift ;;
    esac
  done
  local current_branch
  current_branch="$(git branch --show-current 2>/dev/null)"
  if [[ "$current_branch" == "main" || "$current_branch" == "master" ]]; then
    log_warn "Protection: Flow operations are restricted on protected branch '$current_branch'."
    echo "💡 Hint: Use 'vibe flow new <feature>' to start a new task on a feature branch."
    return 1
  fi

  target="$(_flow_show_resolve_target "$target")" || { log_error "Unable to resolve current flow."; return 1; }
  record="$(_flow_show_open_record "$target")"
  local open_status=$?
  if [[ "$open_status" -ne 0 && "$open_status" -ne 1 ]]; then
    return "$open_status"
  fi
  [[ -z "$record" && "$open_status" -eq 1 ]] && record="$(_flow_history_show "$target")"
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
        | .spec_standard = (.spec_standard // ($task.spec_standard // null))
        | .spec_ref = (.spec_ref // ($task.spec_ref // null))
      ')"
    fi
  fi
  (( json_out )) && { echo "$record"; return 0; }
  echo "${BOLD}Flow:${NC} $(echo "$record" | jq -r '.feature')"
  echo "${BOLD}State:${NC} $(echo "$record" | jq -r '.state')"
  echo "${BOLD}Branch:${NC} $(echo "$record" | jq -r '.branch')"
  echo "${BOLD}Worktree:${NC} $(echo "$record" | jq -r '.worktree_name // "none"')"
  echo "${BOLD}Issues:${NC} $(echo "$record" | jq -r '(.issue_refs // []) | if length == 0 then "none" else join(", ") end')"
  echo "${BOLD}Spec Ref:${NC} $(echo "$record" | jq -r '.spec_ref // "N/A"')"
  echo "${BOLD}PR:${NC} $(echo "$record" | jq -r '.pr_ref // "none"')"
  echo "${BOLD}Task:${NC} $(echo "$record" | jq -r '.current_task // "none"')"
  echo "${BOLD}Title:${NC} $(echo "$record" | jq -r '.title // "N/A"')"
  echo "${BOLD}Task Status:${NC} $(echo "$record" | jq -r '.task_status // "N/A"')"
  echo "${BOLD}Next Step:${NC} $(echo "$record" | jq -r '.next_step // "N/A"')"
  [[ "$(echo "$record" | jq -r '.closed_at // empty')" != "" ]] && echo "${BOLD}Closed At:${NC} $(echo "$record" | jq -r '.closed_at')"
  return 0
}
