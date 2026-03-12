#!/usr/bin/env zsh
# lib/roadmap_init.sh - Shared-state skeleton initialization for roadmap

_vibe_roadmap_registry_file() {
    local common_dir="$1"
    echo "$common_dir/vibe/registry.json"
}

_vibe_roadmap_worktrees_file() {
    local common_dir="$1"
    echo "$common_dir/vibe/worktrees.json"
}

_vibe_roadmap_shared_state_init() {
    local common_dir="$1"
    local force="${2:-false}"
    local vibe_dir="$common_dir/vibe"
    local roadmap_file="$(_vibe_roadmap_file "$common_dir")"
    local registry_file="$(_vibe_roadmap_registry_file "$common_dir")"
    local worktrees_file="$(_vibe_roadmap_worktrees_file "$common_dir")"
    local tasks_dir="$vibe_dir/tasks"
    local pending_tasks_dir="$vibe_dir/pending-tasks"

    mkdir -p "$vibe_dir" || return 1

    if [[ "$force" == "true" ]]; then
        rm -f "$roadmap_file" "$registry_file" "$worktrees_file" || return 1
        rm -rf "$tasks_dir" "$pending_tasks_dir" || return 1
    fi

    mkdir -p "$tasks_dir" "$pending_tasks_dir" || return 1

    if [[ ! -f "$roadmap_file" ]]; then
        jq -n '{schema_version: "v2", project_id: null, milestone: null, version_goal: null, items: []}' > "$roadmap_file" || return 1
    fi

    if [[ ! -f "$registry_file" ]]; then
        jq -n '{schema_version: "v2", tasks: []}' > "$registry_file" || return 1
    fi

    if [[ ! -f "$worktrees_file" ]]; then
        jq -n '{schema_version: "v2", worktrees: []}' > "$worktrees_file" || return 1
    fi

    if [[ "$force" == "true" ]]; then
        echo "Roadmap shared state rebuilt."
    else
        echo "Roadmap shared state initialized."
    fi
}

_vibe_roadmap_init_command() {
    local force="false"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                force="true"
                shift
                ;;
            *)
                vibe_die "Unknown roadmap init flag: $1"
                return 1
                ;;
        esac
    done

    local common_dir
    common_dir="$(_vibe_roadmap_common_dir)" || return 1
    _vibe_roadmap_shared_state_init "$common_dir" "$force"
}
