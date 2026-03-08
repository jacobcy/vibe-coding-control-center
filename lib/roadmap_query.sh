#!/usr/bin/env zsh
# lib/roadmap_query.sh - Read/Query operations for Roadmap module

_vibe_roadmap_require_file() {
    if [[ -f "$1" ]]; then
        return 0
    fi
    vibe_die "Missing $2: $1"
}

_vibe_roadmap_common_dir() {
    if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        vibe_die "Not in a git repository"
    fi
    git rev-parse --git-common-dir
}

_vibe_roadmap_file() {
    local common_dir="$1"
    echo "$common_dir/vibe/roadmap.json"
}

_vibe_roadmap_status() {
    local common_dir roadmap_file output_json="false"
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_json="true"
                shift
                ;;
            *)
                echo "Error: Unknown option: $1"
                return 1
                ;;
        esac
    done

    common_dir="$(_vibe_roadmap_common_dir)" || return 1
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1

    local status_json
    status_json="$(jq -c '{
        version_goal: .version_goal,
        counts: {
            p0: ([.items[]? | select(.status == "p0")] | length),
            current: ([.items[]? | select(.status == "current")] | length),
            next: ([.items[]? | select(.status == "next")] | length),
            deferred: ([.items[]? | select(.status == "deferred")] | length),
            rejected: ([.items[]? | select(.status == "rejected")] | length)
        }
    }' "$roadmap_file")"

    if [[ "$output_json" == "true" ]]; then
        echo "$status_json"
        return 0
    fi

    local version_goal counts p0_count current_count next_count deferred_count rejected_count
    version_goal="$(echo "$status_json" | jq -r '.version_goal // "none"')"

    echo "========================================"
    echo "         Roadmap Status"
    echo "========================================"
    echo ""
    echo "Version Goal: $version_goal"
    echo ""

    echo "Issue Summary:"
    counts="$(echo "$status_json" | jq -r '"\(.counts.p0) \(.counts.current) \(.counts.next) \(.counts.deferred) \(.counts.rejected)"')"
    IFS=' ' read -r p0_count current_count next_count deferred_count rejected_count <<< "$counts"

    echo "  P0 (urgent):      $p0_count"
    echo "  Current:          $current_count"
    echo "  Next:             $next_count"
    echo "  Deferred:         $deferred_count"
    echo "  Rejected:        $rejected_count"
    echo ""

    if [[ "$version_goal" == "none" ]]; then
        echo "${YELLOW}No version goal set. Run 'vibe roadmap assign' to set one.${NC}"
    fi
}

_vibe_roadmap_list() {
    local common_dir="$1" output_json="false" status_filter="" source_filter="" keywords="" linked="false" unlinked="false" roadmap_file
    shift

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_json="true"
                shift
                ;;
            --status)
                status_filter="$2"
                shift 2
                ;;
            --source)
                source_filter="$2"
                shift 2
                ;;
            --keywords)
                keywords="$2"
                shift 2
                ;;
            --linked)
                linked="true"
                shift
                ;;
            --unlinked)
                unlinked="true"
                shift
                ;;
            *)
                echo "Error: Unknown option: $1"
                return 1
                ;;
        esac
    done

    [[ "$linked" == "true" && "$unlinked" == "true" ]] && {
        echo "Error: --linked and --unlinked cannot be used together"
        return 1
    }

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1

    local items_json
    items_json="$(jq -c \
        --arg status "$status_filter" \
        --arg source "$source_filter" \
        --arg keywords "${keywords:l}" \
        --argjson linked "$linked" \
        --argjson unlinked "$unlinked" \
        '[.items[]?
          | select(
              ($status == "" or .status == $status)
              and ($source == "" or .source_type == $source)
              and ($keywords == "" or ((.roadmap_item_id + " " + .title + " " + (.description // "")) | ascii_downcase | contains($keywords)))
              and (($linked | not) or ((.linked_task_ids | length) > 0))
              and (($unlinked | not) or ((.linked_task_ids | length) == 0))
            )]' \
        "$roadmap_file")"

    if [[ "$output_json" == "true" ]]; then
        echo "$items_json"
        return 0
    fi

    if [[ "$(echo "$items_json" | jq 'length')" == "0" ]]; then
        echo "No roadmap items found."
        return 0
    fi

    echo "$items_json" | jq -r '.[] | "\(.roadmap_item_id)\t[\(.status)]\t\(.title)"'
}

_vibe_roadmap_show() {
    local common_dir="$1" item_id="$2" output_json="false" roadmap_file item_json
    shift 2

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json)
                output_json="true"
                shift
                ;;
            *)
                echo "Error: Unknown option: $1"
                return 1
                ;;
        esac
    done

    [[ -n "$item_id" ]] || { echo "Usage: vibe roadmap show <roadmap-item-id> [--json]"; return 1; }

    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1
    item_json="$(jq -c --arg id "$item_id" '.items[]? | select(.roadmap_item_id == $id)' "$roadmap_file" | head -n 1)"
    [[ -n "$item_json" ]] || { echo "Error: roadmap item not found: $item_id"; return 1; }

    if [[ "$output_json" == "true" ]]; then
        echo "$item_json"
        return 0
    fi

    echo "$item_json" | jq -r '
        "Roadmap Item: \(.roadmap_item_id)\n" +
        "Title: \(.title)\n" +
        "Status: \(.status)\n" +
        "Source: \(.source_type)\n" +
        "Description: \(.description // "null")\n" +
        "Linked Tasks: \((.linked_task_ids | join(", ")))\n" +
        "Issue Refs: \((.issue_refs | join(", ")))\n" +
        "Updated At: \(.updated_at)"'
}

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
        check_links="true"
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

_vibe_roadmap_get_version_goal() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq -r '.version_goal // empty' "$roadmap_file"
}

_vibe_roadmap_has_version_goal() {
    local common_dir="$1" version_goal
    version_goal="$(_vibe_roadmap_get_version_goal "$common_dir")"
    [[ -n "$version_goal" ]]
}

_vibe_roadmap_get_current_issues() {
    local common_dir="$1" roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    jq -c '[.items[]? | select(.status == "current" or .status == "p0")]' "$roadmap_file"
}
