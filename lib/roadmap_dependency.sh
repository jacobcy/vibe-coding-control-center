#!/usr/bin/env zsh
# lib/roadmap_dependency.sh - Derived dependency views for roadmap items

[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/check_pr_status.sh" ]] && source "$VIBE_LIB/check_pr_status.sh"

_vibe_roadmap_merged_prs_json() {
    if [[ -n "${_VIBE_ROADMAP_MERGED_PRS_JSON:-}" ]]; then
        print -r -- "$_VIBE_ROADMAP_MERGED_PRS_JSON"
        [[ "${_VIBE_ROADMAP_MERGED_PRS_JSON_VALID:-false}" == "true" ]]
        return $?
    fi

    if _check_gh_available; then
        _VIBE_ROADMAP_MERGED_PRS_JSON="$(_get_merged_prs 1000)"
        if print -r -- "$_VIBE_ROADMAP_MERGED_PRS_JSON" | jq -e 'type == "array"' >/dev/null 2>&1; then
            _VIBE_ROADMAP_MERGED_PRS_JSON_VALID="true"
        else
            _VIBE_ROADMAP_MERGED_PRS_JSON='[]'
            _VIBE_ROADMAP_MERGED_PRS_JSON_VALID="false"
        fi
    else
        _VIBE_ROADMAP_MERGED_PRS_JSON='[]'
        _VIBE_ROADMAP_MERGED_PRS_JSON_VALID="false"
    fi

    print -r -- "$_VIBE_ROADMAP_MERGED_PRS_JSON"
    [[ "$_VIBE_ROADMAP_MERGED_PRS_JSON_VALID" == "true" ]]
}

_vibe_roadmap_has_dependency_item() {
    local roadmap_file="$1" dep_id="$2"
    jq -e --arg id "$dep_id" '.items[]? | select(.roadmap_item_id == $id)' "$roadmap_file" >/dev/null 2>&1
}

_vibe_roadmap_dependency_task_prs() {
    local registry_file="$1" dep_id="$2"
    jq -r --arg rid "$dep_id" '
        [
            .tasks[]?
            | select((.roadmap_item_ids // []) | index($rid))
            | .pr_ref // ""
            | select(. != "")
        ]
        | unique
        | .[]
    ' "$registry_file" 2>/dev/null
}

_vibe_roadmap_pr_is_merged() {
    local pr_ref="${1#\#}" merged_prs_json
    [[ -n "$pr_ref" ]] || return 1

    merged_prs_json="$(_vibe_roadmap_merged_prs_json)" || return 2
    print -r -- "$merged_prs_json" | jq -e --arg ref "$pr_ref" '.[]? | select((.number | tostring) == $ref)' >/dev/null 2>&1
}

_vibe_roadmap_compute_dependency_status() {
    local common_dir="$1" item_id="$2"
    local roadmap_file registry_file depends_on blockers_json blocker_count gh_available merged_prs_ready

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    registry_file="$common_dir/vibe/registry.json"
    depends_on="$(jq -c --arg id "$item_id" '.items[]? | select(.roadmap_item_id == $id) | .depends_on_item_ids // []' "$roadmap_file")"
    gh_available="false"
    merged_prs_ready="false"
    if _check_gh_available; then
        gh_available="true"
        if _vibe_roadmap_merged_prs_json >/dev/null; then
            merged_prs_ready="true"
        fi
    fi

    if [[ "$(print -r -- "$depends_on" | jq 'length')" -eq 0 ]]; then
        jq -n '{ready: true, blocked: false, blockers: []}'
        return 0
    fi

    blockers_json="$(
        print -r -- "$depends_on" | jq -r '.[]' | while read -r dep_id; do
            local matched_pr_refs has_merged_pr

            if ! _vibe_roadmap_has_dependency_item "$roadmap_file" "$dep_id"; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "missing_dependency_item"}'
                continue
            fi

            matched_pr_refs="$(_vibe_roadmap_dependency_task_prs "$registry_file" "$dep_id")"
            if [[ -z "$matched_pr_refs" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "missing_pr_ref"}'
                continue
            fi

            if [[ "$gh_available" != "true" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "merge_status_unavailable"}'
                continue
            fi

            if [[ "$merged_prs_ready" != "true" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "merge_status_unavailable"}'
                continue
            fi

            has_merged_pr="false"
            while read -r pr_ref; do
                [[ -n "$pr_ref" ]] || continue
                if _vibe_roadmap_pr_is_merged "$pr_ref"; then
                    has_merged_pr="true"
                    break
                fi
            done <<< "$matched_pr_refs"

            if [[ "$has_merged_pr" != "true" ]]; then
                jq -c -n --arg id "$dep_id" '{roadmap_item_id: $id, reason: "pr_not_merged"}'
            fi
        done | jq -s '. | map(select(. != null))'
    )"

    blocker_count="$(print -r -- "$blockers_json" | jq 'length')"
    if [[ "$blocker_count" -eq 0 ]]; then
        jq -n '{ready: true, blocked: false, blockers: []}'
    else
        print -r -- "$blockers_json" | jq -c '{ready: false, blocked: true, blockers: .}'
    fi
}

_vibe_roadmap_status_with_dependency_counts() {
    local common_dir="$1" roadmap_file="$2" status_json="$3"
    local dependency_ready=0 dependency_blocked=0 dep_status

    while IFS= read -r item_id; do
        dep_status="$(_vibe_roadmap_compute_dependency_status "$common_dir" "$item_id")"
        if [[ "$(echo "$dep_status" | jq -r '.ready')" == "true" ]]; then
            ((dependency_ready++))
        else
            ((dependency_blocked++))
        fi
    done < <(jq -r '.items[].roadmap_item_id' "$roadmap_file")

    print -r -- "$status_json" | jq -c --argjson ready "$dependency_ready" --argjson blocked "$dependency_blocked" '
        . + {dependency_counts: {ready: $ready, blocked: $blocked}}
    '
}

_vibe_roadmap_render_dependency_summary() {
    local status_json="$1" dep_ready dep_blocked
    dep_ready="$(print -r -- "$status_json" | jq -r '.dependency_counts.ready')"
    dep_blocked="$(print -r -- "$status_json" | jq -r '.dependency_counts.blocked')"

    echo "Dependency Status:"
    if _vibe_roadmap_supports_color; then
        printf "  %-16s  %b\n" "Ready:" "$(_vibe_roadmap_format "$GREEN" "($dep_ready)")"
        printf "  %-16s  %b\n" "Blocked:" "$(_vibe_roadmap_format "$RED" "($dep_blocked)")"
    else
        echo "  Ready:           $dep_ready"
        echo "  Blocked:         $dep_blocked"
    fi
    echo ""
}

_vibe_roadmap_render_item_dependency_status() {
    local dependency_status="$1"
    local dep_ready dep_blockers

    dep_ready="$(print -r -- "$dependency_status" | jq -r '.ready')"
    dep_blockers="$(print -r -- "$dependency_status" | jq -r '.blockers')"

    if [[ "$dep_ready" == "true" ]]; then
        echo "Dependency Status: $(_vibe_roadmap_format "$GREEN" "ready")"
    else
        echo "Dependency Status: $(_vibe_roadmap_format "$RED" "blocked")"
        echo ""
        echo "Blockers:"
        print -r -- "$dep_blockers" | jq -r '.[] | "  - \(.roadmap_item_id) (\(.reason))"'
        echo ""
    fi
}
