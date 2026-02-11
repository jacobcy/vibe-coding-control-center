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
VIBE_HOME="${VIBE_HOME:-$HOME/.vibe}"

# Resolve VIBE_ROOT from symlink (Zsh specific :A modifier)
# ${(%):-%x} gives source file path, :A resolves to absolute physical path
VIBE_ROOT="$(cd "$(dirname "${(%):-%x:A}")/.." && pwd)"

VIBE_REPO="$(dirname "$VIBE_ROOT")"
VIBE_MAIN="$VIBE_REPO/main"
VIBE_SESSION="${VIBE_SESSION:-vibe}"

export PATH="$VIBE_ROOT/bin:$PATH"

# ---------- Utilities ----------
vibe_has() { command -v "$1" >/dev/null 2>&1; }

vibe_die() { echo "❌ $*" >&2; return 1; }

vibe_require() {
  local miss=()
  for c in "$@"; do vibe_has "$c" || miss+=("$c"); done
  ((${#miss[@]}==0)) || vibe_die "Missing commands: ${miss[*]}"
}

vibe_now() { date +"%Y-%m-%d %H:%M:%S"; }

# ---------- Context Loading ----------
# Helper to load local keys.env if present in PWD or Git root
vibe_load_context() {
    local ctx_home=""
    # 1. Check current directory
    if [[ -d "$PWD/.vibe" ]]; then
        ctx_home="$PWD/.vibe"
    # 2. Check git root
    elif git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local gr="$(git rev-parse --show-toplevel 2>/dev/null)"
        if [[ -d "$gr/.vibe" ]]; then
            ctx_home="$gr/.vibe"
        fi
    fi

    # Load keys if found (override global)
    if [[ -n "$ctx_home" && -f "$ctx_home/keys.env" ]]; then
        set -a
        source "$ctx_home/keys.env"
        set +a
    fi
}

# ---------- tmux core ----------
vibe_tmux_ensure() {
  vibe_load_context
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
# usage: wtnew <branch-name> [agent=claude|opencode|codex] [base-branch=main]
wtnew() {
  vibe_load_context
  # Find git command - rely on PATH
  if ! command -v git >/dev/null 2>&1; then
    vibe_die "git command not found. Please ensure git is installed and in your PATH."
  fi
  local git_cmd="git"

  local branch="$1"
  local agent="${2:-claude}"
  local base="${3:-main}"

  [[ -z "$branch" ]] && vibe_die "usage: wtnew <branch-name> [agent=claude|opencode|codex] [base-branch=main]"

  # Check if current directory is the main worktree
  local current_dir="$(pwd)"
  
  # Try to find main directory in common locations
  local found_main=""
  local search_paths=(
    "$current_dir/main"           # Child directory
    "$current_dir"                # Current directory (if it's main itself)
    "$(dirname "$current_dir")/main"  # Sibling directory
  )
  
  for path in "${search_paths[@]}"; do
    if [[ -d "$path/.git" || -f "$path/.git" ]]; then
      found_main="$path"
      break
    fi
  done
  
  # If we found a main directory but we're not in it
  if [[ -n "$found_main" && "$current_dir" != "$found_main" ]]; then
    echo "❌ You are not in the main worktree directory"
    echo ""
    echo "   Current: $current_dir"
    echo "   Found main at: $found_main"
    echo ""
    echo "💡 Please cd to the main worktree first:"
    echo "   cd $found_main"
    echo "   wtnew $branch $agent $base"
    return 1
  fi
  
  # If we didn't find main directory at all
  if [[ -z "$found_main" ]]; then
    echo "❌ Main worktree not found"
    echo ""
    echo "   Searched in:"
    echo "   - Current directory: $current_dir"
    echo "   - Child directory: $current_dir/main"
    echo "   - Sibling directory: $(dirname "$current_dir")/main"
    echo ""
    echo "💡 Please ensure you have a main worktree set up, or cd to the correct location."
    return 1
  fi

  local prefix="wt-${agent}-"
  local dir="${prefix}${branch}"
  local path="$VIBE_REPO/$dir"

  # Create branch from base in main repo context
  $git_cmd -C "$found_main" fetch -p >/dev/null 2>&1 || true
  $git_cmd -C "$found_main" show-ref --verify --quiet "refs/heads/$branch" || \
    $git_cmd -C "$found_main" branch "$branch" "$base" 2>/dev/null || true

  # Add worktree
  if [[ -e "$path" ]]; then
    echo "ℹ️  Worktree dir already exists: $dir"
  else
    $git_cmd -C "$found_main" worktree add "$path" "$branch" || return 1
    echo "✅ Created worktree: $dir -> branch $branch (base: $base)"
  fi

  # Set agent identity in worktree
  # Use zsh parameter expansion for capitalization: ${(C)var} capitalizes first letter
  local agent_name="Agent-${(C)agent}"
  local agent_email="agent-${agent}@vibecoding.ai"
  
  $git_cmd -C "$path" config user.name "$agent_name"
  $git_cmd -C "$path" config user.email "$agent_email"
  echo "👤 Git identity set: $agent_name <$agent_email>"

  cd "$path" || return
}

# Re-sync Git identity in current worktree
wtinit() {
  local agent="${1:-claude}"
  
  if [[ ! -d ".git" && ! -f ".git" ]]; then
    vibe_die "Not in a git repository or worktree."
  fi
  
  local agent_name="Agent-${(C)agent}"
  local agent_email="agent-${agent}@vibecoding.ai"
  
  git config user.name "$agent_name"
  git config user.email "$agent_email"
  echo "✅ Git identity re-synced: $agent_name <$agent_email>"
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
# Base commands
alias c='claude'
alias cy='claude'


# Start agent in current dir but protect main/master
# Start agent in current dir but protect main/master
c_safe() { vibe_load_context; vibe_main_guard || return; claude; }

# Start agent in a given worktree (cd + run)
# usage: cwt <wt-dir>
cwt() { local d="$1"; [[ -z "$d" ]] && vibe_die "usage: cwt <wt-dir>"; wt "$d" || return; claude; }
owt() { local d="$1"; [[ -z "$d" ]] && vibe_die "usage: owt <wt-dir>"; wt "$d" || return; opencode; }

# ---------- Endpoint Switching ----------
alias c_cn='export ANTHROPIC_BASE_URL="https://api.bghunt.cn" && echo "🇨🇳 Claude Endpoint: China Proxy"'
alias c_off='export ANTHROPIC_BASE_URL="https://api.anthropic.com" && echo "🌐 Claude Endpoint: Official"'
vibe_endpoint() {
    echo "Current Claude Endpoint: ${ANTHROPIC_BASE_URL:-$(config_get ANTHROPIC_BASE_URL)}"
}

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
  case "$agent" in
    opencode)
      vibe_require opencode || return 1
      vibe_tmux_win "$w_agent" "$dir_path" "opencode" || return 1
      ;;
    codex)
      vibe_require codex || return 1
      vibe_tmux_win "$w_agent" "$dir_path" "codex --yes" || return 1
      ;;
    *)
      vibe_require claude || return 1
      vibe_tmux_win "$w_agent" "$dir_path" "claude" || return 1
      ;;
  esac

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
# usage: vnew <branch> [agent=claude|opencode|codex] [base=main]
vnew() {
  vibe_load_context
  local branch="$1"
  local agent="${2:-claude}"
  local base="${3:-main}"

  [[ -z "$branch" ]] && vibe_die "usage: vnew <branch> [agent=claude|opencode|codex] [base=main]"

  wtnew "$branch" "$agent" "$base" || return 1
  local wt_dir="wt-${agent}-$branch"
  vup "$wt_dir" "$agent" || return 1
  echo "✅ All set. Your job: review/commit in lazygit window (${wt_dir}-git)."
}

# Unified vibe/agent aliases (Priority: Claude -> OpenCode -> Codex)
alias vibe="$VIBE_ROOT/bin/vibe"
alias vc='vibe chat'
alias vsign='vibe sign'
alias vsig='vibe sign'
alias vmsign='vibe sign'

# Claude (Priority 1)
alias c='claude'
alias cy='claude'
alias ca='claude'
# alias cp='claude'
alias cr='claude'

# OpenCode (Priority 2)
alias o='opencode'
alias oa='opencode'



# Attach to tmux session
alias vt='vibe_tmux_attach'

# Quick git
alias gs='git status -sb'
alias gd='git diff'
alias gl='git log --oneline --graph --decorate -20'

# Unified vibe/agent aliases
alias vibe='zsh "$VIBE_ROOT/scripts/vibecoding.sh"'
alias cca='claude --auto'
alias ccp='claude --plan'
alias ccr='claude --review'
alias oca='opencode --auto'
# Optional: go main
alias vmain="cd \"$VIBE_MAIN\""
