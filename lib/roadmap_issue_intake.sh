#!/usr/bin/env zsh
# lib/roadmap_issue_intake.sh - repo issue intake helpers for roadmap sync

_vibe_roadmap_fetch_candidate_repo_issues() {
    local repo="$1"
    gh issue list --repo "$repo" --state open --label vibe-task --limit 1000 --json id,number,title,body,url || {
        vibe_die "Failed to list vibe-task issues for repo '$repo'"
        return 1
    }
}

_vibe_roadmap_fetch_candidate_repo_prs() {
    local repo="$1"
    gh pr list --repo "$repo" --state merged --limit 1000 --json id,number,title,body,url || {
        vibe_die "Failed to list merged PRs for repo '$repo'"
        return 1
    }
}

_vibe_roadmap_sync_issue_intake_candidates() {
    local common_dir="$1" repo="$2" project_id="$3" roadmap_file candidate_list_json candidate_issue_json issue_id issue_number issue_ref issue_url added_count=0
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"

    # Intake Issues (always enabled)
    candidate_list_json="$(_vibe_roadmap_fetch_candidate_repo_issues "$repo")" || return 1
    _vibe_roadmap_process_intake_candidates "$roadmap_file" "$project_id" "$candidate_list_json" "gh" "$repo" || return 1

    # Intake merged PRs (opt-in via VIBE_ROADMAP_SYNC_INTAKE_PRS)
    local intake_prs_flag="${VIBE_ROADMAP_SYNC_INTAKE_PRS:-}"
    if [[ "$intake_prs_flag" == "1" || "$intake_prs_flag" == "true" ]]; then
        candidate_list_json="$(_vibe_roadmap_fetch_candidate_repo_prs "$repo")" || return 1
        _vibe_roadmap_process_intake_candidates "$roadmap_file" "$project_id" "$candidate_list_json" "gh" "$repo" || return 1
    fi
}

_vibe_roadmap_process_intake_candidates() {
    local roadmap_file="$1" project_id="$2" candidate_list_json="$3" prefix="$4" repo="$5"
    local candidate_json id number url ref alt_ref

    while IFS= read -r candidate_json; do
        [[ -n "$candidate_json" ]] || continue
        id="$(printf '%s' "$candidate_json" | jq -r '.id // empty')"
        number="$(printf '%s' "$candidate_json" | jq -r '.number // empty')"
        url="$(printf '%s' "$candidate_json" | jq -r '.url // empty')"
        [[ -n "$id" && -n "$number" ]] || continue
        ref="${prefix}-${number}"
        alt_ref="${prefix}:${repo}#${number}"

        if jq -e \
          --arg ref "$ref" \
          --arg alt_ref "$alt_ref" \
          --arg url "$url" \
          '.items[]? | select(((.issue_refs // []) | index($ref)) != null or ((.issue_refs // []) | index($alt_ref)) != null or ((.source_refs // []) | index($url)) != null)' \
          "$roadmap_file" >/dev/null; then
            # Even if it exists as its own item, or is being skipped, we check if it links to another issue
            # to establish the bridge.
            _vibe_roadmap_bridge_pr_links "$roadmap_file" "$candidate_json" "$repo"
            continue
        fi

        _vibe_roadmap_add_project_item_from_content "$project_id" "$id" >/dev/null || return 1
        added_count=$((added_count + 1))
        _vibe_roadmap_bridge_pr_links "$roadmap_file" "$candidate_json" "$repo"
    done < <(printf '%s' "$candidate_list_json" | jq -c '.[]?')

    echo "Added $added_count vibe-task issue candidates into GitHub Project."
}

_vibe_roadmap_bridge_pr_links() {
    local roadmap_file="$1" candidate_json="$2" repo="$3"
    local title body url pr_ref pr_alt_ref linked_issues issue_num issue_ref issue_alt_ref
    
    url="$(printf '%s' "$candidate_json" | jq -r '.url // empty')"
    [[ "$url" == *"/pull/"* ]] || return 0
    
    title="$(printf '%s' "$candidate_json" | jq -r '.title // empty')"
    body="$(printf '%s' "$candidate_json" | jq -r '.body // empty')"
    number="$(printf '%s' "$candidate_json" | jq -r '.number // empty')"
    pr_ref="gh-${number}"
    pr_alt_ref="gh:${repo}#${number}"

    # Extract issue numbers from "Fixes #123", "Closes #123", etc.
    linked_issues=$(printf '%s\n%s' "$title" "$body" | grep -oEi "(fixes|closes|resolves) #[0-9]+" | grep -oEi "#[0-9]+" | tr -d '#' || true)
    
    [[ -n "$linked_issues" ]] || return 0
    
    local tmp; tmp="$(mktemp)" || return 1
    cp "$roadmap_file" "$tmp"

    while read -r issue_num; do
        [[ -n "$issue_num" ]] || continue
        issue_ref="gh-${issue_num}"
        issue_alt_ref="gh:${repo}#${issue_num}"
        
        # Update the existing issue item to include this PR in its refs
        jq --arg issue_ref "$issue_ref" \
           --arg issue_alt_ref "$issue_alt_ref" \
           --arg pr_url "$url" \
           --arg pr_ref "$pr_ref" \
           --arg pr_alt_ref "$pr_alt_ref" \
           '(.items[] | select(((.issue_refs // []) | index($issue_ref)) != null or ((.issue_refs // []) | index($issue_alt_ref)) != null)) |= (
              .source_refs = (((.source_refs // []) + [$pr_url]) | unique)
              | .issue_refs = (((.issue_refs // []) + [$pr_ref, $pr_alt_ref]) | unique)
              | .updated_at = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
           )' "$tmp" > "${tmp}.new" && mv "${tmp}.new" "$tmp"
    done <<< "$linked_issues"
    
    mv "$tmp" "$roadmap_file"
}
