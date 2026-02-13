#!/bin/bash

# git-ops.sh
# Core Git operations for Vibe Agent Workflows

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# --- Helper Functions ---

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

ensure_git_repo() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        log_error "Not a git repository."
        return 1
    fi
}

# --- Smart Commit Logic ---

smart_commit() {
    ensure_git_repo || return 1
    
    log_info "Analyzing uncommitted changes..."
    
    # Check for changes
    if [ -z "$(git status --porcelain)" ]; then
        log_warn "No changes to commit."
        return 0
    fi
    
    git status -s
    echo ""
    log_info "Entering Smart Commit Mode."
    echo "Tip: Group changes by feature/scope. Use 'git add <file>' then 'git commit'."
    echo "Type 'exit' or 'done' when finished or to stop."
    
    # Interactive loop for the user/agent
    while true; do
        if [ -z "$(git status --porcelain)" ]; then
            log_success "All changes committed!"
            break
        fi
        
        echo "---------------------------------------------------"
        git status -s
        echo "---------------------------------------------------"
        read -p "Enter command (e.g., 'git add ...', 'git commit ...', 'done'): " cmd
        
        if [[ "$cmd" == "exit" || "$cmd" == "done" ]]; then
            break
        fi
        
        eval "$cmd"
    done
}

# --- Sync Branches Logic ---

sync_all() {
    ensure_git_repo || return 1
    
    current_branch=$(git branch --show-current)
    log_info "Syncing from source branch: $current_branch"
    
    # Get all worktrees
    git worktree list --porcelain | grep '^worktree' | cut -d' ' -f2 | while read -r wt_path; do
        # Get branch for this worktree
        wt_branch=$(git -C "$wt_path" branch --show-current)
        
        if [[ "$wt_branch" == "$current_branch" ]]; then
            continue
        fi
        
        log_info "Checking worktree: $wt_path ($wt_branch)"
        
        # Check divergence
        behind=$(git rev-list --count "$wt_branch".."$current_branch" 2>/dev/null || echo "0")
        
        if [[ "$behind" -gt 0 ]]; then
            echo "  -> Behind by $behind commits. Syncing..."
            
            # Perform merge in the worktree
            if git -C "$wt_path" merge "$current_branch" --no-edit; then
                log_success "  -> Synced $wt_branch"
                
                # Optional: Push if configured to auto-push
                # git -C "$wt_path" push origin "$wt_branch"
            else
                log_error "  -> Merge failed for $wt_branch. Manual resolution required in $wt_path"
            fi
        else
            echo "  -> Up to date."
        fi
    done
    
    log_success "Sync operations complete."
}
