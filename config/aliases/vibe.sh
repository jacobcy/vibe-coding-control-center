#!/usr/bin/env zsh
# ======================================================
# Vibe 命令
# 命名规范: v* (Vibe)
# ======================================================

# Lazygit
alias lg='lazygit'

# Vibe chat
alias vc='vibe chat'

# Vibe sign（合并 vsig, vmsign）
alias vsign='vibe sign'

# 跳转到 main 目录
alias vmain="cd \"$VIBE_MAIN\""

# 统一 vibe 命令（动态路径解析）
# 优先级: local ./bin/vibe -> git root bin/vibe -> VIBE_ROOT bin/vibe
vibe() {
  local local_vibe="./bin/vibe"
  local git_root_vibe=""

  # Check for explicit global
  if [[ "$1" == "-g" || "$1" == "--global" ]]; then
    shift
    local global_vibe="$HOME/.vibe/bin/vibe"
    if [[ -x "$global_vibe" ]]; then
      "$global_vibe" "$@"
      return
    elif [[ -x "$VIBE_ROOT/bin/vibe" ]]; then
      "$VIBE_ROOT/bin/vibe" "$@"
      return
    else
      echo "❌ Global vibe not found at $global_vibe" >&2
      return 1
    fi
  fi

  # Check for bin/vibe in current directory
  if [[ -x "$local_vibe" ]]; then
    "$local_vibe" "$@"
    return
  fi

  # Check for bin/vibe in git root
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local root
    root="$(git rev-parse --show-toplevel)"
    if [[ -x "$root/bin/vibe" ]]; then
      git_root_vibe="$root/bin/vibe"
      "$git_root_vibe" "$@"
      return
    fi
  fi

  # Fallback to VIBE_ROOT
  if [[ -x "$VIBE_ROOT/bin/vibe" ]]; then
    "$VIBE_ROOT/bin/vibe" "$@"
  else
    echo "❌ Could not find 'vibe' executable."
    echo "   Checked: ./bin/vibe"
    [[ -n "$git_root_vibe" ]] && echo "   Checked: $git_root_vibe"
    echo "   Checked: $VIBE_ROOT/bin/vibe"
    return 1
  fi
}
