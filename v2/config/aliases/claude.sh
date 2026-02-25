#!/usr/bin/env zsh
# Claude aliases

alias ccy='claude --dangerously-skip-permissions --continue'
alias ccp='claude --permission-mode plan'

# Claude with main-branch guard
c_safe() {
  vibe_main_guard || return
  claude --dangerously-skip-permissions --continue
}

# Claude in a worktree
cwt() {
  local d="$1"
  [[ -z "$d" ]] && vibe_die "usage: cwt <wt-dir>"
  wt "$d" || return
  claude --dangerously-skip-permissions --continue
}

# Endpoint switching
cc_cn() {
  local ep="${ANTHROPIC_BASE_URL_CHINA:-https://api.myprovider.com}"
  export ANTHROPIC_BASE_URL="$ep"
  echo "🇨🇳 Claude Endpoint: $ep"
}
cc_off() { export ANTHROPIC_BASE_URL="https://api.anthropic.com"; echo "Claude Endpoint: Official"; }
cc_endpoint() { echo "Claude Endpoint: ${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"; }
