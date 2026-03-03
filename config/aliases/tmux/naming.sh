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

  # Check minimum parts
  local IFS='-'
  local -a parts
  parts=($name)
  if [[ ${#parts[@]} -lt 2 ]]; then
    echo "Error: Name must have at least 2 parts: <agent>-<task>" >&2
    return 1
  fi

  return 0
}

# Extract agent and task from session name
_parse_session_name() {
  local name="$1"
  if [[ "$name" =~ ^([^-]+)-(.+)$ ]]; then
    echo "${match[1]} ${match[2]}"
  else
    echo "unknown $name"
  fi
}
