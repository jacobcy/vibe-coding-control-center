_flow_detect_parent_branch() {
  local current_branch="$1" parent_branch=""

  # Strategy 1: Check if current branch has an upstream configured
  parent_branch="$(git rev-parse --abbrev-ref "$current_branch@{upstream}" 2>/dev/null || true)"
  if [[ -n "$parent_branch" && "$parent_branch" != "$current_branch" && "$parent_branch" != "origin/main" && ! "$parent_branch" =~ ^origin/ ]]; then
    echo "$parent_branch"
    return 0
  fi

  # Strategy 2: Find all local branches that contain current branch's HEAD
  # The most recent non-main branch that contains our HEAD is likely the parent
  local candidate_branches
  candidate_branches="$(git branch --contains "$current_branch" 2>/dev/null | grep -v "^\*" | grep -v "main" || true)"

  if [[ -n "$candidate_branches" ]]; then
    # Find the branch with the most commits in common with current branch
    local best_parent="" best_common=0
    while read -r branch; do
      [[ -z "$branch" ]] && continue
      branch="$(echo "$branch" | xargs)"  # Trim whitespace

      # Count common commits
      local common_commits
      common_commits="$(git rev-list --count "$branch..$current_branch" 2>/dev/null || echo "999999")"

      # The parent branch should have fewer commits ahead of current branch
      if [[ "$common_commits" -lt "$best_common" || "$best_common" -eq 0 ]]; then
        best_parent="$branch"
        best_common="$common_commits"
      fi
    done <<< "$candidate_branches"

    if [[ -n "$best_parent" ]]; then
      echo "$best_parent"
      return 0
    fi
  fi

  # Fallback to main if no parent branch detected
  echo "main"
}

_flow_checkout_safe_main_branch() {
  local current_branch="$1" parent_branch="" safe_branch

  # Get current branch if not provided
  if [[ -z "$current_branch" ]]; then
    current_branch="$(git branch --show-current 2>/dev/null || true)"
  fi

  # Detect parent branch for the current branch
  if [[ -n "$current_branch" && "$current_branch" != "main" ]]; then
    parent_branch="$(_flow_detect_parent_branch "$current_branch")"
  else
    parent_branch="main"
  fi

  # Try to check out the parent branch locally first
  if [[ "$parent_branch" != "main" ]]; then
    if git show-ref --verify --quiet "refs/heads/$parent_branch"; then
      if git checkout "$parent_branch" >/dev/null 2>&1; then
        log_info "Checked out parent branch: $parent_branch"
        return 0
      fi
    fi

    # Try to fetch and check out from remote if not local
    local remote_branch="origin/$parent_branch"
    if git show-ref --verify --quiet "refs/remotes/$remote_branch"; then
      git fetch origin "$parent_branch" --quiet 2>/dev/null || true
      if git checkout -B "$parent_branch" "$remote_branch" >/dev/null 2>&1; then
        log_info "Checked out parent branch from remote: $parent_branch"
        return 0
      fi
    fi
  fi

  # Fallback to main branch checkout
  git fetch origin main --quiet 2>/dev/null || true
  if git show-ref --verify --quiet refs/heads/main; then
    if git checkout main >/dev/null 2>&1; then
      return 0
    fi
  fi
  if git show-ref --verify --quiet refs/remotes/origin/main; then
    safe_branch="$(_flow_safe_main_branch_name)"
    if git show-ref --verify --quiet "refs/heads/${safe_branch}"; then
      git checkout "$safe_branch" >/dev/null 2>&1
      return $?
    fi
    git checkout -B "$safe_branch" origin/main >/dev/null 2>&1
    return $?
  fi
  return 1
}

