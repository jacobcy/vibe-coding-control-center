#!/usr/bin/env zsh
# v2/lib/config.sh - Configuration for Vibe 2.0
# Target: ~40 lines | Single source of truth for paths

# ── VIBE_ROOT Detection ─────────────────────────────────
# Always resolve from this script's location (one level up from lib/) if not overridden.
# Never inherit from parent shell to prevent cross-worktree contamination by default.
if [[ -n "${ZSH_VERSION:-}" ]]; then
    _SCRIPT_PATH="${(%):-%x}"
else
    _SCRIPT_PATH="${BASH_SOURCE[0]:-$0}"
fi
_DETECTED_ROOT="$(cd "$(dirname "$_SCRIPT_PATH")/.." && pwd)"

if [[ -n "${VIBE_ROOT:-}" && "$VIBE_ROOT" != "$_DETECTED_ROOT" ]]; then
    # Overridden (likely a test or nested context)
    export VIBE_BIN="${VIBE_BIN:-$VIBE_ROOT/bin}"
    export VIBE_LIB="${VIBE_LIB:-$VIBE_ROOT/lib}"
    export VIBE_CONFIG="${VIBE_CONFIG:-$VIBE_ROOT/config}"
else
    # Normal usage or matches - Force derivation to prevent contamination (Rule 7)
    export VIBE_ROOT="$_DETECTED_ROOT"
    export VIBE_BIN="$VIBE_ROOT/bin"
    export VIBE_LIB="$VIBE_ROOT/lib"
    export VIBE_CONFIG="$VIBE_ROOT/config"
fi
export VIBE_AGENT="${VIBE_AGENT:-$VIBE_ROOT/.agent}"

# ── Load Utils ──────────────────────────────────────────
if [[ "${VIBE_UTILS_LOADED:-}" != "$VIBE_LIB/utils.sh" ]]; then
    source "$VIBE_LIB/utils.sh"
    VIBE_UTILS_LOADED="$VIBE_LIB/utils.sh"
fi

# ── Load Keys (if keys.env exists) ──────────────────────
_vibe_load_keys() {
    local keys_file="$1"
    [[ -f "$keys_file" ]] || return 0
    while IFS='=' read -r key value; do
        # Skip comments and empty lines
        [[ "$key" =~ ^[[:space:]]*# ]] && continue
        [[ -z "$key" ]] && continue
        # Strip surrounding quotes from value
        value="${value#\"}" ; value="${value%\"}"
        value="${value#\'}" ; value="${value%\'}"
        export "$key=$value"
    done < "$keys_file"
}

# Load project keys.env, then user keys.env
_vibe_load_keys "$VIBE_CONFIG/keys.env"
_vibe_load_keys "${HOME}/.vibe/keys.env"

# ── Defaults ────────────────────────────────────────────
export VIBE_DEFAULT_TOOL="${VIBE_DEFAULT_TOOL:-claude}"
export VIBE_SESSION="${VIBE_SESSION:-vibe}"
