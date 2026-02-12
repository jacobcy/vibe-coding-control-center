#!/usr/bin/env zsh
# Vibe Coding Control Center - Unified Shell Loader
# Sourced once from ~/.zshrc. Handles PATH + aliases for all branches.
# DO NOT EDIT - managed by `scripts/install.sh`
#
# Resolution order:
#   1. Local: $PWD/.vibe  → project bin + local aliases
#   2. Global: ~/.vibe    → fallback bin + global aliases

# ---------- PATH ----------
# Always add global bin as baseline
export PATH="$HOME/.vibe/bin:$PATH"

# If a local .vibe exists in PWD (branch worktree), prepend its bin
if [[ -d "$PWD/.vibe" ]]; then
    # The project root is the parent of .vibe
    local _vibe_local_root="$PWD"
    if [[ -d "$_vibe_local_root/bin" ]]; then
        export PATH="$_vibe_local_root/bin:$PATH"
    fi
fi

# ---------- Aliases ----------
# Source aliases from the global install; aliases.sh internally uses
# config.sh to auto-detect VIBE_ROOT, so the `vibe()` function will
# dynamically resolve ./bin/vibe → git-root/bin/vibe → $VIBE_ROOT/bin/vibe.
if [[ -f "$HOME/.vibe/aliases.sh" ]]; then
    source "$HOME/.vibe/aliases.sh"
fi
