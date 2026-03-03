#!/usr/bin/env zsh
# Tmux session listing with task context
# Part of V3 Execution Plane

# Enhanced session listing with task context
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
    source "${0:a:h}/../execution-contract.sh" 2>/dev/null || true
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
