#!/usr/bin/env zsh
# config/shell/aliases.sh - Compatibility shim for Vibe 2.0
# DEPRECATED: Use source $(vibe alias --load) which points to lib/alias/loader.sh

_v_shim_self="$(dirname "${(%):-%x:A}")"
_v_root="$(cd "$_v_shim_self/../.." && pwd)"
_v_new_loader="$_v_root/lib/alias/loader.sh"
_v_legacy_alias_dir="$_v_shim_self/aliases"
_v_legacy_loaded=0

if [[ -f "$_v_new_loader" ]]; then
  source "$_v_new_loader"
elif [[ -d "$_v_legacy_alias_dir" ]]; then
  if [[ -f "$_v_root/lib/config.sh" ]]; then
    source "$_v_root/lib/config.sh"
  else
    export VIBE_ROOT="$_v_root"
    export VIBE_BIN="$VIBE_ROOT/bin"
    export VIBE_LIB="$VIBE_ROOT/lib"
    export VIBE_CONFIG="$VIBE_ROOT/config"
  fi

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

  for _v_alias_file in git.sh tmux.sh worktree.sh claude.sh opencode.sh openspec.sh vibe.sh; do
    if [[ -f "$_v_legacy_alias_dir/$_v_alias_file" ]]; then
      source "$_v_legacy_alias_dir/$_v_alias_file"
      _v_legacy_loaded=1
    fi
  done
else
  echo "vibe: error: no compatible alias loader found in $_v_root" >&2
fi

if [[ ( -f "$_v_new_loader" || $_v_legacy_loaded -eq 1 ) && -o interactive ]]; then
  echo "✅ Vibe aliases loaded (source \$(vibe alias --load))"
fi

unset _v_alias_file _v_legacy_alias_dir _v_legacy_loaded _v_new_loader _v_root _v_shim_self
