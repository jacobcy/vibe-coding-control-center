#!/usr/bin/env zsh
# v2/lib/config.sh - Configuration for Vibe 2.0
# Target: ~40 lines | Single source of truth for paths

# ── VIBE_ROOT Detection ─────────────────────────────────
# Simple: resolve from script location (one level up from lib/)
VIBE_ROOT="${VIBE_ROOT:-$(cd "$(dirname "${(%):-%x}")/.." && pwd)}"
export VIBE_ROOT

# ── Core Directories ────────────────────────────────────
export VIBE_BIN="$VIBE_ROOT/bin"
export VIBE_LIB="$VIBE_ROOT/lib"
export VIBE_CONFIG="$VIBE_ROOT/config"
export VIBE_AGENT="$VIBE_ROOT/.agent"

# ── Load Utils ──────────────────────────────────────────
[[ -z "$VIBE_UTILS_LOADED" ]] && source "$VIBE_LIB/utils.sh" && VIBE_UTILS_LOADED=1

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
