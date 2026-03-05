#!/usr/bin/env zsh
# Git helper functions

# @desc Get git root directory
vibe_git_root() { git -C "$PWD" rev-parse --show-toplevel 2>/dev/null; }

# @desc Get current branch
vibe_branch() { git -C "$PWD" branch --show-current 2>/dev/null; }

# @desc Guard main/master branch from agent execution
vibe_main_guard() {
  local br; br="$(vibe_branch)"
  [[ "$br" == "main" || "$br" == "master" ]] && {
    echo "⚠️  You are on '$br'. Use a worktree for agent execution."; return 1
  }
}

# --- Common Git Aliases ---

# @desc Git status
# @featured
alias gst='git status'

# @desc Git log (pretty)
# @featured
alias gl='git log --oneline --graph --decorate'

# @desc Quick git commit
alias gca='git commit -a -m'

# @desc Quick git push
alias gp='git push'
