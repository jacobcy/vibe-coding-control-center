#!/usr/bin/env zsh
# ======================================================
# Claude 命令
# 命名规范: cc* (Claude Commands)
# ======================================================

# Claude 快速命令（跳过权限检查，继续之前的会话）
alias ccy='claude --dangerously-skip-permissions --continue'

# Claude Plan 模式
alias ccp='claude --permission-mode plan'

# Claude 在当前目录运行（保护 main 分支）
c_safe() {
  vibe_load_context
  vibe_main_guard || return
  claude --dangerously-skip-permissions --continue
}

# Claude 在指定 worktree 运行
# usage: cwt <wt-dir>
cwt() {
  local d="$1"
  [[ -z "$d" ]] && vibe_die "usage: cwt <wt-dir>"
  wt "$d" || return
  claude --dangerously-skip-permissions --continue
}

# ---------- Endpoint Switching ----------

# 切换到自定义 endpoint（中国）
cc_cn() {
  local endpoint
  # Try to get from config cache or file
  endpoint="$(config_get ANTHROPIC_BASE_URL)"
  # Fallback to hardcoded if not set
  if [[ -z "$endpoint" || "$endpoint" == "https://api.anthropic.com" ]]; then
       endpoint="${ANTHROPIC_BASE_URL_CHINA:-https://api.myprovider.com}"
  fi
  export ANTHROPIC_BASE_URL="$endpoint"
  echo "🇨🇳 Claude Endpoint: Custom ($endpoint)"
}

# 切换到官方 endpoint
cc_off() {
  export ANTHROPIC_BASE_URL="https://api.anthropic.com"
  echo "Claude Endpoint: Official"
}

# 显示当前 endpoint
cc_endpoint() {
  echo "Current Claude Endpoint: ${ANTHROPIC_BASE_URL:-$(config_get ANTHROPIC_BASE_URL)}"
}
