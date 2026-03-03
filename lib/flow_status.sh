#!/usr/bin/env zsh
# lib/flow_status.sh - Status and Detection for Flow module

_detect_feature() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-[^-]+-(.+)$ ]] && { echo "${match[1]}"; return 0; }; return 1; }
_detect_agent() { local dir; dir=$(basename "$PWD"); [[ "$dir" =~ ^wt-([^-]+)- ]] && { echo "${match[1]}"; return 0; }; echo "claude"; }

_flow_status() {
  local json_out=0
  [[ "${1:-}" == "--json" ]] && { json_out=1; shift; }

  local feature="${1:-$(_detect_feature || true)}"
  [[ -z "$feature" && "$json_out" -eq 0 ]] && { log_error "Not in a worktree"; return 1; }
  local current_wt; current_wt=$(basename "$PWD")
  local shared_dir; shared_dir="$(_flow_shared_dir)"
  local shared_count; shared_count=$(ls -1 "$shared_dir" 2>/dev/null | wc -l | xargs)

  if (( json_out )); then
    local wts_json="[]"
    local worktrees_file; worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
    while read -r wt_path; do
      local wt_name=$(basename "$wt_path")
      local is_dirty=0
      [[ -n "$(git -C "$wt_path" status --porcelain 2>/dev/null)" ]] && is_dirty=1
      local wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)
      local wt_tasks; wt_tasks=$(jq -c --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .tasks // []' "$worktrees_file" 2>/dev/null || echo "[]")
      wts_json=$(echo "$wts_json" | jq --arg n "$wt_name" --arg p "$wt_path" --arg b "$wt_branch" --argjson d "$is_dirty" --argjson t "$wt_tasks" \
        '. += [{"name":$n, "path":$p, "branch":$b, "is_dirty":$d, "tasks":$t}]')
    done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')
    
    jq -n --arg f "$feature" --arg f_id "$feature" --arg c "$current_wt" --argjson w "$wts_json" --argjson s "$shared_count" \
      '{current_feature: $f, current_feature_id: $f_id, current_worktree: $c, worktrees: $w, shared_context_count: $s}'
    return 0
  fi

  local dirty_count; dirty_count=$(git status --porcelain | wc -l | xargs)
  echo "${BOLD}Task:${NC} $feature | ${BOLD}Branch:${NC} $(git branch --show-current 2>/dev/null)"
  echo "${CYAN}Physical Status:${NC} $dirty_count dirty files found (current)."
  
  # Cross-worktree scan
  echo "${CYAN}Worktree Landscape:${NC}"
  local worktrees_file; worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
  while read -r wt_path; do
    local wt_name=$(basename "$wt_path")
    local d_count=$(git -C "$wt_path" status --porcelain 2>/dev/null | wc -l | xargs)
    local indicator="${GREEN}clean${NC}"
    [[ "$d_count" -gt 0 ]] && indicator="${YELLOW}$d_count dirty files${NC}"
    
    local tasks_info="$(jq -r --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .tasks // [] | join(", ")' "$worktrees_file" 2>/dev/null)"
    local t_label=""
    [[ -n "$tasks_info" ]] && t_label=" [tasks: ${tasks_info}]"

    local marker=""
    [[ "$wt_name" == "$current_wt" ]] && marker=" (current)"
    
    printf "  - %-30s %b%s\n" "${wt_name}${marker}" "$indicator" "$t_label"
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')

  [[ "$shared_count" -gt 0 ]] && echo "${CYAN}Shared Context:${NC} $shared_count files in .git/vibe/shared"
  git status --short
}
