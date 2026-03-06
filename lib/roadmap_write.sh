#!/usr/bin/env zsh
# lib/roadmap_write.sh - Write operations for Roadmap module

# Valid roadmap issue statuses
_vibe_roadmap_valid_states() { echo "p0 current next deferred rejected"; }

_vibe_roadmap_check_state() {
    local input_state="$1"
    for valid in $(_vibe_roadmap_valid_states); do
        [[ "$input_state" == "$valid" ]] && return 0
    done
    return 1
}

_vibe_roadmap_init() {
    local common_dir="$1" registry_file="$common_dir/vibe/registry.json"
    if ! jq -e '.roadmap' "$registry_file" >/dev/null 2>&1; then
        jq '. + {roadmap: {version_goal: null, current_version: "v0.0", issues: []}}' "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"
    fi
}

_vibe_roadmap_set_version_goal() {
    local common_dir="$1" version_goal="$2" registry_file="$common_dir/vibe/registry.json"
    _vibe_roadmap_init "$common_dir"
    jq --arg goal "$version_goal" '.roadmap.version_goal = $goal' "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"
    echo "Version goal set to: $version_goal"
}

_vibe_roadmap_classify() {
    local common_dir="$1" issue_id="$2" issue_state="$3" registry_file="$common_dir/vibe/registry.json"

    if ! _vibe_roadmap_check_state "$issue_state"; then
        echo "Error: Invalid state '$issue_state'. Valid states: $(_vibe_roadmap_valid_states)"
        return 1
    fi
    _vibe_roadmap_init "$common_dir"

    local exists
    exists="$(jq --arg id "$issue_id" '[.roadmap.issues[]? | select(.id == $id)] | length' "$registry_file")"

    if [[ "$exists" == "0" ]]; then
        echo "Issue $issue_id not found in roadmap. Adding it..."
        jq --arg id "$issue_id" --arg s "$issue_state" \
            '.roadmap.issues += [{id: $id, status: $s, added_at: (now | strftime("%Y-%m-%d"))}]' \
            "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"
    else
        jq --arg id "$issue_id" --arg s "$issue_state" \
            '(.roadmap.issues[]? | select(.id == $id) | .status) = $s' \
            "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"
    fi
    echo "Issue $issue_id classified as: $issue_state"
}

_vibe_roadmap_sync_github() {
    local common_dir="$1" repo="$2" label="${3:-vibe-task}" registry_file="$common_dir/vibe/registry.json"
    _vibe_roadmap_init "$common_dir"

    echo "Syncing GitHub issues from $repo with label '$label'..."

    local issues_json
    issues_json="$(gh issue list --repo "$repo" --label "$label" --state open --json number,title 2>/dev/null)" || {
        echo "Failed to fetch issues from GitHub. Make sure gh is authenticated."
        return 1
    }

    local issue_count
    issue_count="$(echo "${issues_json}" | jq 'length')"
    if [[ "$issue_count" == "0" ]]; then
        echo "No issues found with label '$label' in $repo"
        return 0
    fi

    local new_issues_json
    new_issues_json="$(echo "${issues_json}" | jq --arg repo "$repo" --arg state "deferred" '[.[] | {id: ("gh-" + (.number | tostring)), repo: $repo, issue_number: .number, title: .title, status: $state, added_at: (now | strftime("%Y-%m-%d"))}]')"

    # Merge with existing issues (P1 fix: remove extra array wrapper)
    local merged_issues
    merged_issues="$(jq --argjson new "$new_issues_json" '(.roadmap.issues // []) + $new | unique_by(.id) | .[:100]' "$registry_file")"

    # Get current roadmap fields (P2 fix: preserve null for version_goal)
    local version_goal_json current_version
    version_goal_json="$(jq -c '.roadmap.version_goal // null' "$registry_file")"
    current_version="$(jq -r '.roadmap.current_version // "v0.0"' "$registry_file")"

    # Use --argjson to preserve null, otherwise null becomes string "null"
    jq --argjson vg "$version_goal_json" --arg cv "$current_version" --argjson issues "$merged_issues" \
        '.roadmap = {version_goal: $vg, current_version: $cv, issues: $issues}' \
        "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"

    echo "Sync complete. Added $issue_count issues (state: deferred - use 'vibe roadmap classify' to categorize)."
}

_vibe_roadmap_assign() {
    local common_dir="$1" version_goal="$2"
    if [[ -z "$version_goal" ]]; then
        echo "Error: version_goal required"
        return 1
    fi
    _vibe_roadmap_set_version_goal "$common_dir" "$version_goal"
}
