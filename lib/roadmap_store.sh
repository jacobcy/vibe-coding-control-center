#!/usr/bin/env zsh
# lib/roadmap_store.sh - Shared storage/model helpers for Roadmap module

_vibe_roadmap_require_file() {
    if [[ -f "$1" ]]; then
        return 0
    fi
    vibe_die "Missing $2: $1"
}

_vibe_roadmap_common_dir() {
    vibe_git_dir
}

_vibe_roadmap_file() {
    local common_dir="$1"
    echo "$common_dir/vibe/roadmap.json"
}

_vibe_roadmap_project_id() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1
    jq -r '.project_id // empty' "$roadmap_file"
}

_vibe_roadmap_current_repo() {
    local remote_url repo_path
    remote_url="$(git remote get-url origin 2>/dev/null || git config --get remote.origin.url 2>/dev/null || true)"
    [[ -n "$remote_url" ]] || { vibe_die "Unable to infer current repo from git remote origin"; return 1; }

    case "$remote_url" in
        git@github.com:*)
            repo_path="${remote_url#git@github.com:}"
            ;;
        ssh://git@github.com/*)
            repo_path="${remote_url#ssh://git@github.com/}"
            ;;
        https://github.com/*)
            repo_path="${remote_url#https://github.com/}"
            ;;
        http://github.com/*)
            repo_path="${remote_url#http://github.com/}"
            ;;
        *)
            vibe_die "Unsupported GitHub remote URL: $remote_url"
            return 1
            ;;
    esac

    repo_path="${repo_path%.git}"
    [[ "$repo_path" == */* ]] || { vibe_die "Unable to normalize repo from remote origin: $remote_url"; return 1; }
    print -r -- "$repo_path"
}

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
            depends_on_item_ids: [],
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

_vibe_roadmap_get_version_goal() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq -r '.version_goal // empty' "$roadmap_file"
}
