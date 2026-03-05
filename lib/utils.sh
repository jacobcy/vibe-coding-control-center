#!/usr/bin/env zsh
# v2/lib/utils.sh - Minimalist Utilities for Vibe 2.0
# Target: ~60 lines | No dead code

# ── Colors ──────────────────────────────────────────────
# Use printf to ensure literal escape characters are assigned
export RED=$(printf '\033[0;31m')
export GREEN=$(printf '\033[0;32m')
export YELLOW=$(printf '\033[1;33m')
export BLUE=$(printf '\033[0;34m')
export CYAN=$(printf '\033[0;36m')
export BOLD=$(printf '\033[1m')
export NC=$(printf '\033[0m')

# ── Logging ─────────────────────────────────────────────
log_info()    { echo "${GREEN}ℹ $1${NC}"; }
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

# Delete local branch with safe (-d) or force (-D) mode.
vibe_delete_local_branch() {
    local branch="$1" mode="${2:-safe}" flag="-d"
    [[ -n "$branch" ]] || return 1
    [[ "$mode" == "force" ]] && flag="-D"
    if git branch "$flag" "$branch" >/dev/null 2>&1; then
        log_step "Deleted local branch: $branch"
        return 0
    fi
    log_warn "Failed to delete local branch: $branch"
    return 1
}

# Delete remote branch from origin.
vibe_delete_remote_branch() {
    local branch="$1"
    [[ -n "$branch" ]] || return 1
    if git push origin --delete "$branch" >/dev/null 2>&1; then
        log_step "Deleted remote branch: $branch"
        return 0
    fi
    log_warn "Failed to delete remote branch: $branch"
    return 1
}

# Print error and return failure
vibe_die() {
    echo "${RED}✗ $*${NC}" >&2
    return 1
}
