#!/usr/bin/env zsh
# ======================================================
# Git 辅助函数
# ======================================================

# 获取 git root 目录
vibe_git_root() {
  git -C "$PWD" rev-parse --show-toplevel 2>/dev/null
}

# 获取当前分支
vibe_branch() {
  git -C "$PWD" branch --show-current 2>/dev/null
}

# 保护 main/master 分支（防止在这些分支上执行代理操作）
vibe_main_guard() {
  local br
  br="$(vibe_branch)"
  if [[ "$br" == "main" || "$br" == "master" ]]; then
    echo "⚠️  You are on '$br'. Use a worktree for agent execution."
    return 1
  fi
}
