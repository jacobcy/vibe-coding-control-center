#!/usr/bin/env zsh
# OpenCode aliases

alias oo='opencode'
alias ooa='opencode --continue'

# Run opencode in a worktree
owt() {
  local d="$1"
  [[ -z "$d" ]] && vibe_die "usage: owt <wt-dir>"
  wt "$d" || return
  opencode
}
