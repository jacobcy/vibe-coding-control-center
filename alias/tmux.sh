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

# ── Shared session finding logic ───────────────────────────────────────────
# Returns session name(s) matching the given pattern
# Usage: _vt_find "name" → prints session name(s)
_vt_find() {
  local target="$1"
  local -a all_sessions=()
  while IFS= read -r s; do
    [[ -n "$s" ]] && all_sessions+=("$s")
  done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null)

  [[ ${#all_sessions[@]} -eq 0 ]] && return 1

  # ① Exact match
  for s in "${all_sessions[@]}"; do
    [[ "$s" == "$target" ]] && { echo "$s"; return 0; }
  done

  # ② Suffix match: ends with "-<target>" or "_<target>"
  local -a candidates=()
  for s in "${all_sessions[@]}"; do
    [[ "$s" == *"-${target}" || "$s" == *"_${target}" ]] && candidates+=("$s")
  done

  # ③ Substring match: contains "<target>"
  if [[ ${#candidates[@]} -eq 0 ]]; then
    for s in "${all_sessions[@]}"; do
      [[ "$s" == *"${target}"* ]] && candidates+=("$s")
    done
  fi

  printf '%s\n' "${candidates[@]}"
}

# @desc List or attach to existing Tmux sessions
#   vt          → list all sessions
#   vt <name>   → attach to matched session (only existing)
# @featured
vt() {
  vibe_require tmux || return 1
  local target="${1:-}"

  if [[ -z "$target" ]]; then
    # List all sessions
    local -a sessions=()
    while IFS= read -r s; do
      [[ -n "$s" ]] && sessions+=("$s")
    done < <(tmux list-sessions -F '#{session_name}' 2>/dev/null)

    if [[ ${#sessions[@]} -eq 0 ]]; then
      echo "ℹ️  No active sessions. Use ${CYAN}vtup${NC} to create one."
      return 0
    fi

    echo "${BOLD}Active Sessions:${NC}"
    for s in "${sessions[@]}"; do
      echo "  • $s"
    done
    return 0
  fi

  # Smart match existing session
  local result=$(_vt_find "$target")
  [[ -z "$result" ]] && { echo "❌ Session not found: $target"; return 1; }

  local -a matches=(${(f)result})
  case ${#matches[@]} in
    1) [[ -n "$TMUX" ]] && tmux switch-client -t "${matches[1]}" || tmux attach -t "${matches[1]}" ;;
    *)
      echo "🔍 Multiple sessions match '${target}':"
      local i=1 s
      for s in "${matches[@]}"; do
        echo "  [$i] $s"
        (( i++ ))
      done
      echo -n "Enter choice [1-${#matches[@]}]: "
      local choice; read -r choice
      if [[ "$choice" =~ ^[0-9]+$ ]] && (( choice >= 1 && choice <= ${#matches[@]} )); then
        [[ -n "$TMUX" ]] && tmux switch-client -t "${matches[$choice]}" || tmux attach -t "${matches[$choice]}"
      else
        echo "❌ Invalid choice"
      fi
      ;;
  esac
}

# @desc Create or attach to a session in current/specified directory
#   vtup            → use current dir name as session
#   vtup <rel-dir>  → use rel-dir as session (create directly)
#   vtup /abs/path  → use dir basename as session
# @featured
vtup() {
  vibe_require tmux git || return 1
  local target="${1:-}"

  local session_name dir_path

  if [[ -z "$target" ]]; then
    # No arg: use current directory name
    dir_path="$(pwd)"
    session_name="${dir_path##*/}"
  elif [[ "$target" == /* ]]; then
    # Absolute path: use basename
    dir_path="$target"
    session_name="${target##*/}"
  else
    # Relative path: use as-is
    dir_path="$(pwd)/$target"
    session_name="$target"
  fi

  # Check if session exists
  if tmux has-session -t "$session_name" 2>/dev/null; then
    echo "📎 Attaching to: $session_name"
    [[ -n "$TMUX" ]] && tmux switch-client -t "$session_name" || tmux attach -t "$session_name"
  else
    # Create new session
    echo "🆕 Creating session: $session_name"
    tmux new-session -d -s "$session_name" -c "$dir_path" -n "main"
    [[ -n "$TMUX" ]] && tmux switch-client -t "$session_name" || tmux attach -t "$session_name"
  fi
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
