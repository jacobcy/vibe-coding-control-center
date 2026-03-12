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
    local common_dir="$1" repo="$2" project_id="$3" roadmap_file candidate_list_json
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
            continue
        fi

        _vibe_roadmap_add_project_item_from_content "$project_id" "$id" >/dev/null || return 1
    done < <(printf '%s' "$candidate_list_json" | jq -c '.[]?')
}
