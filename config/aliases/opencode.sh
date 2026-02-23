#!/usr/bin/env zsh
# ======================================================
# OpenCode 命令
# 命名规范: oo* (OpenCode)
# ======================================================

# OpenCode 标准命令
alias oo='opencode'

# OpenCode 继续之前的会话
alias ooa='opencode --continue'

# OpenCode 在指定 worktree 运行
# usage: owt <wt-dir>
owt() {
  local d="$1"
  [[ -z "$d" ]] && vibe_die "usage: owt <wt-dir>"
  wt "$d" || return
  opencode
}
