#!/usr/bin/env zsh
# lib/alias/loader.sh - Runtime alias loader for Vibe 2.0
# Main entry point for user shell integration

# ── Self-resolve VIBE_ROOT ────────────────────────────────
if [[ -n "${ZSH_VERSION:-}" ]]; then
  _al_loader_path="${(%):-%x:A}"
else
  _al_loader_path="$(readlink -f "${BASH_SOURCE[0]:-$0}" 2>/dev/null || echo "${BASH_SOURCE[0]:-$0}")"
fi
_al_loader_dir="$(dirname "$_al_loader_path")"
_al_root="$(cd "$_al_loader_dir/../.." && pwd)"

# ── Force VIBE_ROOT to this loader's location ──────────────
# Always override to ensure local repo takes precedence
export VIBE_ROOT="$_al_root"
export VIBE_BIN="$VIBE_ROOT/bin"
export VIBE_LIB="$VIBE_ROOT/lib"
export VIBE_CONFIG="$VIBE_ROOT/config"
export VIBE_AGENT="$VIBE_ROOT/.agent"

# Ensure shared helper functions (e.g., vibe_find_cmd) are available
if [[ -f "$VIBE_LIB/utils.sh" ]]; then
  source "$VIBE_LIB/utils.sh"
fi

# ── Context Resolution ────────────────────────────────────
# VIBE_REPO: 主仓库根目录（包含 .git 和 .worktrees 的目录）
# VIBE_MAIN: main worktree 的位置
#
# 场景1 - 单 worktree（直接 clone）：
#   VIBE_REPO = clone 目录（包含 .git）
#   VIBE_MAIN = VIBE_REPO（没有 .worktrees/main）
#
# 场景2 - 多 worktree（bare repo）：
#   VIBE_REPO = bare repo 目录（包含 .git 和 .worktrees）
#   VIBE_MAIN = $VIBE_REPO/.worktrees/main

if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  # 获取 git common dir（共享 .git 目录）
  # - 单 worktree: .git
  # - 多 worktree: 绝对路径（如 /path/to/repo/.git）
  local git_common_dir="$(git rev-parse --git-common-dir 2>/dev/null || true)"

  if [[ -n "$git_common_dir" && -d "$git_common_dir" ]]; then
    # VIBE_REPO 是 .git 的父目录
    export VIBE_REPO="$(cd "$git_common_dir/.." && pwd)"
  else
    # Fallback: 使用 show-toplevel
    export VIBE_REPO="$(git rev-parse --show-toplevel 2>/dev/null || dirname "$VIBE_ROOT")"
  fi
else
  export VIBE_REPO="$(dirname "$VIBE_ROOT")"
fi

# VIBE_MAIN: 在 VIBE_REPO 下查找 main
if [[ -d "$VIBE_REPO/.worktrees/main" ]]; then
  # 多 worktree 模式：main 在 .worktrees/main
  export VIBE_MAIN="$VIBE_REPO/.worktrees/main"
elif [[ -d "$VIBE_REPO/main" && ( -d "$VIBE_REPO/main/.git" || -f "$VIBE_REPO/main/.git" ) ]]; then
  # 兼容旧结构：main 作为子目录
  export VIBE_MAIN="$VIBE_REPO/main"
else
  # 单 worktree 模式：没有独立的 main
  export VIBE_MAIN="$VIBE_REPO"
fi
export VIBE_SESSION="${VIBE_SESSION:-vibe}"

# ── Clear cached functions (ensures fresh load) ─────────────
unset -f wt wtls wtnew wtrm vup vnew 2>/dev/null || true
unset -f cc{,i} cx{,i} oc{,i} gm{,i} oo{,a,d,p} vc vsign vmain vt vtup vtdown vtswitch vtls vtkill 2>/dev/null || true

# ── Source Aliases ────────────────────────────────────────
_al_src_dir="$VIBE_LIB/alias"
_al_loaded=0
for f in git.sh tmux.sh worktree.sh agent.sh openspec.sh vibe.sh vibe3.sh; do
  if [[ -f "$_al_src_dir/$f" ]]; then
    source "$_al_src_dir/$f"
    ((_al_loaded++))
  fi
done

if [[ $(( _al_loaded )) -gt 0 && -o interactive ]]; then
  echo "✅ Vibe aliases loaded from $VIBE_ROOT ($_al_loaded files)"
fi

unset _al_loader_path _al_loader_dir _al_root _al_src_dir _al_loaded
