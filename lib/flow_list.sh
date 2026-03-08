#!/usr/bin/env zsh
# lib/flow_list.sh - Worktree list rendering for flow module

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
    if ! vibe_has gh; then
      log_error "gh CLI not found. Cannot query PR information."
      return 1
    fi

    echo "${BOLD}${CYAN}Branches with Recent PRs (last 10):${NC}"
    echo ""

    local pr_list
    pr_list=$(gh pr list --state all --limit 10 --json number,headRefName,title,state,mergedAt 2>/dev/null)
    if [[ -z "$pr_list" || "$pr_list" == "[]" ]]; then
      echo "No PRs found."
      return 0
    fi

    echo "$pr_list" | jq -r '.[] | "\(.number)|\(.headRefName)|\(.title)|\(.state)|\(.mergedAt // "N/A")"' |
      while IFS='|' read -r number branch title state merged_at; do
        printf "${BOLD}PR #${number}${NC} (${state})\n"
        printf "  Branch: %s\n" "$branch"
        printf "  Title: %s\n" "$title"
        [[ "$state" == "MERGED" ]] && printf "  Merged: %s\n" "$merged_at"
        echo ""
      done
    return 0
  fi

  local current_wt shared_dir shared_count worktrees_file registry_file
  current_wt=$(basename "$PWD")
  shared_dir="$(_flow_shared_dir)"
  shared_count=$(ls -1 "$shared_dir" 2>/dev/null | wc -l | xargs)
  worktrees_file="$(git rev-parse --git-common-dir)/vibe/worktrees.json"
  registry_file="$(_flow_registry_file)"

  echo "${BOLD}${CYAN}Worktree Landscape:${NC}"
  echo ""

  while read -r wt_path; do
    local wt_name d_count indicator wt_branch cur_t wt_tasks_raw marker
    wt_name=$(basename "$wt_path")
    d_count=$(git -C "$wt_path" status --porcelain 2>/dev/null | wc -l | xargs)
    indicator="${GREEN}clean${NC}"
    [[ "$d_count" -gt 0 ]] && indicator="${YELLOW}$d_count dirty files${NC}"
    wt_branch=$(git -C "$wt_path" branch --show-current 2>/dev/null)

    cur_t=$(jq -r --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .current_task // empty' "$worktrees_file" 2>/dev/null)
    wt_tasks_raw=$(jq -r --arg n "$wt_name" '.worktrees[]? | select(.worktree_name == $n) | .tasks[]?' "$worktrees_file" 2>/dev/null)
    local -a wt_tasks sorted_tasks
    wt_tasks=(${(f)wt_tasks_raw})

    [[ -n "$cur_t" ]] && sorted_tasks+=("$cur_t")
    local t
    for t in "${wt_tasks[@]}"; do
      [[ "$t" == "$cur_t" ]] && continue
      [[ ${#sorted_tasks[@]} -ge 6 ]] && break
      sorted_tasks+=("$t")
    done

    marker=""
    [[ "$wt_name" == "$current_wt" ]] && marker=" ${BOLD}(current)${NC}"
    printf "${BOLD}%s${NC}%s\n" "$wt_name" "$marker"
    printf "  Branch: %s\n" "${wt_branch:-N/A}"
    printf "  Status: %b\n" "$indicator"

    if [[ ${#sorted_tasks[@]} -gt 0 ]]; then
      local tid t_status t_next prefix
      for tid in "${sorted_tasks[@]}"; do
        t_status=$(jq -r --arg tid "$tid" '.tasks[]? | select(.task_id == $tid) | .status // "unknown"' "$registry_file" 2>/dev/null)
        t_next=$(jq -r --arg tid "$tid" '.tasks[]? | select(.task_id == $tid) | .next_step // "N/A"' "$registry_file" 2>/dev/null | head -c 50)
        [[ ${#t_next} -eq 50 ]] && t_next="${t_next}..."
        prefix="  [Sub ]"
        [[ "$tid" == "$cur_t" ]] && prefix="  [Main]"
        printf "%s %s (%s)\n" "$prefix" "$tid" "$t_status"
        [[ "$tid" == "$cur_t" ]] && printf "         Next: %s\n" "$t_next"
      done
    else
      printf "  Task: none\n"
    fi
    echo ""
  done < <(git worktree list --porcelain | awk '/^worktree / {print $2}')

  [[ "$shared_count" -gt 0 ]] && echo "${CYAN}Shared Context:${NC} $shared_count files in .git/vibe/shared" || true
}
