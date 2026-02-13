#!/bin/bash

# gh-ops.sh
# Core GitHub operations for Vibe Agent Workflows

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }

ensure_gh_auth() {
    if ! gh auth status >/dev/null 2>&1; then
        echo -e "${RED}[ERROR]${NC} Not authenticated with GitHub CLI. Run 'gh auth login'."
        return 1
    fi
}

# --- PR Operations ---

pr_create() {
    ensure_gh_auth || return 1
    
    current_branch=$(git branch --show-current)
    log_info "Preparing to create PR for branch: $current_branch"
    
    # Basic analysis
    commits=$(git log origin/main..HEAD --oneline | wc -l)
    log_info "Changes contain $commits commits."
    
    echo "DRAFTING PR..."
    echo "Title tip: feat/fix/docs: <description>"
    read -p "PR Title: " title
    
    echo "Body tip: What changed? Why? Testing?"
    read -p "PR Body: " body
    
    log_info "Pushing branch..."
    git push -u origin HEAD
    
    log_info "Creating Pull Request..."
    gh pr create --title "$title" --body "$body" --web
}

pr_review_list() {
    ensure_gh_auth || return 1
    log_info "Fetching Open Pull Requests..."
    gh pr list
}

# --- Issue Operations ---

issue_list() {
    ensure_gh_auth || return 1
    log_info "Fetching Assigned Issues..."
    gh issue list --assignee "@me"
}

issue_create() {
    ensure_gh_auth || return 1
    
    echo "CREATE ISSUE"
    read -p "Title: " title
    read -p "Body: " body
    
    gh issue create --title "$title" --body "$body"
    log_success "Issue created."
}

issue_resolve() {
    ensure_gh_auth || return 1
    
    # If issue number not provided, list them first
    if [ -z "$1" ]; then
        issue_list
        read -p "Enter Issue Number to resolve: " issue_num
    else
        issue_num=$1
    fi
    
    if [ -z "$issue_num" ]; then
        echo "Cancelled."
        return 0
    fi
    
    echo "Resolving Issue #$issue_num"
    read -p "Closing comment: " comment
    
    gh issue comment "$issue_num" --body "$comment"
    gh issue close "$issue_num"
    
    log_success "Issue #$issue_num closed."
}
