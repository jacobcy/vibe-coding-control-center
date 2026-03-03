#!/usr/bin/env zsh
# Core worktree operations
# Part of V3 Execution Plane

# Create new worktree: wtnew <branch> [agent] [base]
# V3: Auto-naming with conflict detection
wtnew() {
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }
  local branch="$1" agent="${2:-claude}" base="${3:-}"
  [[ -z "$branch" ]] && vibe_die "usage: wtnew <branch> [agent=claude|opencode|codex] [base]"

  local repo_root
  repo_root="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || vibe_die "Not in a git repo"

  # Determine base branch if not specified
  if [[ -z "$base" ]]; then
    # Try main first, then master, then current branch
    if $git_cmd -C "$repo_root" show-ref --verify --quiet refs/heads/main; then
      base="main"
    elif $git_cmd -C "$repo_root" show-ref --verify --quiet refs/heads/master; then
      base="master"
    else
      base="$($git_cmd -C "$repo_root" branch --show-current 2>/dev/null)"
    fi
  fi

  # V3: Generate standardized worktree name
  local dir="wt-${agent}-${branch}"
  local path="${repo_root:h}/$dir"

  # V3: Validate naming convention (naming.sh already loaded by parent)
  if type _validate_worktree_name >/dev/null 2>&1; then
    if ! _validate_worktree_name "$dir"; then
      return 1
    fi
  fi

  # V3: Handle naming conflicts with auto-suffix
  local suffix=""
  if [[ -e "$path" ]]; then
    if type _generate_conflict_suffix >/dev/null 2>&1; then
      suffix=$(_generate_conflict_suffix)
      dir="${dir}-${suffix}"
      path="${repo_root:h}/$dir"
      echo "⚠️  Naming conflict detected, auto-generated suffix: $suffix"
    fi
  fi

  $git_cmd -C "$repo_root" fetch -p >/dev/null 2>&1 || true
  $git_cmd -C "$repo_root" show-ref --verify --quiet "refs/heads/$branch" || \
    $git_cmd -C "$repo_root" branch "$branch" "$base" 2>/dev/null || true

  if [[ -e "$path" ]]; then
    echo "ℹ️  Worktree exists: $dir"
  else
    $git_cmd -C "$repo_root" worktree add "$path" "$branch" || return 1
    if [[ -n "$suffix" ]]; then
      echo "✅ Created worktree: $dir -> $branch (base: $base, suffix: $suffix)"
    else
      echo "✅ Created worktree: $dir -> $branch (base: $base)"
    fi
  fi

  # Set agent identity (capitalize first letter for name)
  local aname="Agent-${agent^}" aemail="agent-${agent}@vibecoding.ai"
  $git_cmd -C "$path" config user.name "$aname"
  $git_cmd -C "$path" config user.email "$aemail"
  echo "👤 Identity: $aname <$aemail>"
  cd "$path" || return

  # V3: Write execution result
  source "${0:a:h}/../execution-contract.sh" 2>/dev/null || true
  if type write_execution_result >/dev/null 2>&1; then
    local task_id="${branch}"  # Use branch as task_id placeholder
    write_execution_result "$task_id" "$dir" "${agent}-${branch}" || true
  fi
}
