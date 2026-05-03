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
export PATH="${HOME}/.vibe/bin:${PATH}"

# If a local .vibe exists in PWD (branch worktree), prepend its bin
if [[ -d "${PWD}/.vibe" && -d "${PWD}/bin" ]]; then
    export PATH="${PWD}/bin:${PATH}"
fi

# ---------- Aliases ----------
# Source aliases from the global install; aliases.sh internally resolves VIBE_ROOT.
if [[ -f "${HOME}/.vibe/config/shell/aliases.sh" ]]; then
    source "${HOME}/.vibe/config/shell/aliases.sh"
elif [[ -f "${HOME}/.vibe/config/aliases.sh" ]]; then
    source "${HOME}/.vibe/config/aliases.sh"
fi

# ---------- Config ----------
# Load keys.env so VIBE_* vars are available to all tools
_keys_load() {
    local f="$1"
    [[ -f "$f" ]] || return 1
    while IFS='=' read -r key value; do
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        export "$key=$value"
    done < "$f"
    return 0
}
_keys_load "${HOME}/.vibe/config/keys.env"
