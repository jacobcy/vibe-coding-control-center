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

_vibe_roadmap_color_status() {
    local s="$1"
    case "$s" in
        p0) echo "${RED}${BOLD}${s}${NC}" ;;
        current) echo "${GREEN}${s}${NC}" ;;
        next) echo "${BLUE}${s}${NC}" ;;
        deferred) echo "${YELLOW}${s}${NC}" ;;
        rejected) echo -e "\033[0;90m${s}${NC}" ;; # Grey
        *) echo "$s" ;;
    esac
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
    echo "         ${BOLD}Roadmap Status${NC}"
    echo "========================================"
    echo ""
    echo "Version Goal: ${CYAN}${version_goal}${NC}"
    echo ""

    echo "Issue Summary:"
    counts="$(echo "$status_json" | jq -r '"\(.counts.p0) \(.counts.current) \(.counts.next) \(.counts.deferred) \(.counts.rejected)"')"
    IFS=' ' read -r p0_count current_count next_count deferred_count rejected_count <<< "$counts"

    printf "  %-16s  %b\n" "P0 (urgent):" "$(_vibe_roadmap_color_status "p0") ($p0_count)"
    printf "  %-16s  %b\n" "Current:" "$(_vibe_roadmap_color_status "current") ($current_count)"
    printf "  %-16s  %b\n" "Next:" "$(_vibe_roadmap_color_status "next") ($next_count)"
    printf "  %-16s  %b\n" "Deferred:" "$(_vibe_roadmap_color_status "deferred") ($deferred_count)"
    printf "  %-16s  %b\n" "Rejected:" "$(_vibe_roadmap_color_status "rejected") ($rejected_count)"
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

    local row item_status rid title colored_status
    echo "$items_json" | jq -c '.[]' | while read -r row; do
        item_status=$(echo "$row" | jq -r '.status')
        rid=$(echo "$row" | jq -r '.roadmap_item_id')
        title=$(echo "$row" | jq -r '.title')
        colored_status=$(_vibe_roadmap_color_status "$item_status")
        
        if [[ "$title" == "$rid" || -z "$title" ]]; then
            printf "[%b] %s\n" "$colored_status" "$rid"
        else
            printf "[%b] %-12s  %s\n" "$colored_status" "$rid" "$title"
        fi
    done
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

    # Read fields
    local id title item_status source description tasks issues updated
    id=$(echo "$item_json" | jq -r '.roadmap_item_id')
    title=$(echo "$item_json" | jq -r '.title')
    item_status=$(echo "$item_json" | jq -r '.status')
    source=$(echo "$item_json" | jq -r '.source_type')
    description=$(echo "$item_json" | jq -r '.description // ""')
    tasks=$(echo "$item_json" | jq -r '.linked_task_ids | join(", ")')
    issues=$(echo "$item_json" | jq -r '.issue_refs | join(", ")')
    updated=$(echo "$item_json" | jq -r '.updated_at')

    local colored_status
    colored_status=$(_vibe_roadmap_color_status "$item_status")

    echo "Roadmap Item: ${CYAN}${BOLD}${id}${NC}"
    echo "----------------------------------------"
    echo "Title:       ${BOLD}${title}${NC}"
    echo "Status:      ${colored_status}"
    echo "Source:      ${source}"
    echo "Updated:     ${updated}"
    echo ""
    if [[ -n "$description" ]]; then
        echo "Description:"
        echo "  ${description}"
        echo ""
    fi
    if [[ -n "$tasks" ]]; then
        echo "Linked Tasks:"
        echo "  ${tasks}"
    fi
    if [[ -n "$issues" ]]; then
        echo "Issue Refs:"
        echo "  ${issues}"
    fi
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
