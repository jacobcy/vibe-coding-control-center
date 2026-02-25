#!/usr/bin/env zsh
# v2/lib/utils.sh - Minimalist Utilities for Vibe 2.0
# Target: ~60 lines | No dead code

# ── Colors ──────────────────────────────────────────────
readonly RED=$'\033[0;31m'
readonly GREEN=$'\033[0;32m'
readonly YELLOW=$'\033[1;33m'
readonly BLUE=$'\033[0;34m'
readonly CYAN=$'\033[0;36m'
readonly BOLD=$'\033[1m'
readonly NC=$'\033[0m'

# ── Logging ─────────────────────────────────────────────
log_info()    { echo "${GREEN}✓ $1${NC}"; }
log_warn()    { echo "${YELLOW}! $1${NC}" >&2; }
log_error()   { echo "${RED}✗ $1${NC}" >&2; }
log_step()    { echo "${BLUE}>> $1...${NC}"; }
log_success() { echo "${GREEN}★ $1${NC}"; }

# ── Interaction ─────────────────────────────────────────
confirm_action() {
    local prompt="${1:-Are you sure?}"
    local response
    echo -n "${YELLOW}? $prompt [y/N]: ${NC}"
    read -r response
    [[ "$response" =~ ^[yY](es)?$ ]]
}

# ── Path Validation ─────────────────────────────────────
validate_path() {
    local path="$1"
    [[ -z "$path" ]] && { log_error "Empty path"; return 1; }
    [[ "$path" == *".."* ]] && { log_error "Path traversal detected: $path"; return 1; }
    return 0
}

# ── Version ─────────────────────────────────────────────
get_vibe_version() {
    local vfile="${VIBE_ROOT:-$(cd "$(dirname "${(%):-%x}")/.." && pwd)}/VERSION"
    [[ -f "$vfile" ]] && cat "$vfile" || echo "2.0.0-dev"
}

# ── Command Helpers ─────────────────────────────────────
# Check if a command exists
vibe_has() {
    command -v "$1" >/dev/null 2>&1
}

# Get command version (best effort)
get_command_version() {
    local cmd="$1" flag="${2:---version}"
    vibe_has "$cmd" && "$cmd" "$flag" 2>&1 | head -1 || echo ""
}

# Require multiple commands or die
vibe_require() {
    local miss=()
    for c in "$@"; do vibe_has "$c" || miss+=("$c"); done
    ((${#miss[@]}==0)) || vibe_die "Missing commands: ${miss[*]}"
}

# Find command in PATH or common locations
vibe_find_cmd() {
    local cmd="$1"
    command -v "$cmd" 2>/dev/null && return 0
    for p in /opt/homebrew/bin/$cmd /usr/local/bin/$cmd /usr/bin/$cmd; do
        [[ -x "$p" ]] && { echo "$p"; return 0; }
    done
    return 1
}

# Die with error message
vibe_die() { echo "${RED}✗ $*${NC}" >&2; return 1; }
