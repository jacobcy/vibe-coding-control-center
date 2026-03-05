#!/usr/bin/env zsh
# Claude aliases

# @desc Claude CLI proxy — continue with full permissions
# @featured
alias ccy='claude --dangerously-skip-permissions --continue'
# @desc Run Claude in planning mode
alias ccp='claude --permission-mode plan'

# --- New unified cc* commands ---

# @desc Run Claude safely with main branch protection
# @featured
ccs() {
  vibe_main_guard || return
  claude --dangerously-skip-permissions --continue
}

# @desc Run Claude in a specified worktree
ccwt() {
  local d="$1"
  [[ -z "$d" ]] && vibe_die "usage: ccwt <wt-dir>"
  wt "$d" || return
  claude --dangerously-skip-permissions --continue
}

# @desc Switch to Claude China endpoint
cccn() {
  local ep="${ANTHROPIC_BASE_URL_CHINA:-https://api.myprovider.com}"
  export ANTHROPIC_BASE_URL="$ep"
  echo "🇨🇳 Claude Endpoint: $ep"
}

# @desc Switch to official Claude endpoint
ccoff() { export ANTHROPIC_BASE_URL="https://api.anthropic.com"; echo "Claude Endpoint: Official"; }

# @desc Show current Claude endpoint
ccep() { echo "Claude Endpoint: ${ANTHROPIC_BASE_URL:-https://api.anthropic.com}"; }

# --- Deprecation shims (warn + delegate) ---

# @deprecated use ccs
c_safe() { echo "⚠️  'c_safe' is deprecated, use 'ccs'" >&2; ccs "$@"; }
# @deprecated use ccwt
cwt() { echo "⚠️  'cwt' is deprecated, use 'ccwt'" >&2; ccwt "$@"; }
# @deprecated use cccn
cc_cn() { echo "⚠️  'cc_cn' is deprecated, use 'cccn'" >&2; cccn "$@"; }
# @deprecated use ccoff
cc_off() { echo "⚠️  'cc_off' is deprecated, use 'ccoff'" >&2; ccoff "$@"; }
# @deprecated use ccep
cc_endpoint() { echo "⚠️  'cc_endpoint' is deprecated, use 'ccep'" >&2; ccep "$@"; }
