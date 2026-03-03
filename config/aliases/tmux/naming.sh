#!/usr/bin/env zsh
# Tmux session naming utilities
# Part of V3 Execution Plane

# Naming convention: <agent>-<task-slug>
# Examples: claude-add-user-auth, opencode-fix-bug-123

# Validate tmux session naming convention
_validate_tmux_session_name() {
  local name="$1"
  [[ -z "$name" ]] && { echo "Error: Empty name"; return 1; }

  # Check format: <agent>-<task-slug>
  if [[ ! "$name" =~ ^[a-z0-9-]+$ ]]; then
    echo "Error: Invalid naming format"
    echo "Expected: <agent>-<task-slug>"
    echo "Example: claude-add-user-auth"
    echo "Got: $name"
    return 1
  fi

  # Check minimum parts (must have at least agent-task)
  # Count hyphens - need at least 1 for valid format
  local hyphen_count
  hyphen_count=$(echo "$name" | tr -cd '-' | wc -c)
  if [[ $hyphen_count -lt 1 ]]; then
    echo "Error: Name must have at least 2 parts: <agent>-<task>" >&2
    return 1
  fi

  return 0
}

# Extract agent and task from session name
_parse_session_name() {
  local name="$1"
  local agent task

  # Split on first hyphen using parameter expansion (bash-compatible)
  agent="${name%%-*}"
  task="${name#*-}"

  if [[ -n "$agent" && -n "$task" && "$agent" != "$task" ]]; then
    echo "$agent $task"
  else
    echo "unknown $name"
  fi
}
