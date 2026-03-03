#!/usr/bin/env zsh
# lib/utils/helpers.sh - Helper utilities
# Target: ~40 lines | Pure functions, no side effects

# ── Interaction ─────────────────────────────────────────
confirm_action() {
    local prompt="${1:-Are you sure?}"
    local response
    echo -n "${YELLOW}? $prompt [y/N]: ${NC}"
    read -r response
    [[ "$response" =~ ^[yY](es)?$ ]]
}

# ── Command Helpers ─────────────────────────────────────
# Check if a command exists
vibe_has() {
    command -v "$1" >/dev/null 2>&1
}

# Require commands to exist
vibe_require() {
    local miss=()
    local c
    for c in "$@"; do
        vibe_has "$c" || miss+=("$c")
    done
    ((${#miss[@]} == 0)) || vibe_die "Missing commands: ${miss[*]}"
}

# Resolve command path from PATH or common install locations
vibe_find_cmd() {
    local cmd="$1"
    command -v "$cmd" 2>/dev/null && return 0
    local p
    for p in "/opt/homebrew/bin/$cmd" "/usr/local/bin/$cmd" "/usr/bin/$cmd"; do
        [[ -x "$p" ]] && { echo "$p"; return 0; }
    done
    return 1
}

# Print error and return failure
vibe_die() {
    echo "${RED}✗ $*${NC}" >&2
    return 1
}
