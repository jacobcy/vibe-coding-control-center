#!/usr/bin/env zsh
# lib/roadmap_write.sh - Write operations for Roadmap module

# Valid roadmap item statuses
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
        jq -n '{schema_version: "v2", project_id: null, milestone: null, version_goal: null, items: []}' > "$roadmap_file" || return 1
    fi
}

_vibe_roadmap_slugify() {
    local raw="$1" slug
    slug="$(print -r -- "$raw" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//')"
    [[ -n "$slug" ]] || slug="roadmap-item"
    print -r -- "$slug"
}

_vibe_roadmap_new_item() {
    local item_id="$1" title="$2" source_type="$3" source_refs_json="$4" issue_refs_json="$5"
    jq -nc \
        --arg id "$item_id" \
        --arg title "$title" \
        --arg source_type "$source_type" \
        --argjson source_refs "$source_refs_json" \
        --argjson issue_refs "$issue_refs_json" \
        '{
            roadmap_item_id: $id,
            title: $title,
            description: null,
            status: "deferred",
            source_type: $source_type,
            source_refs: $source_refs,
            issue_refs: $issue_refs,
            linked_task_ids: [],
            github_project_item_id: null,
            content_type: "draft_issue",
            execution_record_id: null,
            spec_standard: "none",
            spec_ref: null,
            created_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
            updated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
        }'
}

_vibe_roadmap_next_item_id() {
    local common_dir="$1" title="$2" roadmap_file date_part slug base candidate suffix exists
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    date_part="$(date +%F)"
    slug="$(_vibe_roadmap_slugify "$title")"
    base="rm-${date_part}-${slug}"
    candidate="$base"
    suffix=2

    while true; do
        exists="$(jq --arg id "$candidate" '[.items[]? | select(.roadmap_item_id == $id)] | length' "$roadmap_file")"
        [[ "$exists" == "0" ]] && break
        candidate="${base}-${suffix}"
        suffix=$((suffix + 1))
    done

    print -r -- "$candidate"
}

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
    echo "GitHub Project item created: $remote_item_id"
}

_vibe_roadmap_create_github_draft_issue() {
    local project_id="$1" title="$2" response item_id
    response="$(gh api graphql -f query='
      mutation($project: ID!, $title: String!, $body: String!) {
        addProjectV2DraftIssue(input: {projectId: $project, title: $title, body: $body}) {
          projectItem {
            id
          }
        }
      }' -F project="$project_id" -f title="$title" -f body="" 2>/dev/null)" || {
        echo "Failed to create GitHub Project draft item. Make sure gh is authenticated and project_id is valid."
        return 1
    }
    item_id="$(echo "$response" | jq -r '.data.addProjectV2DraftIssue.projectItem.id // empty')"
    [[ -n "$item_id" ]] || {
        echo "Failed to parse GitHub Project item id from GraphQL response."
        return 1
    }
    print -r -- "$item_id"
}

_vibe_roadmap_sync_github() {
    local common_dir="$1" repo="$2" project_id="$3" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_init "$common_dir"

    [[ -n "$project_id" ]] || {
        echo "Error: roadmap.json project_id required for GitHub Project sync"
        return 1
    }

    echo "GitHub Project sync contract validated for $repo (project_id: $project_id)."
    echo "Project mirror refresh is not implemented yet; current shell contract now targets GitHub Project items instead of repo issue import."
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
        echo "Error: Roadmap item '$issue_id' not found. Add or sync it before classifying."
        return 1
    fi

    jq --arg id "$issue_id" --arg s "$issue_state" \
        '(.items[]? | select(.roadmap_item_id == $id) | .status) = $s
         | (.items[]? | select(.roadmap_item_id == $id) | .updated_at) = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))' \
        "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"

    echo "Roadmap item $issue_id classified as: $issue_state"
}


_vibe_roadmap_assign() {
    local common_dir="$1" version_goal="$2"
    if [[ -z "$version_goal" ]]; then
        echo "Error: version_goal required"
        return 1
    fi
    _vibe_roadmap_set_version_goal "$common_dir" "$version_goal"
}
