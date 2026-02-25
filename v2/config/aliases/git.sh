#!/usr/bin/env zsh
# Git helper functions

# Get git root directory
vibe_git_root() { git -C "$PWD" rev-parse --show-toplevel 2>/dev/null; }

# Get current branch
vibe_branch() { git -C "$PWD" branch --show-current 2>/dev/null; }

# Guard main/master branch from agent execution
vibe_main_guard() {
  local br; br="$(vibe_branch)"
  [[ "$br" == "main" || "$br" == "master" ]] && {
    echo "⚠️  You are on '$br'. Use a worktree for agent execution."; return 1
  }
}
