#!/usr/bin/env zsh
# Worktree navigation utilities
# Part of V3 Execution Plane

# Jump to a worktree by name
wt() {
  local target="$1"
  [[ -z "$target" ]] && { git worktree list; return; }
  local wt_path
  wt_path="$(git worktree list --porcelain 2>/dev/null |
    awk -v name="$target" '/^worktree /{
      path=substr($0,10); b=path; sub(/.*\//,"",b)
      if(b==name||path==name){print path; exit}
    }')"
  if [[ -n "$wt_path" && -d "$wt_path" ]]; then
    cd "$wt_path" || return
    [[ -n "$TMUX" ]] && tmux rename-window "${target:t}"
  else
    echo "❌ Worktree not found: $target"; git worktree list 2>/dev/null | sed 's/^/   /'; return 1
  fi
}
