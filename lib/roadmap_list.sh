#!/usr/bin/env zsh
# lib/roadmap_list.sh - Roadmap list command
[[ -n "${VIBE_LIB:-}" && -f "$VIBE_LIB/roadmap_store.sh" ]] && source "$VIBE_LIB/roadmap_store.sh"

_vibe_roadmap_list() {
    local common_dir="$1" output_json="false" status_filter="" source_filter="" keywords="" linked="false" unlinked="false" show_all="false" roadmap_file
    shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --json) output_json="true"; shift ;;
            --status) status_filter="$2"; shift 2 ;;
            --source) source_filter="$2"; shift 2 ;;
            --keywords) keywords="$2"; shift 2 ;;
            --linked) linked="true"; shift ;;
            --unlinked) unlinked="true"; shift ;;
            --all) show_all="true"; shift ;;
            *) echo "Error: Unknown option: $1"; return 1 ;;
        esac
    done

    # Default logic: if no filters, show active items (p0,current,next)
    if [[ -z "$status_filter" && -z "$source_filter" && -z "$keywords" && "$linked" == "false" && "$unlinked" == "false" ]]; then
        status_filter="p0,current,next"
    fi

    # Warning for --json without filters (may produce large output)
    if [[ "$output_json" == "true" && -z "$keywords" && "$show_all" == "true" ]]; then
        echo "${YELLOW}WARNING: JSON output without --keywords filter may produce large data. Consider using --keywords to filter results.${NC}" >&2
        # Ask for confirmation in interactive mode
        if [[ -t 0 && -z "${VIBE_FORCE:-}" ]]; then
            echo -n "Continue? [y/N] "
            read -r response
            [[ "$response" =~ ^[Yy]$ ]] || return 0
        fi
    fi

    [[ "$linked" == "true" && "$unlinked" == "true" ]] && { echo "Error: --linked and --unlinked cannot be used together"; return 1; }
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1

    local limit=10
    [[ "$show_all" == "true" || "$output_json" == "true" ]] && limit=999999

    # Build the main jq pipeline for filtering and sorting
    local jq_filter
    jq_filter='("," + $status_csv + ",") as $csv 
      | (.items // []) 
      | map(select(type == "object") | . as $item | $item.status as $s | select(
          ($status_csv == "" or ($csv | contains("," + ($s // "") + ",")))
          and ($source == "" or ($item.source_type // "") == $source)
          and ($keywords == "" or ((($item.roadmap_item_id // "") + " " + ($item.title // "") + " " + ($item.description // "")) | ascii_downcase | contains($keywords)))
          and (($linked | not) or (($item.linked_task_ids // [] | length) > 0))
          and (($unlinked | not) or (($item.linked_task_ids // [] | length) == 0))
        ))
      | sort_by(.updated_at // "") | reverse'

    if [[ "$output_json" == "true" ]]; then
        jq -c --arg status_csv "$status_filter" \
              --arg source "$source_filter" \
              --arg keywords "${keywords:l}" \
              --argjson linked "$linked" \
              --argjson unlinked "$unlinked" \
              "$jq_filter" "$roadmap_file"
        return 0
    fi

    local items_json
    items_json="$(jq -c --arg status_csv "$status_filter" \
                       --arg source "$source_filter" \
                       --arg keywords "${keywords:l}" \
                       --argjson linked "$linked" \
                       --argjson unlinked "$unlinked" \
                       "$jq_filter" "$roadmap_file")"

    if [[ "$(print -r -- "$items_json" | jq 'length')" == "0" ]]; then
        echo "No roadmap items found."
        return 0
    fi

    local first_group="true" group_status group_items group_count row rid title
    local -a ordered_statuses=(p0 current next deferred rejected)

    # If limited, we apply the limit globally after sorting but before grouping
    local limited_items
    limited_items="$(print -r -- "$items_json" | jq -c --argjson limit "$limit" '.[0:$limit]')"

    for group_status in "${ordered_statuses[@]}"; do
        group_items="$(print -r -- "$limited_items" | jq -c --arg status "$group_status" 'map(select(.status == $status))')"
        group_count="$(print -r -- "$group_items" | jq 'length')"
        [[ "$group_count" == "0" ]] && continue

        if [[ "$first_group" == "true" ]]; then
            first_group="false"
        else
            printf '\n'
        fi

        printf '%s\n' "$(_vibe_roadmap_group_heading "$group_status" "$group_count")"
        # Robust iteration: pass the whole array to jq and extract fields in one command to avoid echo corruption
        print -r -- "$group_items" | jq -r '.[] | "\(.roadmap_item_id)\t\(.title // "")"' | while IFS=$'\t' read -r rid title; do
            if [[ "$title" == "$rid" || -z "$title" ]]; then
                printf '  %-10s\n' "$rid"
            else
                printf '  %-10s  %s\n' "$rid" "$title"
            fi
        done
    done

    # Inform the user if items were hidden
    local total_count
    total_count="$(print -r -- "$items_json" | jq 'length')"
    if [[ "$show_all" == "false" && "$total_count" -gt "$limit" ]]; then
        printf '\n%s\n' "${CYAN}Showing 10 of $total_count items. Use --all to see the full list.${NC}"
    fi
}
