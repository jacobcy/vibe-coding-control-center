#!/usr/bin/env zsh
# lib/roadmap_project_sync.sh - GitHub Project sync helpers for Roadmap module
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_store.sh" ]] && source "$VIBE_LIB/roadmap_store.sh"
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_issue_intake.sh" ]] && source "$VIBE_LIB/roadmap_issue_intake.sh"
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_github_api.sh" ]] && source "$VIBE_LIB/roadmap_github_api.sh"

_vibe_roadmap_import_remote_item() {
    local common_dir="$1" remote_json="$2" roadmap_file roadmap_item_id title source_type source_refs issue_refs
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    title="$(printf '%s' "$remote_json" | jq -r '.title // "Imported Project Item"')"
    source_type="$(printf '%s' "$remote_json" | jq -r '.source_type')"
    source_refs="$(printf '%s' "$remote_json" | jq -c '.source_refs // []')"
    issue_refs="$(printf '%s' "$remote_json" | jq -c '.issue_refs // []')"

    if [[ "$source_type" == "github" ]]; then
        roadmap_item_id="$(printf '%s' "$remote_json" | jq -r '"gh-" + (.remote_number | tostring)')"
    else
        roadmap_item_id="$(_vibe_roadmap_next_item_id "$common_dir" "$title")" || return 1
    fi

    jq --arg id "$roadmap_item_id" \
       --arg title "$title" \
       --arg source_type "$source_type" \
       --argjson source_refs "$source_refs" \
       --argjson issue_refs "$issue_refs" \
       --arg remote_item_id "$(printf '%s' "$remote_json" | jq -r '.github_project_item_id')" \
       --arg content_type "$(printf '%s' "$remote_json" | jq -r '.content_type')" \
       --arg description "$(printf '%s' "$remote_json" | jq -r '.description // empty')" \
       '
        .items += [{
          roadmap_item_id: $id,
          title: $title,
          description: (if $description == "" then null else $description end),
          status: "deferred",
          source_type: $source_type,
          source_refs: $source_refs,
          issue_refs: $issue_refs,
          linked_task_ids: [],
          github_project_item_id: $remote_item_id,
          content_type: $content_type,
          execution_record_id: null,
          spec_standard: "none",
          spec_ref: null,
          created_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z")),
          updated_at: (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
        }]' \
       "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
}

_vibe_roadmap_refresh_local_mirror() {
    local common_dir="$1" project_id="$2" roadmap_file remote_items remote_json refreshed_count=0 imported_count=0
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    remote_items="$(_vibe_roadmap_fetch_github_project_items "$project_id")" || return 1
    while IFS= read -r remote_json; do
        [[ -n "$remote_json" ]] || continue
        if jq -e --arg remote_id "$(printf '%s' "$remote_json" | jq -r '.github_project_item_id')" \
            '.items[]? | select(.github_project_item_id == $remote_id)' "$roadmap_file" >/dev/null; then
            jq --arg remote_id "$(printf '%s' "$remote_json" | jq -r '.github_project_item_id')" \
               --arg title "$(printf '%s' "$remote_json" | jq -r '.title // empty')" \
               --arg description "$(printf '%s' "$remote_json" | jq -r '.description // empty')" \
               --arg source_type "$(printf '%s' "$remote_json" | jq -r '.source_type')" \
               --argjson source_refs "$(printf '%s' "$remote_json" | jq -c '.source_refs')" \
               --argjson issue_refs "$(printf '%s' "$remote_json" | jq -c '.issue_refs')" \
               --arg content_type "$(printf '%s' "$remote_json" | jq -r '.content_type')" \
               '
                 (.items[] | select(.github_project_item_id == $remote_id) | .title) = $title
                 | (.items[] | select(.github_project_item_id == $remote_id) | .description) = (if $description == "" then null else $description end)
                 | (.items[] | select(.github_project_item_id == $remote_id) | .source_type) = $source_type
                 | (.items[] | select(.github_project_item_id == $remote_id) | .source_refs) = $source_refs
                 | (.items[] | select(.github_project_item_id == $remote_id) | .issue_refs) = $issue_refs
                 | (.items[] | select(.github_project_item_id == $remote_id) | .content_type) = $content_type
                 | (.items[] | select(.github_project_item_id == $remote_id) | .updated_at) = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))
               ' "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
            refreshed_count=$((refreshed_count + 1))
        else
            _vibe_roadmap_import_remote_item "$common_dir" "$remote_json" || return 1
            imported_count=$((imported_count + 1))
        fi
    done < <(print -r -- "$remote_items" | jq -c '.[]')

    echo "Refreshed $refreshed_count local roadmap mirrors from GitHub Project."
    echo "Imported $imported_count new roadmap items from GitHub Project."
}

_vibe_roadmap_sync_github() {
    local common_dir="$1" repo="$2" project_id="$3" roadmap_file
    local item_json bootstrap_result remote_item_id content_type pushed_count=0
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_init "$common_dir"

    [[ -n "$project_id" ]] || {
        echo "Error: roadmap.json project_id required for GitHub Project sync"
        return 1
    }

    while IFS= read -r item_json; do
        bootstrap_result="$(_vibe_roadmap_bootstrap_remote_item "$project_id" "$item_json")" || {
            echo "Failed to bootstrap roadmap item: $(printf '%s' "$item_json" | jq -r '.roadmap_item_id')"
            return 1
        }
        remote_item_id="${bootstrap_result%%|*}"
        content_type="${bootstrap_result##*|}"

        jq --arg rid "$(printf '%s' "$item_json" | jq -r '.roadmap_item_id')" \
           --arg remote_item_id "$remote_item_id" \
           --arg content_type "$content_type" \
           '(.items[] | select(.roadmap_item_id == $rid) | .github_project_item_id) = $remote_item_id
            | (.items[] | select(.roadmap_item_id == $rid) | .content_type) = $content_type
            | (.items[] | select(.roadmap_item_id == $rid) | .updated_at) = (now | strftime("%Y-%m-%dT%H:%M:%S%z"))' \
           "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
        pushed_count=$((pushed_count + 1))
    done < <(jq -c '.items[]? | select(.github_project_item_id == null)' "$roadmap_file")

    echo "GitHub Project bootstrap sync complete for $repo (project_id: $project_id)."
    echo "Bootstrapped $pushed_count roadmap item mirrors into GitHub Project."
    _vibe_roadmap_refresh_local_mirror "$common_dir" "$project_id" || return 1
    _vibe_roadmap_sync_issue_intake_candidates "$common_dir" "$repo" "$project_id" || return 1
    _vibe_roadmap_refresh_local_mirror "$common_dir" "$project_id" || return 1
}
