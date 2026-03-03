#!/usr/bin/env zsh
# Tmux session management utilities
# Part of V3 Execution Plane

# Create or attach to named session (enhanced)
vtup() {
  local session="${1:-$VIBE_SESSION}"
  local old="$VIBE_SESSION"; VIBE_SESSION="$session"
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "📎 Attaching: $session"
  else
    echo "🆕 Creating: $session"
    # Assuming vibe_tmux_ensure exists from main tmux.sh
    if type vibe_tmux_ensure >/dev/null 2>&1; then
      vibe_tmux_ensure
    fi
  fi
  tmux attach -t "$session"
  VIBE_SESSION="$old"
}

# Detach
vtdown() {
  [[ -z "$TMUX" ]] && { echo "❌ Not in tmux"; return 1; }
  tmux detach-client
}

# Enhanced session switching with validation
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
