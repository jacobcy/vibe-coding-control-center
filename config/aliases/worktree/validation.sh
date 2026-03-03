#!/usr/bin/env zsh
# Worktree validation utilities
# Part of V3 Execution Plane

# Validate worktree integrity and git status
wtvalidate() {
  local wt_name="$1"
  local git_cmd; git_cmd="$(vibe_find_cmd git)" || { vibe_die "git not found"; return 1; }

  [[ -z "$wt_name" ]] && wt_name="${PWD##*/}"  # Default to current worktree

  local main_dir; main_dir="$($git_cmd rev-parse --show-toplevel 2>/dev/null)" || { vibe_die "Not in git repo"; return 1; }

  # Resolve worktree path
  local wt_path
  if [[ "$wt_name" == /* ]]; then
    wt_path="$wt_name"
  elif [[ "$wt_name" == "main" ]]; then
    wt_path="$main_dir"
  else
    wt_path="${main_dir:h}/$wt_name"
  fi

  [[ -d "$wt_path" ]] || { echo "❌ Worktree not found: $wt_name"; return 1; }

  echo "🔍 Validating worktree: $wt_name"
  echo "--------------------------------"

  # Check naming convention
  echo "✓ Checking naming convention..."
  if [[ "$wt_name" =~ ^wt- ]]; then
    if source "${0:a:h}/naming.sh" 2>/dev/null && _validate_worktree_name "$wt_name"; then
      echo "  ✅ Naming valid"
    else
      echo "  ⚠️  Naming invalid (expected: wt-<owner>-<task-slug>)"
    fi
  else
    echo "  ℹ️  Main worktree (no naming convention)"
  fi

  # Check git status
  echo "✓ Checking git status..."
  if [[ -f "$wt_path/.git" || -d "$wt_path/.git" ]]; then
    cd "$wt_path" || return 1

    # Check branch
    local branch
    branch=$($git_cmd rev-parse --abbrev-ref HEAD 2>/dev/null)
    echo "  Branch: $branch"

    # Check tracking
    local tracking
    tracking=$($git_cmd rev-parse --abbrev-ref --symbolic-full-name @{u} 2>/dev/null)
    if [[ -n "$tracking" ]]; then
      echo "  Tracking: $tracking"
    else
      echo "  ⚠️  No upstream tracking"
    fi

    # Check working directory cleanliness
    local status
    status=$($git_cmd status --porcelain 2>/dev/null)
    if [[ -z "$status" ]]; then
      echo "  ✅ Working directory clean"
    else
      local changed
      changed=$(echo "$status" | wc -l | tr -d ' ')
      echo "  ⚠️  Uncommitted changes: $changed files"
    fi

    # Check git integrity
    if $git_cmd fsck --full 2>/dev/null 1>&2; then
      echo "  ✅ Git repository integrity OK"
    else
      echo "  ❌ Git repository corruption detected"
      return 1
    fi
  else
    echo "  ❌ Not a git worktree"
    return 1
  fi

  echo "--------------------------------"
  echo "✅ Validation complete"

  return 0
}
