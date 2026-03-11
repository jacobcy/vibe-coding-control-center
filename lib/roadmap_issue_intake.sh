#!/usr/bin/env zsh
# lib/roadmap_issue_intake.sh - repo issue intake helpers for roadmap sync

_vibe_roadmap_fetch_candidate_repo_issues() {
    local repo="$1"
    gh issue list --repo "$repo" --state open --label vibe-task --json id,number,title,body,url 2>/dev/null
}

_vibe_roadmap_sync_issue_intake_candidates() {
    local common_dir="$1" repo="$2" project_id="$3" roadmap_file candidate_json issue_id issue_number issue_ref issue_url
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    candidate_json="$(_vibe_roadmap_fetch_candidate_repo_issues "$repo")" || return 1

    while IFS= read -r candidate_json; do
        [[ -n "$candidate_json" ]] || continue
        issue_id="$(printf '%s' "$candidate_json" | jq -r '.id // empty')"
        issue_number="$(printf '%s' "$candidate_json" | jq -r '.number // empty')"
        issue_url="$(printf '%s' "$candidate_json" | jq -r '.url // empty')"
        [[ -n "$issue_id" && -n "$issue_number" ]] || continue
        issue_ref="gh-${issue_number}"

        if jq -e \
          --arg issue_ref "$issue_ref" \
          --arg issue_url "$issue_url" \
          '.items[]? | select(((.issue_refs // []) | index($issue_ref)) != null or ((.source_refs // []) | index($issue_url)) != null)' \
          "$roadmap_file" >/dev/null; then
            continue
        fi

        _vibe_roadmap_add_project_item_from_content "$project_id" "$issue_id" >/dev/null || return 1
    done < <(printf '%s' "$candidate_json" | jq -c '.[]?')
}
