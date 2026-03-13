#!/usr/bin/env zsh
# lib/check_pr_status.sh - PR status helpers for vibe check

_check_gh_available() {
    if ! vibe_has gh; then
        return 1
    fi

    if ! gh auth status >/dev/null 2>&1; then
        return 1
    fi

    return 0
}

_get_merged_prs() {
    local limit="${1:-10}"
    gh pr list --state merged --limit "$limit" --json number,headRefName,title,mergedAt 2>/dev/null
}

_get_in_progress_tasks() {
    local registry_file="$1"
    jq -r '.tasks[] | select(.status == "in_progress") | @json' "$registry_file" 2>/dev/null
}
