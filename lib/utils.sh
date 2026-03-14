#!/usr/bin/env zsh

export RED=$(printf '\033[0;31m')
export GREEN=$(printf '\033[0;32m')
export YELLOW=$(printf '\033[1;33m')
export BLUE=$(printf '\033[0;34m')
export CYAN=$(printf '\033[0;36m')
export BOLD=$(printf '\033[1m')
export NC=$(printf '\033[0m')

log_info()    { echo "${GREEN}ℹ $1${NC}"; }
log_warn()    { echo "${YELLOW}! $1${NC}" >&2; }
log_error()   { echo "${RED}✗ $1${NC}" >&2; }
log_step()    { echo "${BLUE}>> $1...${NC}"; }
log_success() { echo "${GREEN}★ $1${NC}"; }

confirm_action() {
    local prompt="${1:-Are you sure?}" response
    if [[ "${VIBE_ASSUME_YES:-}" == "1" ]]; then
        return 0
    fi
    if [[ -n "${VIBE_ALLOW_INTERACTIVE:-}" && -t 0 ]]; then
        echo -n "${YELLOW}? $prompt [y/N]: ${NC}"
        read -r response
        [[ "$response" =~ ^[yY](es)?$ ]]
    else
        vibe_die "Interactive confirmation blocked: $prompt (set VIBE_ASSUME_YES=1 or pass --yes)."
    fi
}

get_vibe_version() { local vfile="${VIBE_ROOT:-$(cd "$(dirname "${(%):-%x}")/.." && pwd)}/VERSION"; [[ -f "$vfile" ]] && cat "$vfile" || echo "2.0.0-dev"; }

vibe_has() { command -v "$1" >/dev/null 2>&1; }

vibe_require() {
    local miss=() c; for c in "$@"; do vibe_has "$c" || miss+=("$c"); done
    ((${#miss[@]} == 0)) || vibe_die "Missing commands: ${miss[*]}"
}

vibe_find_cmd() {
    local cmd="$1" p
    command -v "$cmd" 2>/dev/null && return 0
    for p in "/opt/homebrew/bin/$cmd" "/usr/local/bin/$cmd" "/usr/bin/$cmd"; do [[ -x "$p" ]] && { echo "$p"; return 0; }; done
    return 1
}

vibe_delete_local_branch() {
    local branch="$1" mode="${2:-safe}" flag="-d"
    [[ -n "$branch" ]] || return 1
    [[ "$mode" == "force" ]] && flag="-D"
    git branch "$flag" "$branch" >/dev/null 2>&1 && { log_step "Deleted local branch: $branch"; return 0; }
    log_warn "Failed to delete local branch: $branch"; return 1
}

vibe_delete_remote_branch() {
    local branch="$1"
    [[ -n "$branch" ]] || return 1
    git push origin --delete "$branch" >/dev/null 2>&1 && { log_step "Deleted remote branch: $branch"; return 0; }
    log_warn "Failed to delete remote branch: $branch"; return 1
}

# Check if a branch is occupied by any worktree (excluding current worktree)
# Returns 0 if occupied, 1 if not occupied
vibe_is_branch_occupied_by_worktree() {
    local branch="$1"
    [[ -n "$branch" ]] || return 1

    local current_worktree current_branch occupied_worktrees

    # Get current worktree path
    current_worktree="$(git rev-parse --show-toplevel 2>/dev/null)" || return 1

    # Get current branch in this worktree
    current_branch="$(git branch --show-current 2>/dev/null)" || true

    # If checking the current branch, it's not considered "occupied" by this worktree
    if [[ "$branch" == "$current_branch" ]]; then
        # Check if any OTHER worktree has this branch checked out
        # Use -B2 to get the worktree line before the branch line
        occupied_worktrees="$(git worktree list --porcelain 2>/dev/null | grep -B2 "branch refs/heads/$branch$" | grep "^worktree" | grep -v "$current_worktree" || true)"
    else
        # Check if ANY worktree has this branch checked out
        occupied_worktrees="$(git worktree list --porcelain 2>/dev/null | grep -B2 "branch refs/heads/$branch$" | grep "^worktree" || true)"
    fi

    [[ -n "$occupied_worktrees" ]]
}

vibe_die() { echo "${RED}✗ $*${NC}" >&2; return 1; }

# Worktree-aware git directory resolution with caching
# Returns the common git directory (shared across worktrees)
# Cached in VIBE_GIT_DIR environment variable for session performance
vibe_git_dir() {
    if [[ -n "${VIBE_GIT_DIR:-}" ]]; then
        echo "$VIBE_GIT_DIR"
        return 0
    fi

    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        vibe_die "Not in a git repository"
        return 1
    fi

    local git_dir
    git_dir="$(git rev-parse --git-common-dir 2>/dev/null)" || {
        vibe_die "Failed to resolve git directory"
        return 1
    }

    # Cache for session-level performance
    export VIBE_GIT_DIR="$git_dir"
    echo "$git_dir"
}
