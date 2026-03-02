#!/usr/bin/env zsh
# Tmux session & window management
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
  local parts
  parts=(${(s/-/)name})
  if [[ ${#parts[@]} -lt 2 ]]; then
    echo "Error: Name must have at least 2 parts: <agent>-<task>"
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

# Ensure session exists (kill stale & create)
vibe_tmux_ensure() {
  vibe_require tmux || return 1
  if tmux has-session -t "$VIBE_SESSION" 2>/dev/null; then
    local cur; cur="$(tmux display-message -p '#S' 2>/dev/null)"
    [[ "$cur" == "$VIBE_SESSION" ]] && return 0
    echo "💡 Killing stale session '$VIBE_SESSION'..."
    tmux kill-session -t "$VIBE_SESSION" 2>/dev/null || true
  fi
  tmux new-session -d -s "$VIBE_SESSION" -c "$VIBE_MAIN" -n "main"
}

# Attach to session
vibe_tmux_attach() { vibe_tmux_ensure || return 1; tmux attach -t "$VIBE_SESSION"; }

# Create or focus a window
vibe_tmux_win() {
  local name="$1"; shift; local dir="$1"; shift; local cmd="$*"
  vibe_tmux_ensure || return 1
  if tmux list-windows -t "$VIBE_SESSION" -F "#{window_name}" | command grep -qx "$name"; then
    tmux select-window -t "$VIBE_SESSION:$name"
  elif [[ -n "$cmd" ]]; then
    tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir" "$cmd"
  else
    tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir"
  fi
}

# --- User commands ---

# V3: Create session with auto-naming: tmnew <task-slug> [agent]
tmnew() {
  local task_slug="$1" agent="${2:-claude}"
  [[ -z "$task_slug" ]] && { echo "Usage: tmnew <task-slug> [agent=claude]"; return 1; }

  local session="${agent}-${task_slug}"

  # V3: Validate naming convention
  if ! _validate_tmux_session_name "$session"; then
    return 1
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

  # V3: Write execution result
  source "${0:a:h}/execution-contract.sh" 2>/dev/null || true
  if type write_execution_result >/dev/null 2>&1; then
    local task_id="${task_slug}"  # Use task_slug as task_id
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

# Create or attach to named session (enhanced)
vtup() {
  local session="${1:-$VIBE_SESSION}"
  local old="$VIBE_SESSION"; VIBE_SESSION="$session"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "📎 Attaching: $session"
  else
    echo "🆕 Creating: $session"
    vibe_tmux_ensure
  fi
  tmux attach -t "$session"
  VIBE_SESSION="$old"
}

# Detach
vtdown() {
  [[ -z "$TMUX" ]] && { echo "❌ Not in tmux"; return 1; }
  tmux detach-client
}

# V3: Enhanced session switching with validation
tmswitch() {
  local s="$1"
  [[ -z "$s" ]] && { echo "Usage: tmswitch <session>"; return 1; }

  tmux has-session -t "$s" 2>/dev/null || {
    echo "❌ No session: $s"
    tmlist
    return 1
  }

  [[ -n "$TMUX" ]] && tmux switch-client -t "$s" || tmux attach -t "$s"
  echo "✅ Switched to: $s"
}

# Alias for compatibility
vtswitch() { tmswitch "$@"; }

# V3: Enhanced session listing with task context
tmlist() {
  echo "📋 Tmux Sessions:"
  command -v tmux >/dev/null 2>&1 || { echo "  tmux not installed"; return 1; }

  local out
  out="$(tmux list-sessions -F '#{session_name}|#{?session_attached,*,}|#{session_windows}' 2>/dev/null)"
  [[ -z "$out" ]] && { echo "  No active sessions"; return 0; }

  echo "$out" | while IFS='|' read -r name att win; do
    local agent task
    read -r agent task <<< "$(_parse_session_name "$name")"

    echo "  - $name ($win windows) ${att:+✓ attached}"
    echo "    Agent: $agent"
    echo "    Task: $task"

    # V3: Try to find execution result
    source "${0:a:h}/execution-contract.sh" 2>/dev/null || true
    if type query_by_session >/dev/null 2>&1; then
      local result
      result=$(query_by_session "$name" 2>/dev/null)
      if [[ -n "$result" ]]; then
        local worktree
        worktree=$(echo "$result" | jq -r '.resolved_worktree' 2>/dev/null)
        echo "    Worktree: $worktree"
      fi
    fi
    echo ""
  done
}

# Alias for compatibility
vtls() { tmlist; }

# V3: Kill session with confirmation
tmkill() {
  local s="$1" force="$2"

  if [[ -z "$s" ]]; then
    [[ -z "$TMUX" ]] && { echo "❌ No session specified"; return 1; }
    s="$(tmux display-message -p '#S')"
  fi

  tmux has-session -t "$s" 2>/dev/null || { echo "❌ No session: $s"; return 1; }

  # V3: Confirmation prompt (unless --force)
  if [[ "$force" != "--force" ]]; then
    echo -n "❓ Kill session '$s'? [y/N] "
    local response
    read -r response
    [[ ! "$response" =~ ^[yY]$ ]] && { echo "ℹ️  Cancelled"; return 0; }
  fi

  tmux kill-session -t "$s"
  echo "✅ Killed: $s"
}

# Alias for compatibility
vtkill() { tmkill "$@"; }

# V3: Rename session
tmrename() {
  local old_name="$1" new_name="$2"
  [[ -z "$old_name" || -z "$new_name" ]] && {
    echo "Usage: tmrename <old-session> <new-session>"
    return 1
  }

  tmux has-session -t "$old_name" 2>/dev/null || {
    echo "❌ Session not found: $old_name"
    return 1
  }

  # Validate new name
  if ! _validate_tmux_session_name "$new_name"; then
    return 1
  fi

  tmux rename-session -t "$old_name" "$new_name"
  echo "✅ Renamed: $old_name -> $new_name"

  # V3: Update execution result
  source "${0:a:h}/execution-contract.sh" 2>/dev/null || true
  if type query_by_session >/dev/null 2>&1; then
    local result task_id
    result=$(query_by_session "$old_name" 2>/dev/null)
    if [[ -n "$result" ]]; then
      task_id=$(echo "$result" | jq -r '.task_id' 2>/dev/null)
      if [[ -n "$task_id" ]]; then
        update_execution_result "$task_id" "resolved_session" "$new_name" || true
      fi
    fi
  fi
}
