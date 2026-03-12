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

_vibe_roadmap_validate_project_id() {
    local project_id="$1"
    [[ -n "$project_id" ]] || return 1
    [[ "$project_id" == PVT_* ]] || return 1
}

_vibe_roadmap_project_id_guidance() {
    cat <<'EOF'
Error: roadmap init requires a GitHub Project project_id.

Provide it with one of:
- vibe roadmap init --project-id <PVT_...>
- export GITHUB_PROJECT_ID=<PVT_...>

If you only know the project number, query it first:
  gh project view <number> --owner <owner>
EOF
}

_vibe_roadmap_shared_state_init() {
    local common_dir="$1"
    local force="${2:-false}"
    local project_id="$3"
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
        jq -n --arg project_id "$project_id" '{schema_version: "v2", project_id: $project_id, milestone: null, version_goal: null, items: []}' > "$roadmap_file" || return 1
    else
        local tmp
        tmp="$(mktemp)" || return 1
        jq --arg project_id "$project_id" '.project_id = $project_id' "$roadmap_file" > "$tmp" && mv "$tmp" "$roadmap_file" || {
            rm -f "$tmp"
            return 1
        }
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
    local project_id="${GITHUB_PROJECT_ID:-}"

    while [[ $# -gt 0 ]]; do
        case "$1" in
            --force)
                force="true"
                shift
                ;;
            --project-id)
                [[ $# -ge 2 ]] || {
                    vibe_die "Missing value for --project-id"
                    return 1
                }
                project_id="$2"
                shift 2
                ;;
            *)
                vibe_die "Unknown roadmap init flag: $1"
                return 1
                ;;
        esac
    done

    local common_dir
    common_dir="$(_vibe_roadmap_common_dir)" || return 1

    if [[ -z "$project_id" ]]; then
        local roadmap_file existing_project_id=""
        roadmap_file="$(_vibe_roadmap_file "$common_dir")"
        if [[ -f "$roadmap_file" ]]; then
            existing_project_id="$(jq -r '.project_id // empty' "$roadmap_file" 2>/dev/null || true)"
        fi
        project_id="$existing_project_id"
    fi

    if ! _vibe_roadmap_validate_project_id "$project_id"; then
        _vibe_roadmap_project_id_guidance >&2
        return 1
    fi

    _vibe_roadmap_shared_state_init "$common_dir" "$force" "$project_id"
}
