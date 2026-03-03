#!/usr/bin/env zsh
# Worktree listing and query functions
# Part of V3 Execution Plane

# V3: Enhanced worktree listing with filtering
wtlist() {
  local filter_owner="$1" filter_task="$2"
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }

  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || { vibe_die "Not in git repo"; return 1; }

  echo "Worktrees:"
  echo "-----------"

  local count=0
  while IFS= read -r line; do
    local path branch
    path=$(echo "$line" | awk '{print $1}')
    branch=$(echo "$line" | awk '{print $3}')

    # Skip main worktree
    [[ "$path" == "$main_dir" ]] && continue

    # Extract worktree name
    local wt_name="${path##*/}"

    # V3: Filter by owner if specified
    if [[ -n "$filter_owner" ]]; then
      local owner_prefix="wt-${filter_owner}-"
      [[ "$wt_name" != "$owner_prefix"* ]] && continue
    fi

    # V3: Filter by task if specified
    if [[ -n "$filter_task" ]]; then
      [[ "$wt_name" != *"$filter_task"* ]] && continue
    fi

    # Display worktree info
    local owner task
    if [[ "$wt_name" =~ ^wt-([^-]+)-(.+)$ ]]; then
      owner="${match[1]}"
      task="${match[2]}"
    else
      owner="unknown"
      task="$wt_name"
    fi

    echo "  $wt_name"
    echo "    Owner: $owner"
    echo "    Task: $task"
    echo "    Branch: $branch"
    echo "    Path: $path"
    echo ""

    ((count++))
  done < <($git_cmd -C "$main_dir" worktree list 2>/dev/null)

  echo "-----------"
  echo "Total: $count worktree(s)"

  [[ $count -eq 0 ]] && {
    [[ -n "$filter_owner$filter_task" ]] && \
      echo "No worktrees match filters (owner=$filter_owner, task=$filter_task)" || \
      echo "No worktrees found (use 'wtnew' to create one)"
  }
}

# Maintain backward compatibility
alias wtls='wtlist'
