#!/usr/bin/env zsh
# lib/roadmap.sh - Roadmap module for intelligent scheduling

# Load dependencies
source "$VIBE_LIB/roadmap_render.sh"
source "$VIBE_LIB/roadmap_store.sh"
source "$VIBE_LIB/roadmap_query.sh"
source "$VIBE_LIB/roadmap_audit.sh"
source "$VIBE_LIB/roadmap_write.sh"
source "$VIBE_LIB/roadmap_project_sync.sh"
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
        list)
            shift
            local common_dir="$(_vibe_roadmap_common_dir)" || return 1
            _vibe_roadmap_list "$common_dir" "$@"
            ;;
        show)
            shift
            local common_dir="$(_vibe_roadmap_common_dir)" || return 1
            _vibe_roadmap_show "$common_dir" "$@"
            ;;
        audit)
            shift
            local common_dir="$(_vibe_roadmap_common_dir)" || return 1
            _vibe_roadmap_audit "$common_dir" "$@"
            ;;
        add)
            shift
            local common_dir="$(_vibe_roadmap_common_dir)" || return 1
            _vibe_roadmap_add "$common_dir" "$*"
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
    local project_id=""
    local output_json="false"

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
            --project-id)
                project_id="$2"
                shift 2
                ;;
            --json)
                output_json="true"
                shift
                ;;
            *)
                shift
                ;;
        esac
    done

    local common_dir
    common_dir="$(_vibe_roadmap_common_dir)" || return 1

    [[ -n "$repo" ]] || repo="$(_vibe_roadmap_current_repo)" || return 1
    [[ -n "$project_id" ]] || project_id="$(_vibe_roadmap_project_id "$common_dir")" || return 1

    case "$provider" in
        github)
            if [[ -z "$project_id" ]]; then
                echo "Error: roadmap.json project_id required for GitHub Project sync"
                return 1
            fi
            if [[ "$output_json" == "true" ]]; then
                jq -n \
                  --arg provider "$provider" \
                  --arg repo "$repo" \
                  --arg project_id "$project_id" \
                  '{
                    mode: "project_first",
                    official_layer: {
                      provider: $provider,
                      repo: $repo,
                      project_id: $project_id,
                      primary_object: "github_project_item_mirror",
                      sync_direction: "bidirectional"
                    },
                    local_execution_layer: {
                      sync: "local_only",
                      fields: ["execution_record_id", "spec_standard", "spec_ref", "linked_task_ids"]
                    }
                  }'
                return 0
            fi
            _vibe_roadmap_sync_github "$common_dir" "$repo" "$project_id"
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
    local roadmap_file
    roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    _vibe_roadmap_init "$common_dir"

    case "$action" in
        set-goal)
            shift
            _vibe_roadmap_assign "$common_dir" "$*"
            ;;
        clear-goal)
            jq '.version_goal = null' "$roadmap_file" > "${roadmap_file}.tmp" && mv "${roadmap_file}.tmp" "$roadmap_file"
            echo "Version goal cleared."
            ;;
        *)
            echo "Usage: vibe roadmap version <set-goal|clear-goal> [text]"
            ;;
    esac
}
