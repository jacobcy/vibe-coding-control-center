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
    local common_dir roadmap_file
    common_dir="$(_vibe_roadmap_common_dir)" || return 1
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_require_file "$roadmap_file" "roadmap.json" || return 1

    local version_goal
    version_goal="$(jq -r '.version_goal // "none"' "$roadmap_file")"

    echo "========================================"
    echo "         Roadmap Status"
    echo "========================================"
    echo ""
    echo "Version Goal: $version_goal"
    echo ""

    echo "Issue Summary:"
    # Single jq call to get all counts, parse with read
    local counts
    local p0_count current_count next_count deferred_count rejected_count
    counts="$(jq -r '[.items[]? | .status] |
        {p0: (map(select(. == "p0")) | length),
         current: (map(select(. == "current")) | length),
         next: (map(select(. == "next")) | length),
         deferred: (map(select(. == "deferred")) | length),
         rejected: (map(select(. == "rejected")) | length)} |
        "\(.p0) \(.current) \(.next) \(.deferred) \(.rejected)"' "$roadmap_file")"
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
