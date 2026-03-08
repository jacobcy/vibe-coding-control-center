#!/usr/bin/env zsh
# lib/roadmap_audit.sh - Audit operations for Roadmap module

_vibe_roadmap_audit() {
    local common_dir="$1" output_json="false" check_links="false" check_status="false" check_version_goal="false" roadmap_file
    shift

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_json="true"
                shift
                ;;
            --check-links)
                check_links="true"
                shift
                ;;
            --check-status)
                check_status="true"
                shift
                ;;
            --check-version-goal)
                check_version_goal="true"
                shift
                ;;
            *)
                echo "Error: Unknown option: $1"
                return 1
                ;;
        esac
    done

    if [[ "$check_links" == "false" && "$check_status" == "false" && "$check_version_goal" == "false" ]]; then
        check_status="true"
        check_version_goal="true"
    fi

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1

    local audit_json
    audit_json="$(jq -c \
        --argjson check_links "$check_links" \
        --argjson check_status "$check_status" \
        --argjson check_version_goal "$check_version_goal" \
        '{
          ok: (
            ((($check_status | not) or ([.items[]? | select((.status != "p0") and (.status != "current") and (.status != "next") and (.status != "deferred") and (.status != "rejected"))] | length == 0)))
            and
            ((($check_links | not) or ([.items[]? | select((.linked_task_ids | length) == 0)] | length == 0)))
            and
            ((($check_version_goal | not) or ((.version_goal // "") != "")))
          ),
          checks: {
            status: {
              enabled: $check_status,
              invalid_item_ids: (if $check_status then [.items[]? | select((.status != "p0") and (.status != "current") and (.status != "next") and (.status != "deferred") and (.status != "rejected")) | .roadmap_item_id] else [] end)
            },
            links: {
              enabled: $check_links,
              unlinked_item_ids: (if $check_links then [.items[]? | select((.linked_task_ids | length) == 0) | .roadmap_item_id] else [] end)
            },
            version_goal: {
              enabled: $check_version_goal,
              present: ((.version_goal // "") != "")
            }
          }
        }' \
        "$roadmap_file")"

    if [[ "$output_json" == "true" ]]; then
        echo "$audit_json"
    else
        local ok version_goal_present invalid_count unlinked_count
        ok="$(echo "$audit_json" | jq -r '.ok')"
        version_goal_present="$(echo "$audit_json" | jq -r '.checks.version_goal.present')"
        invalid_count="$(echo "$audit_json" | jq -r '.checks.status.invalid_item_ids | length')"
        unlinked_count="$(echo "$audit_json" | jq -r '.checks.links.unlinked_item_ids | length')"

        echo "Roadmap Audit"
        echo "  Status issues: $invalid_count"
        echo "  Unlinked items: $unlinked_count"
        echo "  Version goal present: $version_goal_present"
        [[ "$ok" == "true" ]] || echo "Audit failed."
    fi

    [[ "$(echo "$audit_json" | jq -r '.ok')" == "true" ]]
}
