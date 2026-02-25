#!/usr/bin/env zsh
# config/aliases.sh - Alias loader for Vibe 2.0
# Sources config.sh (paths + utils + keys) then all alias sub-files

# ── Resolve VIBE_ROOT ──────────────────────────────────
_al_dir="$(dirname "${(%):-%x:A}")"
[[ -L "${(%):-%x}" ]] && _al_dir="$(dirname "$(readlink -f "${(%):-%x}" 2>/dev/null || readlink "${(%):-%x}")")"
_al_lib="$_al_dir/../lib/config.sh"
[[ -f "$_al_lib" ]] && source "$_al_lib" || { VIBE_ROOT="$(cd "$_al_dir/.." && pwd)"; }

# Detect repo root and main dir
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  VIBE_REPO="$(git rev-parse --show-toplevel 2>/dev/null)"
else
  VIBE_REPO="$(dirname "$VIBE_ROOT")"
fi
if [[ -d "$VIBE_REPO/main" && (-d "$VIBE_REPO/main/.git" || -f "$VIBE_REPO/main/.git") ]]; then
  VIBE_MAIN="$VIBE_REPO/main"
else
  VIBE_MAIN="$VIBE_REPO"
fi
VIBE_SESSION="${VIBE_SESSION:-vibe}"

# ── Load alias sub-files (order matters: git → tmux → worktree → rest) ──
_al_src="$_al_dir/aliases"
for f in git.sh tmux.sh worktree.sh claude.sh opencode.sh openspec.sh vibe.sh; do
  [[ -f "$_al_src/$f" ]] && source "$_al_src/$f"
done

unset _al_dir _al_lib _al_src
