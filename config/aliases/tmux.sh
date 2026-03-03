#!/usr/bin/env zsh
# Tmux session & window management
# Part of V3 Execution Plane
#
# This module has been refactored into submodules:
# - tmux/naming.sh: Session naming validation
# - tmux/operations.sh: Session creation and attachment
# - tmux/management.sh: Session switching and management
# - tmux/listing.sh: Session listing with task context
# - tmux/lifecycle.sh: Session termination and renaming

# Source all tmux submodules
# Use VIBE_ROOT if available (for testing), otherwise resolve from script location
if [[ -n "$VIBE_ROOT" ]]; then
  TMUX_MODULE_DIR="$VIBE_ROOT/config/aliases/tmux"
else
  TMUX_MODULE_DIR="${0:a:h}/tmux"
fi

source "$TMUX_MODULE_DIR/naming.sh" 2>/dev/null || true
source "$TMUX_MODULE_DIR/operations.sh" 2>/dev/null || true
source "$TMUX_MODULE_DIR/management.sh" 2>/dev/null || true
source "$TMUX_MODULE_DIR/listing.sh" 2>/dev/null || true
source "$TMUX_MODULE_DIR/lifecycle.sh" 2>/dev/null || true

# Legacy functions (preserved for compatibility)
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

vibe_tmux_attach() { vibe_tmux_ensure || return 1; tmux attach -t "$VIBE_SESSION"; }

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
