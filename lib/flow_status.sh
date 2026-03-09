#!/usr/bin/env zsh
# lib/flow_status.sh - Open flow dashboard for flow module

[[ -f "$VIBE_LIB/flow_list.sh" ]] && source "$VIBE_LIB/flow_list.sh"

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }

_flow_open_dashboard_json() {
  local git_common_dir worktrees_file branch lines=""
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || return 1
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  [[ -f "$worktrees_file" ]] || return 1
  while IFS= read -r branch; do
    [[ -n "$branch" ]] || continue
    [[ "$branch" == "main" || "$branch" == "master" ]] && continue
    local record
    record="$(_flow_branch_dashboard_entry "$branch" 2>/dev/null || true)"
    [[ -n "$record" ]] && lines+="$record"$'\n'
  done < <(jq -r '.worktrees[]? | select((.branch // "") != "" and (.status // "active") != "missing") | .branch' "$worktrees_file" 2>/dev/null | awk '!seen[$0]++')
  [[ -z "$lines" ]] && { printf '%s\n' '{"flows":[]}'; return 0; }
  printf '%s' "$lines" | jq -s '{flows: .}'
}

_flow_status() {
  setopt localoptions typeset_silent 2>/dev/null || true
  local json_out=0
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --json) json_out=1; shift ;;
      -h|--help) _flow_status_usage; return 0 ;;
      *) log_error "Unknown option for flow status: $1"; _flow_status_usage; return 1 ;;
    esac
  done
  local dashboard_json
  dashboard_json="$(_flow_open_dashboard_json)" || { log_error "Not in a worktree"; return 1; }
  (( json_out )) && { echo "$dashboard_json"; return 0; }
  local count
  count="$(echo "$dashboard_json" | jq -r '.flows | length')"
  echo "${BOLD}${CYAN}Open Flow Dashboard:${NC}"
  [[ "$count" == "0" ]] && { echo "No open flows."; return 0; }
  echo "$dashboard_json" | jq -c '.flows[]' | while IFS= read -r flow; do
    echo "${BOLD}$(echo "$flow" | jq -r '.feature')${NC}"
    echo "  Branch: $(echo "$flow" | jq -r '.branch')"
    echo "  Task:   $(echo "$flow" | jq -r '.current_task // "none"')"
    echo "  Status: $(echo "$flow" | jq -r '.task_status // "unknown"')"
    echo "  PR:     $(echo "$flow" | jq -r '.pr_ref // "none"')"
    echo "  Next:   $(echo "$flow" | jq -r '.next_step // "N/A"')"
  done
}
