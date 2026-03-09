#!/usr/bin/env zsh
# lib/flow_list.sh - All flow listing for flow module

_flow_list_recent_prs() {
  [[ -n "${1:-}" ]] || true
  vibe_has gh || { log_error "gh CLI not found. Cannot query PR information."; return 1; }
  echo "${BOLD}${CYAN}Branches with Recent PRs (last 10):${NC}"
  local pr_list
  pr_list=$(gh pr list --state all --limit 10 --json number,headRefName,title,state,mergedAt 2>/dev/null)
  [[ -z "$pr_list" || "$pr_list" == "[]" ]] && { echo "No PRs found."; return 0; }
  echo "$pr_list" | jq -r '.[] | "\(.number)|\(.headRefName)|\(.title)|\(.state)|\(.mergedAt // "N/A")"' |
    while IFS='|' read -r number branch title state merged_at; do
      printf "${BOLD}PR #${number}${NC} (${state})\n"
      printf "  Branch: %s\n" "$branch"
      printf "  Title: %s\n" "$title"
      [[ "$state" == "MERGED" ]] && printf "  Merged: %s\n" "$merged_at"
    done
}

_flow_list() {
  setopt localoptions typeset_silent 2>/dev/null || true
  local filter_pr=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --pr) filter_pr=1; shift ;;
      -h|--help) _flow_list_usage; return 0 ;;
      *) log_error "Unknown option for flow list: $1"; _flow_list_usage; return 1 ;;
    esac
  done

  if [[ $filter_pr -eq 1 ]]; then
    _flow_list_recent_prs
    return $?
  fi

  local open_json history_file history_json
  open_json="$(_flow_open_dashboard_json)" || { log_error "Not in a worktree"; return 1; }
  history_file="$(_flow_history_ensure_file)" || return 1
  history_json="$(jq -c '.flows // []' "$history_file" 2>/dev/null)"
  [[ -z "$history_json" ]] && history_json='[]'
  echo "${BOLD}${CYAN}All Flows:${NC}"
  [[ "$(echo "$open_json" | jq '.flows | length')" == "0" && "$(echo "$history_json" | jq 'length')" == "0" ]] && { echo "No flow history found."; return 0; }
  echo "$open_json" | jq -c '.flows[]?' | while IFS= read -r flow; do
    echo "${BOLD}$(echo "$flow" | jq -r '.feature')${NC} [open]"
    echo "  Branch: $(echo "$flow" | jq -r '.branch')"
    echo "  Task:   $(echo "$flow" | jq -r '.current_task // "none"')"
    echo "  PR:     $(echo "$flow" | jq -r '.pr_ref // "none"')"
  done
  echo "$history_json" | jq -c '.[]?' | while IFS= read -r flow; do
    echo "${BOLD}$(echo "$flow" | jq -r '.feature')${NC} [closed]"
    echo "  Branch: $(echo "$flow" | jq -r '.branch')"
    echo "  Task:   $(echo "$flow" | jq -r '.current_task // "none"')"
    echo "  PR:     $(echo "$flow" | jq -r '.pr_ref // "none"')"
    echo "  Closed: $(echo "$flow" | jq -r '.closed_at // "unknown"')"
  done
}
