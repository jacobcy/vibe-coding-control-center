#!/usr/bin/env zsh
# Vibe aliases

# @desc Open Lazygit for TUI git operations
# @featured
alias lg='lazygit'
# @desc Open Vibe Chat in the current context
# @featured
alias vc='vibe chat'
# @desc Digitally sign a task or document
alias vsign='vibe sign'
# @desc Navigate to Vibe main repository root
alias vmain="cd \"$VIBE_MAIN\""

# @desc Dynamic Vibe executor switcher (local/git-root/global)
# @featured
vibe() {
  # Explicit global flag
  if [[ "$1" == "-g" || "$1" == "--global" ]]; then
    shift
    local gv="${HOME}/.vibe/bin/vibe"
    [[ -x "$gv" ]] && { "$gv" "$@"; return; }
    [[ -x "$VIBE_ROOT/bin/vibe" ]] && { "$VIBE_ROOT/bin/vibe" "$@"; return; }
    echo "❌ Global vibe not found" >&2; return 1
  fi
  # Local -> git root -> VIBE_ROOT
  [[ -x "./bin/vibe" ]] && { "./bin/vibe" "$@"; return; }
  if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    local root; root="$(git rev-parse --show-toplevel)"
    [[ -x "$root/bin/vibe" ]] && { "$root/bin/vibe" "$@"; return; }
  fi
  [[ -x "$VIBE_ROOT/bin/vibe" ]] && { "$VIBE_ROOT/bin/vibe" "$@"; return; }
  echo "❌ Could not find 'vibe' executable." >&2; return 1
}
