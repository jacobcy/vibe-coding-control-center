#!/usr/bin/env zsh
# Tmux session operations
# Part of V3 Execution Plane

# Create session with auto-naming: tmnew <task-slug> [agent]
tmnew() {
  local task_slug="$1" agent="${2:-claude}"
  [[ -z "$task_slug" ]] && { echo "Usage: tmnew <task-slug> [agent=claude]"; return 1; }

  local session="${agent}-${task_slug}"

  # V3: Validate naming convention (naming.sh already loaded by parent)
  if type _validate_tmux_session_name >/dev/null 2>&1; then
    if ! _validate_tmux_session_name "$session"; then
      return 1
    fi
  fi

  # Check if session exists
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "ℹ️  Session exists: $session"
    echo "   Use 'tmattach $session' to attach"
    return 0
  fi

  # Create session
  local worktree_path="${3:-.}"
  tmux new-session -d -s "$session" -c "$worktree_path" -n "main"
  echo "✅ Created session: $session"

  # V3: Write execution result (contract already loaded by parent)
  if type write_execution_result >/dev/null 2>&1; then
    local task_id="${task_slug}"
    local worktree="wt-${agent}-${task_slug}"
    write_execution_result "$task_id" "$worktree" "$session" || true
  fi
}

# Attach to session with auto-detect
tmattach() {
  local session="$1"

  # V3: Auto-detect session from current worktree
  if [[ -z "$session" ]]; then
    local wt_name="${PWD##*/}"
    if [[ "$wt_name" =~ ^wt-([^-]+)-(.+)$ ]]; then
      local agent="${match[1]}" task="${match[2]}"
      session="${agent}-${task}"
      echo "🔍 Auto-detected session: $session"
    else
      echo "Usage: tmattach [session]"
      echo "   Or run from within a worktree directory"
      return 1
    fi
  fi

  if tmux has-session -t "$session" 2>/dev/null; then
    tmux attach -t "$session"
  else
    echo "❌ Session not found: $session"
    echo "   Use 'tmnew' to create it"
    return 1
  fi
}

# Alias for compatibility
vt() { tmattach "$@"; }
