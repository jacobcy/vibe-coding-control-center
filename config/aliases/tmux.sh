#!/usr/bin/env zsh
# ======================================================
# Tmux 命令
# ======================================================

# 确保 session 存在
vibe_tmux_ensure() {
  vibe_load_context
  vibe_require tmux || return 1

  # Check if session already exists
  if tmux has-session -t "$VIBE_SESSION" 2>/dev/null; then
    # Check if we're already attached to this session
    local current_session
    current_session="$(tmux display-message -p '#S' 2>/dev/null)"
    if [[ "$current_session" == "$VIBE_SESSION" ]]; then
      # Already attached, nothing to do
      return 0
    fi
    # Session exists but we're not attached
    echo "⚠️  tmux session '$VIBE_SESSION' already exists!"
    echo ""
    echo "Existing sessions:"
    tmux list-sessions -F "  - #S (attached: #{?session_attached,yes,no})"
    echo ""
    echo "Options:"
    echo "  1. Kill existing session:                 vtkill"
    echo "  2. Attach to existing session:             vt"
    echo "  3. Create session with different name:   VIBE_SESSION=new-name vtup ..."
    echo ""
    echo "💡 Auto-killing existing session..."
    tmux kill-session -t "$VIBE_SESSION" 2>/dev/null || true
  fi

  tmux new-session -d -s "$VIBE_SESSION" -c "$VIBE_MAIN" -n "main"
}

# 附加到 session
vibe_tmux_attach() {
  vibe_tmux_ensure || return 1
  tmux attach -t "$VIBE_SESSION"
}

# 创建或聚焦窗口
vibe_tmux_win() {
  # usage: vibe_tmux_win <name> <dir> [cmd...]
  local name="$1"; shift
  local dir="$1"; shift
  local cmd="$*"

  vibe_tmux_ensure || return 1

  if tmux list-windows -t "$VIBE_SESSION" -F "#{window_name}" | command grep -qx "$name"; then
    tmux select-window -t "$VIBE_SESSION:$name"
  else
    if [[ -n "$cmd" ]]; then
      tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir" "$cmd"
    else
      tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir"
    fi
  fi
}

# ---------- Tmux 用户命令 ----------

# 附加到默认 session (vibe)
vt() {
  vibe_tmux_attach
}

# 创建或附加到指定 session
vtup() {
  local session="${1:-$VIBE_SESSION}"

  # Set session name for this call
  local old_session="$VIBE_SESSION"
  VIBE_SESSION="$session"

  # Check if session exists
  if tmux has-session -t "$session" 2>/dev/null; then
    echo "📎 Attaching to existing session: $session"
    tmux attach -t "$session"
  else
    echo "🆕 Creating new session: $session"
    vibe_tmux_ensure
    tmux attach -t "$session"
  fi

  VIBE_SESSION="$old_session"
}

# 分离当前 session
vtdown() {
  if [[ -z "$TMUX" ]]; then
    echo "❌ Not inside a tmux session"
    return 1
  fi
  tmux detach-client
}

# 切换到指定 session
vtswitch() {
  local session="$1"
  [[ -z "$session" ]] && vibe_die "usage: vtswitch <session>"

  # Check if session exists
  if ! tmux has-session -t "$session" 2>/dev/null; then
    echo "❌ Session '$session' does not exist"
    echo "   Available sessions:"
    vtls
    return 1
  fi

  # If inside tmux, switch directly
  if [[ -n "$TMUX" ]]; then
    tmux switch-client -t "$session"
  else
    # Otherwise, attach
    tmux attach -t "$session"
  fi

  echo "✅ Switched to session: $session"
}

# 列出所有 session
vtls() {
  echo "📋 Tmux Sessions:"
  echo ""

  if ! command -v tmux >/dev/null 2>&1; then
    echo "❌ tmux not installed"
    return 1
  fi

  local session_list
  session_list="$(tmux list-sessions -F '#{session_name} #{?session_attached,*,} #{session_windows}' 2>/dev/null)"

  if [[ -z "$session_list" ]]; then
    echo "   No active sessions"
    return 0
  fi

  echo "$session_list" | while read -r name attached windows; do
    local status_icon="${attached:+✓ (attached)}"
    echo "   - $name ($windows windows) $status_icon"
  done
}

# 删除指定 session（或当前 session）
vtkill() {
  local session="$1"

  # If no argument, use current session
  if [[ -z "$session" ]]; then
    if [[ -z "$TMUX" ]]; then
      echo "❌ Not inside a tmux session and no session name provided"
      echo "   Usage: vtkill <session>"
      return 1
    fi
    session="$(tmux display-message -p '#S')"
    echo "🎯 Killing current session: $session"
  else
    echo "🎯 Killing session: $session"
  fi

  # Check if session exists
  if ! tmux has-session -t "$session" 2>/dev/null; then
    echo "❌ Session '$session' does not exist"
    return 1
  fi

  # Kill session
  tmux kill-session -t "$session"
  echo "✅ Session killed: $session"
}
