#!/usr/bin/env zsh
# alias/loader.sh - Runtime alias loader for Vibe 2.0
# Main entry point for user shell integration

# ── Self-resolve VIBE_ROOT ────────────────────────────────
if [[ -n "${ZSH_VERSION:-}" ]]; then
  _al_loader_path="${(%):-%x:A}"
else
  _al_loader_path="$(readlink -f "${BASH_SOURCE[0]:-$0}" 2>/dev/null || echo "${BASH_SOURCE[0]:-$0}")"
fi
_al_loader_dir="$(dirname "$_al_loader_path")"
_al_root="$(cd "$_al_loader_dir/.." && pwd)"

# ── Force VIBE_ROOT to this loader's location ──────────────
# Always override to ensure local repo takes precedence
export VIBE_ROOT="$_al_root"
export VIBE_BIN="$VIBE_ROOT/bin"
export VIBE_LIB="$VIBE_ROOT/lib"
export VIBE_CONFIG="$VIBE_ROOT/config"
export VIBE_AGENT="$VIBE_ROOT/.agent"

# ── Context Resolution ────────────────────────────────────
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  export VIBE_REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
else
  export VIBE_REPO="$(dirname "$VIBE_ROOT")"
fi

if [[ -d "$VIBE_REPO/main" && ( -d "$VIBE_REPO/main/.git" || -f "$VIBE_REPO/main/.git" ) ]]; then
  export VIBE_MAIN="$VIBE_REPO/main"
else
  export VIBE_MAIN="$VIBE_REPO"
fi
export VIBE_SESSION="${VIBE_SESSION:-vibe}"

# ── Clear cached functions (ensures fresh load) ─────────────
unset -f wt wtls wtnew wtrm vup vnew 2>/dev/null || true
unset -f cc{,wt} cx oc gm oo{,a,d,p} vc vsign vmain vt vtup vtdown vtswitch vtls vtkill 2>/dev/null || true

# ── Source Aliases ────────────────────────────────────────
_al_src_dir="$VIBE_ROOT/alias"
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
