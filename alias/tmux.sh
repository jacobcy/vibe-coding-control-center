#!/usr/bin/env zsh
# Tmux session & window management

# @desc Ensure the Vibe Tmux session exists
vibe_tmux_ensure() {
  vibe_require tmux || return 1
  # If session already exists, we're good
  tmux has-session -t "$VIBE_SESSION" 2>/dev/null && return 0
  
  # Otherwise, create a new detached session
  tmux new-session -d -s "$VIBE_SESSION" -c "$VIBE_MAIN" -n "main"
}

# @desc Attach to the active Vibe Tmux session
vibe_tmux_attach() { vibe_tmux_ensure || return 1; tmux attach -t "$VIBE_SESSION"; }

# @desc Create or focus a named Tmux window in a directory
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

# @desc Create a split-pane window (Dash)
vibe_tmux_dash() {
  local name="$1" dir="$2" left_cmd="$3" right_cmd="$4"
  vibe_tmux_ensure || return 1
  if tmux list-windows -t "$VIBE_SESSION" -F "#{window_name}" | command grep -qx "$name"; then
    echo "💡 Window '$name' already exists. Focusing..."
    tmux select-window -t "$VIBE_SESSION:$name"
    return 0
  fi
  # Create window with left command
  tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir" "$left_cmd"
  # Split right and run agent
  tmux split-window -h -t "$VIBE_SESSION:$name" -c "$dir" "$right_cmd"
  # Reset focus to left pane
  tmux select-pane -t "$VIBE_SESSION:$name.0"
}

# --- User commands ---

# @desc Attach to the default Vibe Tmux session
# @featured
vt() { vibe_tmux_attach; }

# @desc Create or attach to a named Tmux session
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

# @desc Detach from the current Tmux session
# @featured
vtdown() {
  [[ -z "$TMUX" ]] && { echo "❌ Not in tmux"; return 1; }
  tmux detach-client
  echo "👋 Detached. Session continues in background."
  echo "💡 Next: Run ${CYAN}vt${NC} to return anytime."
}

# @desc Close specific workspace windows or current window
# @featured
vdown() {
  [[ -z "$TMUX" ]] && { echo "❌ Must be run inside tmux"; return 1; }
  local target="${1:-current}"
  local s; s="$(tmux display-message -p '#S')"
  
  if [[ "$target" == "all" ]]; then
    local -a windows
    windows=("${(@f)$(tmux list-windows -t "$s" -F "#{window_name}" | grep "^wt-")}")
    [[ ${#windows[@]} -eq 0 ]] && { echo "ℹ️ No wt-* windows found"; return 0; }
    confirm_action "Kill all ${#windows[@]} worktree windows?" || return 0
    for w in "${windows[@]}"; do tmux kill-window -t "$s:$w"; done
    echo "✅ Cleaned up all wt-* windows."
  elif [[ "$target" == "current" ]]; then
    local w; w="$(tmux display-message -p '#W')"
    confirm_action "Kill current window '$w'?" || return 0
    tmux kill-window -t "$s:$w"
  else
    # Target specific prefix
    local -a windows
    windows=("${(@f)$(tmux list-windows -t "$s" -F "#{window_name}" | grep "^${target}")}")
    [[ ${#windows[@]} -eq 0 ]] && { echo "❌ No windows found matching '$target'"; return 1; }
    for w in "${windows[@]}"; do tmux kill-window -t "$s:$w"; done
    echo "✅ Cleaned up windows for: $target"
  fi
}

# @desc Switch to a different Tmux session
vtswitch() {
  local s="$1"; [[ -z "$s" ]] && vibe_die "usage: vtswitch <session>"
  tmux has-session -t "$s" 2>/dev/null || { echo "❌ No session: $s"; vtls; return 1; }
  [[ -n "$TMUX" ]] && tmux switch-client -t "$s" || tmux attach -t "$s"
}

# @desc List all active Tmux sessions
# @featured
vtls() {
  echo "📋 Tmux Sessions:"
  command -v tmux >/dev/null 2>&1 || { echo "  tmux not installed"; return 1; }
  local out; out="$(tmux list-sessions -F '#{session_name} #{?session_attached,*,} #{session_windows}' 2>/dev/null)"
  [[ -z "$out" ]] && { echo "  No active sessions"; return 0; }
  echo "$out" | while read -r name att win; do
    echo "  - $name ($win windows) ${att:+✓ attached}"
  done
  echo ""
  echo "💡 Next: Run ${CYAN}vt${NC} to attach to default, or ${CYAN}vtup <name>${NC} for specific."
}

# @desc Kill a specific Tmux session
vtkill() {
  local s="$1"
  if [[ -z "$s" ]]; then
    if [[ -n "$TMUX" ]]; then
      s="$(tmux display-message -p '#S')"
      confirm_action "Kill current session '$s'?" || return 0
    else
      s="$VIBE_SESSION"
    fi
  fi
  tmux has-session -t "$s" 2>/dev/null || { echo "❌ No session: $s"; return 1; }
  tmux kill-session -t "$s"
  echo "✅ Killed: $s"
}
