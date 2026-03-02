#!/usr/bin/env zsh
_vibe_task_common_dir() { git rev-parse --is-inside-work-tree >/dev/null 2>&1 || { vibe_die "Not in a git repository"; return 1; }; git rev-parse --git-common-dir; }
_vibe_task_now() { date +"%Y-%m-%dT%H:%M:%S%z"; }
_vibe_task_slugify() { print -r -- "$1" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//'; }
_vibe_task_require_file() { [[ -f "$1" ]] || { vibe_die "Missing $2: $1"; return 1; }; }
_vibe_task_task_file() { echo "$1/vibe/tasks/$2/task.json"; }

# Source I/O operations (render and write functions)
source "$VIBE_LIB/task_io.sh"

_vibe_task_usage() {
    echo "Usage: vibe task [list] [-a|--all] [--json]"
    echo "       vibe task add <task-id> --title <title> [--status <status>] [--next-step <text>]"
    echo "       vibe task update <task-id> [options]"
    echo "       vibe task remove <task-id>"
    echo "       vibe task sync"
}
_vibe_task_collect_openspec_tasks() {
    local repo_root="$1" changes_dir="$repo_root/openspec/changes" aggregate_file change_dir change_name tasks_file total_tasks done_tasks change_status next_step
    [[ -d "$changes_dir" ]] || { echo '{"tasks":[]}'; return 0; }
    aggregate_file="$(mktemp)" || return 1
    echo '[]' > "$aggregate_file"
    for change_dir in "$changes_dir"/*(N); do
        [[ -d "$change_dir" ]] || continue
        change_name="$(basename "$change_dir")"
        [[ "$change_name" == "archive" ]] && continue
        tasks_file="$change_dir/tasks.md"; total_tasks=0; done_tasks=0
        if [[ -f "$tasks_file" ]]; then
            total_tasks="$(grep -E '^- \[( |x|X)\]' "$tasks_file" | wc -l | tr -d ' ')"
            done_tasks="$(grep -E '^- \[[xX]\]' "$tasks_file" | wc -l | tr -d ' ')"
        fi
        if [[ "$total_tasks" -gt 0 && "$done_tasks" -eq "$total_tasks" ]]; then
            change_status="completed"
        elif [[ "$done_tasks" -gt 0 ]]; then
            change_status="in-progress"
        else
            change_status="todo"
        fi
        next_step="Continue OpenSpec change: openspec/changes/$change_name/tasks.md"
        jq --arg task_id "$change_name" --arg title "$change_name" --arg framework "openspec" --arg source_path "openspec/changes/$change_name" --arg status "$change_status" --arg next_step "$next_step" '. += [{task_id:$task_id,title:$title,framework:$framework,source_path:$source_path,status:$status,current_subtask_id:null,assigned_worktree:null,next_step:$next_step}]' "$aggregate_file" > "$aggregate_file.tmp" && mv "$aggregate_file.tmp" "$aggregate_file"
    done
    jq -n --slurpfile tasks "$aggregate_file" '{"tasks":($tasks[0] // [])}'
    rm -f "$aggregate_file"
}

_vibe_task_list() {
    local common_dir worktrees_file registry_file show_all="0" json_out="0" missing openspec_tasks_file repo_root
    for arg in "$@"; do
        case "$arg" in
            -a|--all) show_all="1" ;;
            --json) json_out="1" ;;
            -h|--help)
                _vibe_task_usage
                echo "  Show active worktrees and tasks in the registry."
                echo "  -a, --all    Show all tasks including completed/archived."
                echo "  --json       Output merged task/worktree data as JSON."
                return 0
                ;;
            *) vibe_die "Unknown list option: $arg"; return 1 ;;
        esac
    done
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1
    worktrees_file="$common_dir/vibe/worktrees.json"
    registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
    openspec_tasks_file="$(mktemp)" || return 1
    _vibe_task_collect_openspec_tasks "$repo_root" > "$openspec_tasks_file"

    if [[ "$json_out" == "1" ]]; then
        jq -n --slurpfile reg "$registry_file" --slurpfile wt "$worktrees_file" --slurpfile os "$openspec_tasks_file" '{tasks: (($reg[0].tasks // []) + ($os[0].tasks // []) | unique_by(.task_id)), worktrees: ($wt[0].worktrees // [])}'
        rm -f "$openspec_tasks_file"
        return 0
    fi

    missing="$(jq -r --slurpfile registry "$registry_file" --slurpfile openspec "$openspec_tasks_file" '((($registry[0].tasks // []) + ($openspec[0].tasks // []) | unique_by(.task_id)) as $all | [.worktrees[]? as $w | select($w.current_task != null) | select(($all | map(.task_id) | index($w.current_task)) == null) | $w.current_task] | unique[])' "$worktrees_file")" || { rm -f "$openspec_tasks_file"; return 1; }
    [[ -z "$missing" ]] || { rm -f "$openspec_tasks_file"; vibe_die "Task not found in registry: ${missing%%$'\n'*}"; return 1; }
    _vibe_task_render "$worktrees_file" "$registry_file" "$openspec_tasks_file" "$show_all"
    rm -f "$openspec_tasks_file"
}

_vibe_task_update() {
    local task_id="${1:-}" task_status="" agent="" worktree="" branch="" next_step="" bind_current=0 force=0 common_dir registry_file worktrees_file now target_name="" target_path="" email_slug="" unassign=0
    shift $(( $# > 0 ? 1 : 0 ))
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task update <task-id> [options]"; echo "  Supported fields: --status --agent --worktree --branch --bind-current --next-step --unassign"; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for update"; return 1; }
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --status|--agent|--worktree|--branch|--next-step) [[ $# -ge 2 ]] || { vibe_die "Missing value for $1"; return 1; }; case "$1" in --status) task_status="$2" ;; --agent) agent="$2" ;; --worktree) worktree="$2" ;; --branch) branch="$2" ;; --next-step) next_step="$2" ;; esac; shift 2 ;;
            --bind-current) bind_current=1; shift ;;
            --unassign) unassign=1; shift ;;
            -f|--force) force=1; shift ;;
            -h|--help) echo "Usage: vibe task update <task-id> [options]"; echo "  Supported fields: --status --agent --worktree --branch --bind-current --next-step --unassign"; return 0 ;;
            *) vibe_die "Unknown update option: $1"; return 1 ;;
        esac
    done
    [[ -n "$task_status$agent$worktree$branch$next_step" || "$bind_current" -eq 1 || "$unassign" -eq 1 ]] || { vibe_die "No update fields provided"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    if [[ -n "$agent" ]]; then
        case "$agent" in codex|antigravity|trae|claude|opencode|kiro) ;; *) [[ "$force" -eq 1 ]] || { vibe_die "Unsupported agent: $agent"; return 1; } ;; esac
        email_slug="$agent"; [[ "$force" -eq 1 ]] && email_slug="$(_vibe_task_slugify "$agent")"
        git config user.name "$agent" 2>/dev/null || git config user.name "$agent" || return 1
        git config user.email "${email_slug}@vibe.coding" 2>/dev/null || git config user.email "${email_slug}@vibe.coding" || return 1
    fi
    if [[ "$unassign" -eq 1 ]]; then
        worktree=""
    fi
    [[ "$bind_current" -eq 1 ]] && { target_name="$(basename "$PWD")"; target_path="$PWD"; worktree="$target_name"; }
    [[ -z "$target_name" ]] && target_name="$worktree"
    _vibe_task_write_registry "$registry_file" "$task_id" "$task_status" "$next_step" "$worktree" "$agent" "$now" || return 1
    _vibe_task_write_task_file "$common_dir" "$registry_file" "$task_id" "$now" || return 1
    _vibe_task_write_worktrees "$worktrees_file" "$target_name" "$target_path" "$task_id" "$branch" "$agent" "$bind_current" "$now" || return 1
    [[ "$bind_current" -eq 1 ]] && _vibe_task_refresh_cache "$common_dir" "$registry_file" "$task_id" "$target_name" "$now"
    return 0
}

_vibe_task_add() {
    local task_id="${1:-}" title="" task_status="todo" next_step="" common_dir registry_file task_file now tmp
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task add <task-id> --title <title> [--status <status>] [--next-step <text>]"; echo "  Register a task in the shared registry."; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for add"; return 1; }
    shift
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --title|--status|--next-step) [[ $# -ge 2 ]] || { vibe_die "Missing value for $1"; return 1; }; case "$1" in --title) title="$2" ;; --status) task_status="$2" ;; --next-step) next_step="$2" ;; esac; shift 2 ;;
            *) vibe_die "Unknown add option: $1"; return 1 ;;
        esac
    done
    [[ -n "$title" ]] || { vibe_die "Missing --title for add"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"; now="$(_vibe_task_now)"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 && { vibe_die "Task already exists: $task_id"; return 1; }
    mkdir -p "$(dirname "$task_file")"; tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" --arg title "$title" --arg task_status "$task_status" --arg next_step "$next_step" --arg now "$now" '.tasks += [{task_id:$task_id,title:$title,status:$task_status,current_subtask_id:null,assigned_worktree:null,next_step:$next_step,updated_at:$now}]' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    jq -n --arg task_id "$task_id" --arg title "$title" --arg task_status "$task_status" --arg next_step "$next_step" '{task_id:$task_id,title:$title,status:$task_status,subtasks:[],assigned_worktree:null,next_step:$next_step}' > "$task_file"
}

_vibe_task_remove() {
    local task_id="${1:-}" common_dir registry_file worktrees_file task_file tmp
    [[ "$task_id" == "-h" || "$task_id" == "--help" ]] && { echo "Usage: vibe task remove <task-id>"; echo "  Remove a task from the shared registry."; return 0; }
    [[ -n "$task_id" ]] || { vibe_die "Missing task id for remove"; return 1; }
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1; registry_file="$common_dir/vibe/registry.json"; worktrees_file="$common_dir/vibe/worktrees.json"; task_file="$(_vibe_task_task_file "$common_dir" "$task_id")"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1; _vibe_task_require_file "$worktrees_file" "worktrees.json" || return 1
    jq -e --arg task_id "$task_id" '.tasks[]? | select(.task_id == $task_id)' "$registry_file" >/dev/null 2>&1 || { vibe_die "Task not found in registry: $task_id"; return 1; }
    jq -e --arg task_id "$task_id" '.worktrees[]? | select(.current_task == $task_id)' "$worktrees_file" >/dev/null 2>&1 && { vibe_die "Task is still bound to a worktree: $task_id"; return 1; }
    tmp="$(mktemp)" || return 1
    jq --arg task_id "$task_id" '.tasks |= map(select(.task_id != $task_id))' "$registry_file" > "$tmp" && mv "$tmp" "$registry_file" || return 1
    rm -f "$task_file"; rmdir "$(dirname "$task_file")" 2>/dev/null || true
}

_vibe_task_sync() {
    local common_dir registry_file repo_root openspec_tasks_file merged_file
    vibe_require git jq || return 1
    common_dir="$(_vibe_task_common_dir)" || return 1
    registry_file="$common_dir/vibe/registry.json"
    _vibe_task_require_file "$registry_file" "registry.json" || return 1
    repo_root="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
    openspec_tasks_file="$(mktemp)" || return 1
    merged_file="$(mktemp)" || { rm -f "$openspec_tasks_file"; return 1; }
    _vibe_task_collect_openspec_tasks "$repo_root" > "$openspec_tasks_file"
    jq --slurpfile os "$openspec_tasks_file" '.tasks = ((.tasks // []) + ($os[0].tasks // []) | unique_by(.task_id))' "$registry_file" > "$merged_file" && mv "$merged_file" "$registry_file"
    rm -f "$openspec_tasks_file"
    log_success "OpenSpec tasks synced to registry"
}

vibe_task() {
    local subcommand="${1:-list}"
    case "$subcommand" in
        list) [[ $# -gt 0 ]] && shift; _vibe_task_list "$@" ;;
        add) [[ $# -gt 0 ]] && shift; _vibe_task_add "$@" ;;
        update) [[ $# -gt 0 ]] && shift; _vibe_task_update "$@" ;;
        remove) [[ $# -gt 0 ]] && shift; _vibe_task_remove "$@" ;;
        sync) [[ $# -gt 0 ]] && shift; _vibe_task_sync "$@" ;;
        -h|--help|help) _vibe_task_usage ;;
        -*) _vibe_task_list "$@" ;;
        "") _vibe_task_list ;;
        *) vibe_die "Unknown task subcommand: $subcommand"; return 1 ;;
    esac
}
