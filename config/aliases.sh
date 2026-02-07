#!/usr/bin/env zsh
# ======================================================
# Vibe Coding Aliases (Level 2)
# Worktree × tmux × Agents (Claude/Codex) × lazygit
# Philosophy:
#   - Agents do the work unattended (auto-approve)
#   - You only review/commit (lazygit)
#   - Main branch is protected (guard)
# ======================================================

# ---------- Base ----------
VIBE_ROOT="$(cd "$(dirname "${(%):-%x}")/.." && pwd)"
VIBE_REPO="$VIBE_ROOT"
VIBE_MAIN="$VIBE_REPO/main"
VIBE_SESSION="${VIBE_SESSION:-vibe}"

# ---------- Utilities ----------
vibe_has() { command -v "$1" >/dev/null 2>&1; }

vibe_die() { echo "❌ $*" >&2; return 1; }

vibe_require() {
  local miss=()
  for c in "$@"; do vibe_has "$c" || miss+=("$c"); done
  ((${#miss[@]}==0)) || vibe_die "Missing commands: ${miss[*]}"
}

vibe_now() { date +"%Y-%m-%d %H:%M:%S"; }

# ---------- tmux core ----------
vibe_tmux_ensure() {
  vibe_require tmux || return 1
  if ! tmux has-session -t "$VIBE_SESSION" 2>/dev/null; then
    tmux new-session -d -s "$VIBE_SESSION" -c "$VIBE_MAIN" -n "main"
  fi
}

vibe_tmux_attach() {
  vibe_tmux_ensure || return 1
  tmux attach -t "$VIBE_SESSION"
}

# Create or focus a window
vibe_tmux_win() {
  # usage: vibe_tmux_win <name> <dir> [cmd...]
  local name="$1"; shift
  local dir="$1"; shift
  local cmd="$*"

  vibe_tmux_ensure || return 1

  if tmux list-windows -t "$VIBE_SESSION" -F "#{window_name}" | grep -qx "$name"; then
    tmux select-window -t "$VIBE_SESSION:$name"
  else
    if [[ -n "$cmd" ]]; then
      tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir" "$cmd"
    else
      tmux new-window -t "$VIBE_SESSION" -n "$name" -c "$dir"
    fi
  fi
}

# ---------- Git helpers ----------
vibe_git_root() {
  git -C "$PWD" rev-parse --show-toplevel 2>/dev/null
}

vibe_branch() {
  git -C "$PWD" branch --show-current 2>/dev/null
}

vibe_main_guard() {
  local br
  br="$(vibe_branch)"
  if [[ "$br" == "main" || "$br" == "master" ]]; then
    echo "⚠️  You are on '$br'. Use a worktree for agent execution."
    return 1
  fi
}

# ---------- Worktree ----------
# List worktrees
alias wtls='git worktree list'

# Jump to a worktree directory under repo root
wt() {
  local target="$1"
  if [[ -z "$target" ]]; then
    git -C "$VIBE_REPO" worktree list
    return
  fi
  cd "$VIBE_REPO/$target" || return
  [[ -n "$TMUX" ]] && tmux rename-window "$target"
}

# Create a new worktree (safe default naming)
# usage: wtnew <branch-name> [base-branch=main] [dir-prefix=wt-]
wtnew() {
  vibe_require git || return 1

  local branch="$1"
  local base="${2:-main}"
  local prefix="${3:-wt-}"

  [[ -z "$branch" ]] && vibe_die "usage: wtnew <branch-name> [base-branch=main] [dir-prefix=wt-]"

  local dir="${prefix}${branch}"
  local path="$VIBE_REPO/$dir"

  # Ensure main worktree exists as base checkout
  [[ -d "$VIBE_MAIN/.git" || -f "$VIBE_MAIN/.git" ]] || \
    vibe_die "Expected main worktree at: $VIBE_MAIN (run your worktree layout first)"

  # Create branch from base in main repo context
  git -C "$VIBE_MAIN" fetch -p >/dev/null 2>&1 || true
  git -C "$VIBE_MAIN" show-ref --verify --quiet "refs/heads/$branch" || \
    git -C "$VIBE_MAIN" branch "$branch" "$base" 2>/dev/null || true

  # Add worktree
  if [[ -e "$path" ]]; then
    echo "ℹ️  Worktree dir already exists: $dir"
  else
    git -C "$VIBE_MAIN" worktree add "$path" "$branch" || return 1
    echo "✅ Created worktree: $dir -> branch $branch (base: $base)"
  fi

  cd "$path" || return
}

# Remove a worktree directory + prune
# usage: wtrm <wt-dir>
wtrm() {
  vibe_require git || return 1
  local dir="$1"
  [[ -z "$dir" ]] && vibe_die "usage: wtrm <wt-dir>"
  local path="$VIBE_REPO/$dir"

  git -C "$VIBE_MAIN" worktree remove --force "$path" || return 1
  git -C "$VIBE_MAIN" worktree prune >/dev/null 2>&1 || true
  echo "✅ Removed worktree: $dir"
}

# ---------- Agents (Claude/Codex) ----------
alias lg='lazygit'

# Base commands
alias c='claude'
alias cy='claude --yes'
alias x='codex'
alias xy='codex --yes'

# Start agent in current dir but protect main/master
c_safe() { vibe_main_guard || return; claude --yes; }
x_safe() { vibe_main_guard || return; codex --yes; }

# Start agent in a given worktree (cd + run)
# usage: cwt <wt-dir> / xwt <wt-dir>
cwt() { local d="$1"; [[ -z "$d" ]] && vibe_die "usage: cwt <wt-dir>"; wt "$d" || return; claude --yes; }
xwt() { local d="$1"; [[ -z "$d" ]] && vibe_die "usage: xwt <wt-dir>"; wt "$d" || return; codex --yes; }

# ---------- “One-button” Workspace Orchestration ----------
# Create a full tmux workspace for a worktree:
# windows:
#   <wt>-edit    (your editor)
#   <wt>-agent   (Claude/Codex auto-approve)
#   <wt>-tests   (placeholder shell)
#   <wt>-logs    (placeholder shell)
#   <wt>-git     (lazygit)
#
# usage:
#   vup <wt-dir> [agent=claude|codex] [editor_cmd]
vup() {
  vibe_require tmux git || return 1

  local wt_dir="$1"
  local agent="${2:-claude}"
  local editor_cmd="${3:-${EDITOR:-vim}}"

  [[ -z "$wt_dir" ]] && vibe_die "usage: vup <wt-dir> [agent=claude|codex] [editor_cmd]"

  local dir_path="$VIBE_REPO/$wt_dir"
  [[ -d "$dir_path" ]] || vibe_die "worktree dir not found: $dir_path"

  vibe_tmux_ensure || return 1

  local w_edit="${wt_dir}-edit"
  local w_agent="${wt_dir}-agent"
  local w_tests="${wt_dir}-tests"
  local w_logs="${wt_dir}-logs"
  local w_git="${wt_dir}-git"

  # Editor window
  vibe_tmux_win "$w_edit" "$dir_path" "$editor_cmd" || return 1

  # Agent window
  if [[ "$agent" == "codex" ]]; then
    vibe_require codex || return 1
    vibe_tmux_win "$w_agent" "$dir_path" "codex --yes" || return 1
  else
    vibe_require claude || return 1
    vibe_tmux_win "$w_agent" "$dir_path" "claude --yes" || return 1
  fi

  # Tests/logs windows (leave as interactive shells so you can run what you want)
  vibe_tmux_win "$w_tests" "$dir_path" || return 1
  vibe_tmux_win "$w_logs" "$dir_path" || return 1

  # lazygit window
  vibe_require lazygit || echo "⚠️  lazygit not found; '$w_git' will open a shell"
  if vibe_has lazygit; then
    vibe_tmux_win "$w_git" "$dir_path" "lazygit" || return 1
  else
    vibe_tmux_win "$w_git" "$dir_path" || return 1
  fi

  echo "✅ tmux workspace ready for: $wt_dir (agent: $agent) @ $(vibe_now)"
  echo "👉 attach with: vt"
}

# One-button: create worktree + bring up tmux workspace
# usage: vnew <branch> [agent=claude|codex] [base=main]
vnew() {
  local branch="$1"
  local agent="${2:-claude}"
  local base="${3:-main}"

  [[ -z "$branch" ]] && vibe_die "usage: vnew <branch> [agent=claude|codex] [base=main]"

  wtnew "$branch" "$base" "wt-" || return 1
  local wt_dir="wt-$branch"
  vup "$wt_dir" "$agent" || return 1
  echo "✅ All set. Your job: review/commit in lazygit window (${wt_dir}-git)."
}

# Attach to tmux session
alias vt='vibe_tmux_attach'

# Quick git
alias gs='git status -sb'
alias gd='git diff'
alias gl='git log --oneline --graph --decorate -20'

# Unified vibe/agent aliases
alias vibe='zsh "$VIBE_ROOT/scripts/vibecoding.sh"'
alias ca='claude --auto'
alias cp='claude --plan'
alias cr='claude --review'
alias oa='opencode --auto'

# Optional: go main
alias vmain="cd \"$VIBE_MAIN\""
