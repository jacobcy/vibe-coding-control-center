#!/usr/bin/env zsh
# lib/flow_status.sh - Status and Detection for Flow module

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }

# Show status for current or specified feature
_flow_status() {
  local json_out=0
  [[ "${1:-}" == "--json" ]] && { json_out=1; shift; }

  local feature="${1:-}"
  local current_wt; current_wt=$(basename "$PWD")

  # Check if we're in a git repository
  local worktrees_file registry_file
  local git_common_dir
  git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || {
    log_error "Not in a worktree"
    return 1
  }
  worktrees_file="$git_common_dir/vibe/worktrees.json"
  registry_file="${git_common_dir}/vibe/registry.json"

  # If no feature specified, use current worktree's task
  if [[ -z "$feature" ]]; then
    feature=$(jq -r --arg wt "$current_wt" '.worktrees[]? | select(.worktree_name == $wt) | .current_task // empty' "$worktrees_file" 2>/dev/null)
    [[ -z "$feature" ]] && { log_error "No task bound to current worktree"; return 1; }
  fi

  if (( json_out )); then
    # JSON output mode (for programmatic use)
    local task_data; task_data=$(jq -e --arg tid "$feature" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null)
    [[ -z "$task_data" ]] && { log_error "Task not found: $feature"; return 1; }
    echo "$task_data" | jq '{task_id, title, status, next_step, assigned_worktree}'
    return 0
  fi

  # Human-readable output
  local task_data; task_data=$(jq -e --arg tid "$feature" '.tasks[]? | select(.task_id == $tid)' "$registry_file" 2>/dev/null)
  if [[ -z "$task_data" ]]; then
    log_error "Task not found: $feature"
    return 1
  fi

  local title task_status next_step worktree
  title=$(echo "$task_data" | jq -r '.title // "N/A"')
  task_status=$(echo "$task_data" | jq -r '.status // "unknown"')
  next_step=$(echo "$task_data" | jq -r '.next_step // "N/A"')
  worktree=$(echo "$task_data" | jq -r '.assigned_worktree // "none"')

  echo "${BOLD}Task:${NC} $feature"
  echo "${BOLD}Title:${NC} $title"
  echo "${BOLD}Status:${NC} $task_status"
  echo "${BOLD}Worktree:${NC} $worktree"
  echo "${BOLD}Branch:${NC} $(git branch --show-current 2>/dev/null)"
  echo "${BOLD}Next Step:${NC} $next_step"
  echo ""

  # Physical status
  local dirty_count; dirty_count=$(git status --porcelain | wc -l | xargs)
  echo "${CYAN}Physical Status:${NC} $dirty_count dirty files"
  git status --short
  echo ""

  # File metrics
  echo "${CYAN}File Metrics:${NC}"
  local total_loc; total_loc=$(find "$VIBE_ROOT/lib" "$VIBE_ROOT/bin" -name '*.sh' -o -name 'vibe' 2>/dev/null | xargs wc -l 2>/dev/null | tail -1 | awk '{print $1}')
  echo "  Total LOC (lib/ + bin/): ${total_loc:-0} / 2400"

  local flow_loc; flow_loc=$(wc -l < "$VIBE_ROOT/lib/flow.sh" 2>/dev/null || echo 0)
  echo "  lib/flow.sh: $flow_loc lines"

  local flow_status_loc; flow_status_loc=$(wc -l < "$VIBE_ROOT/lib/flow_status.sh" 2>/dev/null || echo 0)
  echo "  lib/flow_status.sh: $flow_status_loc lines"
}

# List all worktrees with their status
_flow_list() {
  local current_wt; current_wt=$(basename "$PWD")
  local shared_dir; shared_dir="$(_flow_shared_dir)"
  local shared_count; shared_count=$(ls -1 "$shared_dir" 2>/dev/null | wc -l | xargs)
  local worktrees_file; worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
  local registry_file; registry_file="$(_flow_registry_file)"

  echo "${BOLD}${CYAN}Worktree Landscape:${NC}"
  echo ""

  while read -r wt_path; do
    local wt_name=$(basename "$wt_path")
    local d_count=$(git -C "$wt_path" status --porcelain 2>/dev/null | wc -l | xargs)
    local indicator="${GREEN}clean${NC}"
    [[ "$d_count" -gt 0 ]] && indicator="${YELLOW}$d_count dirty files${NC}"

    local wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
    local current_task=$(jq -r --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .current_task // empty' "$worktrees_file" 2>/dev/null)
    local task_status=""
    local task_next_step=""

    if [[ -n "$current_task" ]]; then
      task_status=$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .status // "unknown"' "$registry_file" 2>/dev/null)
      task_next_step=$(jq -r --arg tid "$current_task" '.tasks[]? | select(.task_id == $tid) | .next_step // "N/A"' "$registry_file" 2>/dev/null | head -c 50)
      [[ ${#task_next_step} -eq 50 ]] && task_next_step="${task_next_step}..."
    fi

    local marker=""
    [[ "$wt_name" == "$current_wt" ]] && marker=" ${BOLD}(current)${NC}"

    printf "${BOLD}%s${NC}%s\n" "$wt_name" "$marker"
    printf "  Branch: %s\n" "${wt_branch:-N/A}"
    printf "  Status: %b\n" "$indicator"
    if [[ -n "$current_task" ]]; then
      printf "  Task: %s (%s)\n" "$current_task" "$task_status"
      printf "  Next: %s\n" "$task_next_step"
    else
      printf "  Task: none\n"
    fi
    echo ""
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')

  [[ "$shared_count" -gt 0 ]] && echo "${CYAN}Shared Context:${NC} $shared_count files in .git/vibe/shared"
}
