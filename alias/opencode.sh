#!/usr/bin/env zsh
# OpenCode aliases

# @desc OpenCode CLI proxy
alias oo='opencode'
# @desc Continue last OpenCode session
# @featured
alias ooa='opencode --continue'

# @desc Run OpenCode in a feature worktree
oowt() {
  local d="$1"
  [[ -z "$d" ]] && vibe_die "usage: oowt <wt-dir>"
  wt "$d" || return
  opencode
}

# --- Deprecation shim ---

# @deprecated use oowt
owt() { echo "⚠️  'owt' is deprecated, use 'oowt'" >&2; oowt "$@"; }
