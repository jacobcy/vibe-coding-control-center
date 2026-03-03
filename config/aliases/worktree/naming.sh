#!/usr/bin/env zsh
# Worktree naming utilities and validation
# Part of V3 Execution Plane

# Naming convention: wt-<owner>-<task-slug>
# Examples: wt-claude-add-user-auth, wt-opencode-fix-bug-123

# Validate worktree naming convention
_validate_worktree_name() {
  local name="$1"
  [[ -z "$name" ]] && { echo "Error: Empty name"; return 1; }

  # Check format: wt-<owner>-<task-slug>
  if [[ ! "$name" =~ ^wt-[a-z0-9-]+$ ]]; then
    echo "Error: Invalid naming format"
    echo "Expected: wt-<owner>-<task-slug>"
    echo "Example: wt-claude-add-user-auth"
    echo "Got: $name"
    return 1
  fi

  # Check minimum parts (must have at least wt-<owner>-<task>)
  # Count hyphens - need at least 2 for valid format
  local hyphen_count
  hyphen_count=$(echo "$name" | tr -cd '-' | wc -c)
  if [[ $hyphen_count -lt 2 ]]; then
    echo "Error: Name must have at least 3 parts: wt-<owner>-<task-slug>" >&2
    return 1
  fi

  return 0
}

# Generate auto-suffix for naming conflicts (4 chars)
_generate_conflict_suffix() {
  # Use nanoseconds + RANDOM for better uniqueness
  local ns random
  ns=$(date +%N 2>/dev/null || echo $RANDOM$$)
  random=$RANDOM
  printf "%04x" $(( (10#$ns ^ random) % 65536 ))
}
