#!/usr/bin/env zsh
# lib/roadmap_write.sh - Write operations for Roadmap module
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_store.sh" ]] && source "$VIBE_LIB/roadmap_store.sh"
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_project_sync.sh" ]] && source "$VIBE_LIB/roadmap_project_sync.sh"

_vibe_roadmap_add() {
    local common_dir="$1" title="$2" roadmap_file item_id item_json project_id remote_item_id
    [[ -n "$title" ]] || { echo "Error: title required"; return 1; }

    _vibe_roadmap_init "$common_dir"
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    project_id="$(_vibe_roadmap_project_id "$common_dir")" || return 1
    [[ -n "$project_id" ]] || { echo "Error: roadmap.json project_id required before roadmap add"; return 1; }
    remote_item_id="$(_vibe_roadmap_create_github_draft_issue "$project_id" "$title")" || return 1
    item_id="$(_vibe_roadmap_next_item_id "$common_dir" "$title")" || return 1
    item_json="$(_vibe_roadmap_new_item "$item_id" "$title" "local" '[]' '[]')" || return 1

    jq --arg remote_item_id "$remote_item_id" \
       --argjson item "$item_json" \
        '.items += [($item | .github_project_item_id = $remote_item_id)]' \
        "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"

    echo "Roadmap item added: $item_id"
    echo "Title: $title"
    echo "GitHub Project item created: $remote_item_id"
}

_vibe_roadmap_set_version_goal() {
    local common_dir="$1" version_goal="$2" roadmap_file
    _vibe_roadmap_init "$common_dir"
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq --arg goal "$version_goal" '.version_goal = $goal' "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
    echo "Version goal set to: $version_goal"
    echo "Note: version goal is currently a compatibility text anchor for the planning window."
}

_vibe_roadmap_classify() {
    local common_dir="$1" issue_id="$2" issue_state="$3" roadmap_file title
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"

    if ! _vibe_roadmap_check_state "$issue_state"; then
        echo "Error: Invalid state '$issue_state'. Valid states: $(_vibe_roadmap_valid_states)"
        return 1
    fi
    _vibe_roadmap_init "$common_dir"

    local exists
    exists="$(jq --arg id "$issue_id" '[.items[]? | select(.roadmap_item_id == $id)] | length' "$roadmap_file")"

    if [[ "$exists" == "0" ]]; then
        echo "Error: Roadmap item '$issue_id' not found. Add or sync it before classifying."
        return 1
    fi
    title="$(jq -r --arg id "$issue_id" '.items[]? | select(.roadmap_item_id == $id) | .title // empty' "$roadmap_file" | head -n 1)"

    jq --arg id "$issue_id" --arg s "$issue_state" \
        '(.items[]? | select(.roadmap_item_id == $id) | .status) = $s
         | (.items[]? | select(.roadmap_item_id == $id) | .updated_at) = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))' \
        "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"

    echo "Roadmap item $issue_id (${title:-untitled}) classified as: $issue_state"
}


_vibe_roadmap_assign() {
    local common_dir="$1" version_goal="$2"
    if [[ -z "$version_goal" ]]; then
        echo "Error: version_goal required"
        return 1
    fi
    _vibe_roadmap_set_version_goal "$common_dir" "$version_goal"
}
