#!/usr/bin/env zsh
# Tmux session lifecycle management
# Part of V3 Execution Plane

# Kill session with confirmation
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

# Rename session
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
  source "${0:a:h}/naming.sh" 2>/dev/null || true
  if type _validate_tmux_session_name >/dev/null 2>&1; then
    if ! _validate_tmux_session_name "$new_name"; then
      return 1
    fi
  fi

  tmux rename-session -t "$old_name" "$new_name"
  echo "✅ Renamed: $old_name -> $new_name"

  # V3: Update execution result
  source "${0:a:h}/../execution-contract.sh" 2>/dev/null || true
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
