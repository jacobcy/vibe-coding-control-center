#!/usr/bin/env zsh

_vibe_task_roadmap_file() {
    echo "$1/vibe/roadmap.json"
}

_vibe_task_validate_roadmap_items() {
    local common_dir="$1" roadmap_item_ids_json="$2" roadmap_file missing_ids first_missing
    [[ "${roadmap_item_ids_json:-[]}" == "[]" ]] && return 0
    roadmap_file="$(_vibe_task_roadmap_file "$common_dir")"
    [[ -f "$roadmap_file" ]] || { vibe_die "Missing roadmap.json: $roadmap_file"; return 1; }
    jq empty "$roadmap_file" >/dev/null 2>&1 || { vibe_die "Invalid roadmap.json: $roadmap_file"; return 1; }
    missing_ids="$(jq -nr --argjson roadmap_item_ids "$roadmap_item_ids_json" --slurpfile roadmap "$roadmap_file" '
      ($roadmap[0].items // [] | map(.roadmap_item_id)) as $existing
      | $roadmap_item_ids[]
      | . as $target
      | select($existing | index($target) | not)
    ')" || { vibe_die "Invalid roadmap.json: $roadmap_file"; return 1; }

    if [[ -n "$missing_ids" ]]; then
        first_missing="$(printf '%s\n' "$missing_ids" | sed -n '1p')"
        vibe_die "Roadmap item not found: $first_missing"
        return 1
    fi
}

_vibe_task_sync_roadmap_links() {
    local common_dir="$1" task_id="$2" roadmap_item_ids_json="$3" now="$4" roadmap_file tmp
    [[ "${roadmap_item_ids_json:-[]}" == "[]" ]] && return 0
    roadmap_file="$(_vibe_task_roadmap_file "$common_dir")"
    [[ -f "$roadmap_file" ]] || { vibe_die "Missing roadmap.json: $roadmap_file"; return 1; }
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg now "$now" --argjson roadmap_item_ids "$roadmap_item_ids_json" '
      .items |= map(
        . as $item
        | if ($roadmap_item_ids | index($item.roadmap_item_id)) != null then
          .linked_task_ids = (((.linked_task_ids // []) + [$task_id]) | unique)
          | .updated_at = $now
        else . end
      )
    ' "$roadmap_file" > "$tmp" && mv "$tmp" "$roadmap_file"
}

_vibe_task_require_plan_binding_for_add() {
    local spec_standard="$1" spec_ref="$2"
    if [[ "$spec_standard" == "none" || -z "$spec_ref" ]]; then
        vibe_die $'Task creation requires a plan binding.\n\n  选项 1: 从已有 plan 创建（推荐）\n    vibe task add <title> --issue <issue> \\\n      --spec-standard openspec \\\n      --spec-ref docs/plans/example.md\n\n  选项 2: 从 roadmap item 创建\n    vibe roadmap add <title> --issue <issue>\n    vibe task add <title> --spec-standard openspec --spec-ref <plan-path>'
        return 1
    fi
}
