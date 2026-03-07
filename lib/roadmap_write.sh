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
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    if [[ ! -f "$roadmap_file" ]]; then
        mkdir -p "$(dirname "$roadmap_file")" || return 1
        jq -n '{schema_version: "v2", version_goal: null, items: []}' > "$roadmap_file" || return 1
    fi
}

_vibe_roadmap_set_version_goal() {
    local common_dir="$1" version_goal="$2" roadmap_file
    _vibe_roadmap_init "$common_dir"
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq --arg goal "$version_goal" '.version_goal = $goal' "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
    echo "Version goal set to: $version_goal"
}

_vibe_roadmap_classify() {
    local common_dir="$1" issue_id="$2" issue_state="$3" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"

    if ! _vibe_roadmap_check_state "$issue_state"; then
        echo "Error: Invalid state '$issue_state'. Valid states: $(_vibe_roadmap_valid_states)"
        return 1
    fi
    _vibe_roadmap_init "$common_dir"

    local exists
    exists="$(jq --arg id "$issue_id" '[.items[]? | select(.roadmap_item_id == $id)] | length' "$roadmap_file")"

    if [[ "$exists" == "0" ]]; then
        echo "Issue $issue_id not found in roadmap. Adding it..."
        jq --arg id "$issue_id" --arg s "$issue_state" \
            '.items += [{roadmap_item_id: $id, title: $id, description: null, status: $s, source_type: "local", source_refs: [], issue_refs: [], linked_task_ids: [], created_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")), updated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z"))}]' \
            "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
    else
        jq --arg id "$issue_id" --arg s "$issue_state" \
            '(.items[]? | select(.roadmap_item_id == $id) | .status) = $s
             | (.items[]? | select(.roadmap_item_id == $id) | .updated_at) = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))' \
            "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
    fi
    echo "Issue $issue_id classified as: $issue_state"
}

_vibe_roadmap_sync_github() {
    local common_dir="$1" repo="$2" label="${3:-vibe-task}" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
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
    new_issues_json="$(echo "${issues_json}" | jq --arg repo "$repo" --arg state "deferred" '[.[] | {roadmap_item_id: ("gh-" + (.number | tostring)), title: .title, description: null, status: $state, source_type: "github", source_refs: [("gh:" + $repo + "#" + (.number | tostring))], issue_refs: [("gh:" + $repo + "#" + (.number | tostring))], linked_task_ids: [], created_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")), updated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z"))}]')"

    local merged_issues
    merged_issues="$(jq --argjson new "$new_issues_json" '(.items // []) + $new | unique_by(.roadmap_item_id) | .[:100]' "$roadmap_file")"

    jq --argjson issues "$merged_issues" '.items = $issues' \
        "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"

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
