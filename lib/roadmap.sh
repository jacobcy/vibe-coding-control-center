#!/usr/bin/env zsh
# lib/roadmap.sh - Roadmap module for intelligent scheduling

# Load dependencies
source "$VIBE_LIB/roadmap_query.sh"
source "$VIBE_LIB/roadmap_write.sh"
source "$VIBE_LIB/roadmap_help.sh"

vibe_roadmap() {
    local subcommand="${1:-status}"

    # Handle help flag
    case "$subcommand" in
        -h|--help|help)
            _vibe_roadmap_usage
            return 0
            ;;
    esac

    case "$subcommand" in
        status)
            shift
            _vibe_roadmap_status "$@"
            ;;
        sync)
            shift
            _vibe_roadmap_sync "$@"
            ;;
        assign)
            shift
            local common_dir="$(_vibe_roadmap_common_dir)" || return 1
            _vibe_roadmap_assign "$common_dir" "$@"
            ;;
        classify)
            shift
            _vibe_roadmap_classify_handler "$@"
            ;;
        version)
            shift
            _vibe_roadmap_version "$@"
            ;;
        *)
            vibe_die "Unknown roadmap subcommand: $subcommand"; return 1 ;;
    esac
}

# Sync subcommand handler
_vibe_roadmap_sync() {
    local provider="github"
    local repo=""
    local label="vibe-task"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --provider)
                provider="$2"
                shift 2
                ;;
            --repo)
                repo="$2"
                shift 2
                ;;
            --label)
                label="$2"
                shift 2
                ;;
            *)
                shift
                ;;
        esac
    done

    local common_dir
    common_dir="$(_vibe_roadmap_common_dir)" || return 1

    case "$provider" in
        github)
            if [[ -z "$repo" ]]; then
                echo "Error: --repo required for GitHub sync"
                return 1
            fi
            _vibe_roadmap_sync_github "$common_dir" "$repo" "$label"
            ;;
        *)
            echo "Error: Unknown provider: $provider"
            return 1
            ;;
    esac
}

# Classify subcommand handler
_vibe_roadmap_classify_handler() {
    local issue_id=""
    local issue_status=""

    while [[ $# -gt 0 ]]; do
        case "$1" in
            -s|--status)
                issue_status="$2"
                shift 2
                ;;
            *)
                if [[ -z "$issue_id" ]]; then
                    issue_id="$1"
                fi
                shift
                ;;
        esac
    done

    if [[ -z "$issue_id" || -z "$issue_status" ]]; then
        echo "Usage: vibe roadmap classify <issue-id> --status <p0|current|next|deferred|rejected>"
        return 1
    fi

    local common_dir
    common_dir="$(_vibe_roadmap_common_dir)" || return 1
    _vibe_roadmap_classify "$common_dir" "$issue_id" "$issue_status"
}

# Version subcommand handler - for version cycle management
_vibe_roadmap_version() {
    local action="$1"
    local common_dir

    common_dir="$(_vibe_roadmap_common_dir)" || return 1
    local registry_file="$common_dir/vibe/registry.json"

    case "$action" in
        bump)
            local bump_type="${2:-minor}"
            local current_version
            current_version="$(jq -r '.roadmap.current_version // "v0.0"' "$registry_file")"

            # Parse version number
            local major minor
            major="$(echo "$current_version" | sed 's/v\([0-9]*\).*/\1/')"
            minor="$(echo "$current_version" | sed 's/v[0-9]*\.\([0-9]*\)/\1/')"

            if [[ "$bump_type" == "major" ]]; then
                major=$((major + 1))
                minor=0
            else
                minor=$((minor + 1))
            fi

            local new_version="v${major}.${minor}"
            jq --arg v "$new_version" '.roadmap.current_version = $v' "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"

            echo "Version bumped to: $new_version"
            ;;
        next)
            # Move "next" issues to "current" - batch update in single write
            local next_count
            next_count="$(jq '[.roadmap.issues[]? | select(.status == "next")] | length' "$registry_file")"

            if [[ "$next_count" == "0" || "$next_count" == "null" ]]; then
                echo "No issues in 'next' status to promote."
                return 0
            fi

            # Single jq to update all "next" to "current"
            jq '(.roadmap.issues[]? | select(.status == "next") | .status) = "current"' \
                "$registry_file" > "${registry_file}.tmp" && mv "${registry_file}.tmp" "$registry_file"

            echo "Promoted $next_count 'next' issues to 'current'."
            ;;
        complete)
            # Mark current version as complete and prepare for next
            local current_version
            current_version="$(jq -r '.roadmap.current_version // "v0.0"' "$registry_file")"

            echo "Version $current_version marked as complete!"
            echo "Run 'vibe roadmap version bump' to increment version"
            echo "Run 'vibe roadmap version next' to promote next issues"
            ;;
        *)
            echo "Usage: vibe roadmap version <bump|next|complete> [major|minor]"
            ;;
    esac
}
