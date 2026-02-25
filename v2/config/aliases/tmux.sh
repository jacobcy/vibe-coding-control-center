#!/usr/bin/env zsh
# Tmux session & window management

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

# Attach to default session
vt() { vibe_tmux_attach; }

# Create or attach to named session
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

# Switch session
vtswitch() {
  local s="$1"; [[ -z "$s" ]] && vibe_die "usage: vtswitch <session>"
  tmux has-session -t "$s" 2>/dev/null || { echo "❌ No session: $s"; vtls; return 1; }
  [[ -n "$TMUX" ]] && tmux switch-client -t "$s" || tmux attach -t "$s"
}

# List sessions
vtls() {
  echo "📋 Tmux Sessions:"
  command -v tmux >/dev/null 2>&1 || { echo "  tmux not installed"; return 1; }
  local out; out="$(tmux list-sessions -F '#{session_name} #{?session_attached,*,} #{session_windows}' 2>/dev/null)"
  [[ -z "$out" ]] && { echo "  No active sessions"; return 0; }
  echo "$out" | while read -r name att win; do
    echo "  - $name ($win windows) ${att:+✓ attached}"
  done
}

# Kill session
vtkill() {
  local s="$1"
  if [[ -z "$s" ]]; then
    [[ -z "$TMUX" ]] && { echo "❌ No session specified"; return 1; }
    s="$(tmux display-message -p '#S')"
  fi
  tmux has-session -t "$s" 2>/dev/null || { echo "❌ No session: $s"; return 1; }
  tmux kill-session -t "$s"
  echo "✅ Killed: $s"
}
