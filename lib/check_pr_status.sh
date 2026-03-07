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

_check_pr_merged_status() {
    local registry_file="$1"
    local worktrees_file="$2"
    local -a merged_pr_branches
    local -a uncertain_tasks

    local merged_prs
    merged_prs=$(_get_merged_prs 50)

    if [[ -z "$merged_prs" ]] || [[ "$merged_prs" == "[]" ]]; then
        return 0
    fi

    while IFS= read -r branch; do
        merged_pr_branches+=("$branch")
    done < <(echo "$merged_prs" | jq -r '.[].headRefName')

    while IFS= read -r task_json; do
        local task_id assigned_worktree branch
        task_id=$(echo "$task_json" | jq -r '.task_id')
        assigned_worktree=$(echo "$task_json" | jq -r '.assigned_worktree // empty')

        [[ -z "$assigned_worktree" ]] && continue
        branch=$(jq -r --arg wt "$assigned_worktree" '.worktrees[]? | select(.worktree_name == $wt) | .branch // empty' "$worktrees_file" 2>/dev/null)
        [[ -z "$branch" ]] && continue

        for merged_branch in "${merged_pr_branches[@]}"; do
            if [[ "$branch" == "$merged_branch" ]]; then
                uncertain_tasks+=("$task_id|$branch")
                break
            fi
        done
    done < <(_get_in_progress_tasks "$registry_file")

    for task_info in "${uncertain_tasks[@]}"; do
        echo "$task_info"
    done
}
